"""ZIP upload extraction (Phase 5).

Kept entirely separate from the direct multi-file upload loop in
app/api/resumes.py, on purpose - the direct-upload path is already
working/tested, and ZIP handling has enough unique concerns (nested
folders, zip-slip, zip-bomb caps, per-entry corruption) that duplicating
the small amount of logic shared with it (hash, per-job dedup check,
Resume insert) here is safer than reshaping that existing code around a
new shared abstraction.

Security posture:
  - Never uses ZipFile.extract()/extractall() (the classic zip-slip vector,
    which writes to a path derived from the archive). Every member is read
    via ZipFile.open() and written to a destination WE choose
    (sanitize_filename() + the existing job/batch storage prefix) -
    the archive's internal path is used only to derive a display basename,
    never as a filesystem path.
  - No recursive extraction - a nested .zip inside the archive is treated
    as an unsupported entry, never opened.
  - Declared per-entry size (ZipInfo.file_size) and the compressed/
    decompressed ratio are cheap pre-filters; the AUTHORITATIVE cap is
    enforced while actually streaming each member's bytes
    (storage_service.save_stream), since a crafted header can lie about
    the declared size.
  - Whole-request entry-count and archive-size caps are checked by the
    caller (app/api/resumes.py) before any member here is ever opened.
  - Every rejected/failed/duplicate member is cleaned up immediately -
    nothing extracted from a non-accepted entry is ever left on disk.
"""
import logging
import os
import zipfile
from dataclasses import dataclass, field
from functools import partial
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.resume import Resume
from app.services.storage import storage_service, sanitize_filename, make_unique_basename

logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".pdf", ".docx"}
_JUNK_PREFIXES = ("__MACOSX/",)
_JUNK_BASENAMES = {".ds_store"}

# Above this ratio of declared-uncompressed to actual-stored bytes, treat an
# entry as a suspected zip bomb and reject it without ever decompressing it.
_MAX_COMPRESSION_RATIO = 100

_READ_CHUNK_BYTES = 1024 * 1024


@dataclass
class ZipIngestResult:
    accepted_resume_ids: List[int] = field(default_factory=list)
    accepted: int = 0
    duplicate: int = 0
    unsupported: int = 0
    failed: int = 0


def _is_supported_entry(info: zipfile.ZipInfo) -> bool:
    if info.is_dir():
        return False
    name = info.filename
    if any(name.startswith(p) for p in _JUNK_PREFIXES):
        return False
    base = os.path.basename(name.rstrip("/"))
    if not base or base.lower() in _JUNK_BASENAMES or base.startswith("."):
        return False
    ext = os.path.splitext(base)[1].lower()
    return ext in _ALLOWED_EXTENSIONS


def count_supported_entries(zf: zipfile.ZipFile) -> int:
    """Cheap - reads only the already-parsed central directory in memory,
    no decompression. Used by the caller to enforce the combined
    direct-files + ZIP-contents cap BEFORE extracting anything."""
    return sum(1 for info in zf.infolist() if _is_supported_entry(info))


def _delete_saved_file(storage_key: str) -> None:
    full_path = storage_service.get_secure_path(storage_key)
    if full_path and os.path.exists(full_path):
        try:
            os.remove(full_path)
        except OSError as e:
            logger.warning("zip_ingest: failed to remove orphaned file %s: %s", full_path, e)


async def extract_zip_into_batch(
    db: AsyncSession, zf: zipfile.ZipFile, *, job_id: int, batch_id: int, used_basenames: set | None = None
) -> ZipIngestResult:
    """Walks every supported entry in an already-opened, already
    size/count-validated ZipFile and ingests it exactly like a direct
    upload would be: per-job file_hash dedup, SAVEPOINT Resume insert. The
    caller (app/api/resumes.py) still owns enqueueing accepted resumes and
    the ScreeningBatch.total_resumes assignment, unchanged from today.

    `used_basenames` should be shared (same set instance) across every
    direct file AND every ZIP processed for one upload request when they
    all land under the same job_id/batch_id prefix - two different sources
    can otherwise sanitize to the same basename and silently overwrite each
    other on disk before either Resume row is inserted. Defaults to a
    fresh set for a standalone call.
    """
    result = ZipIngestResult()
    prefix = f"job_{job_id}/batch_{batch_id}"
    max_member_bytes = settings.MAX_RESUME_FILE_SIZE_MB * 1024 * 1024
    if used_basenames is None:
        used_basenames = set()

    for info in zf.infolist():
        if not _is_supported_entry(info):
            result.unsupported += 1
            continue

        # Cheap pre-filters before ever decompressing this entry. Declared
        # size can be spoofed by a crafted header, so this is only an
        # early-exit optimization - save_stream() below enforces the real
        # cap while actually streaming the bytes.
        #
        # A 0-byte entry can never parse as a PDF/DOCX (extraction always
        # fails downstream with a confusing mupdf/docx error), so reject it
        # here the same way the direct-upload path already rejects an empty
        # UploadFile (see bulk_upload_resumes' `file_size == 0` check).
        if info.file_size == 0:
            logger.info("zip_ingest: entry %s is empty (0 bytes); skipping.", info.filename)
            result.failed += 1
            continue
        if info.file_size > max_member_bytes:
            logger.info(
                "zip_ingest: entry %s declares %d bytes, over the per-file cap; skipping.",
                info.filename, info.file_size,
            )
            result.failed += 1
            continue
        if info.compress_size > 0 and info.file_size / info.compress_size > _MAX_COMPRESSION_RATIO:
            logger.warning(
                "zip_ingest: entry %s has a suspicious compression ratio (%.0fx); skipping.",
                info.filename, info.file_size / info.compress_size,
            )
            result.failed += 1
            continue

        basename = make_unique_basename(
            sanitize_filename(os.path.basename(info.filename.rstrip("/"))), used_basenames
        )

        try:
            with zf.open(info) as member_stream:
                storage_key, file_hash, _size = await storage_service.save_stream(
                    partial(member_stream.read, _READ_CHUNK_BYTES), basename, prefix, max_member_bytes,
                )
        except (zipfile.BadZipFile, RuntimeError, OSError, ValueError) as e:
            # save_stream() has already removed any partial file it wrote.
            logger.warning("zip_ingest: failed to extract entry %s: %s", info.filename, e)
            result.failed += 1
            continue

        # Duplicate check - identical semantics to the direct-upload path's
        # own (job_id, file_hash) pre-check + SAVEPOINT race guard.
        dup = await db.execute(select(Resume).where(Resume.job_id == job_id, Resume.file_hash == file_hash))
        if dup.scalar_one_or_none():
            result.duplicate += 1
            _delete_saved_file(storage_key)
            continue

        resume = Resume(batch_id=batch_id, job_id=job_id, filename=basename, file_hash=file_hash, storage_key=storage_key)
        try:
            async with db.begin_nested():
                db.add(resume)
                await db.flush()
        except IntegrityError:
            # Lost the race with a concurrent upload of the same file.
            result.duplicate += 1
            _delete_saved_file(storage_key)
            continue

        result.accepted += 1
        result.accepted_resume_ids.append(resume.id)

    return result
