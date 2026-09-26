"""Single-file resume intake: validate, hash, store, and insert one Resume row.

Shared by recruiter bulk upload (app/api/resumes.py, for each direct -
non-ZIP - file) and the public candidate apply endpoint
(app/api/public_application.py), so both paths enforce the exact same
type/size rules and the same per-job (job_id, file_hash) dedup.

ingest_uploaded_file does not commit and does not enqueue - the caller owns
the transaction and the queue message, since the two callers differ there
(one batch commit for many files vs. one application per request).
requeue_unenqueued_uploads is the recovery sweep for recruiter uploads whose
enqueue was never confirmed (Resume.enqueued_at).
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import UploadFile
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.job import Job
from app.models.public_application import PublicApplicationSubmission
from app.models.resume import Resume
from app.services.queue import queue_service
from app.services.storage import storage_service, make_unique_basename, sanitize_filename

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_RESUME_FILE_SIZE_BYTES = settings.MAX_RESUME_FILE_SIZE_MB * 1024 * 1024


def is_allowed_resume_file(file: UploadFile) -> bool:
    """Belt-and-suspenders check: the client-supplied Content-Type header is
    trivially spoofable on its own, so also require a matching extension."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    return file.content_type in ALLOWED_CONTENT_TYPES and ext in ALLOWED_EXTENSIONS


@dataclass
class IntakeResult:
    outcome: Literal["accepted", "duplicate", "invalid"]
    resume: Optional[Resume] = None
    # Set when the file was written to storage but no Resume row references
    # it - i.e. this request lost the concurrent (job_id, file_hash) insert
    # race after saving. The caller decides whether to delete it.
    orphaned_storage_key: Optional[str] = None


async def ingest_uploaded_file(
    db: AsyncSession,
    file: UploadFile,
    *,
    job_id: int,
    batch_id: int,
    used_basenames: set,
) -> IntakeResult:
    if not is_allowed_resume_file(file):
        return IntakeResult("invalid")

    # Enforce a per-file size cap without buffering the whole file in memory:
    # peek the size via the underlying spooled file, then rewind for
    # hashing/saving. UploadFile.seek() itself has no `whence` param, so
    # this goes through the sync file object it wraps.
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    await file.seek(0)
    if file_size == 0 or file_size > MAX_RESUME_FILE_SIZE_BYTES:
        return IntakeResult("invalid")

    file_hash = await storage_service.compute_hash(file)

    # Check duplicate (app-level pre-check; the DB unique constraint on
    # (job_id, file_hash) is the authoritative guard against the
    # concurrent-upload race this alone can't close).
    dup_result = await db.execute(
        select(Resume).where(Resume.job_id == job_id, Resume.file_hash == file_hash)
    )
    if dup_result.scalar_one_or_none():
        return IntakeResult("duplicate")

    # Store file
    prefix = f"job_{job_id}/batch_{batch_id}"
    basename = make_unique_basename(sanitize_filename(file.filename), used_basenames)
    storage_key = await storage_service.save_file(file, prefix, filename_override=basename)

    # Save metadata. Flushed inside a SAVEPOINT so that losing the
    # duplicate-hash race on this one file only undoes this insert -
    # not other resumes the caller already flushed in the same
    # transaction (bulk upload commits the whole batch together at the end).
    resume = Resume(
        batch_id=batch_id,
        job_id=job_id,
        filename=file.filename,
        file_hash=file_hash,
        storage_key=storage_key,
    )
    try:
        async with db.begin_nested():
            db.add(resume)
            await db.flush()  # flush to get resume.id
    except IntegrityError:
        # Lost the race with a concurrent upload of the same file.
        return IntakeResult("duplicate", orphaned_storage_key=storage_key)
    return IntakeResult("accepted", resume=resume)


async def requeue_unenqueued_uploads(session: Optional[AsyncSession] = None) -> int:
    """Re-enqueue recruiter-uploaded resumes whose enqueue was never
    confirmed (Resume.enqueued_at is NULL) - e.g. Redis was unreachable
    during the upload request. Mirrors
    public_application.requeue_unenqueued_applications: only rows older than
    UPLOAD_REQUEUE_MIN_AGE_SECONDS, still UPLOADED, on an ACTIVE job, claimed
    FOR UPDATE SKIP LOCKED. Public applications are left to their own sweep.
    A duplicate message is safe (see public_application's module docstring).
    Returns how many were re-enqueued.
    """
    if session is None:
        async with AsyncSessionLocal() as own_session:
            return await requeue_unenqueued_uploads(own_session)

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.UPLOAD_REQUEUE_MIN_AGE_SECONDS)
    resumes = (
        await session.execute(
            select(Resume)
            .join(Job, Job.id == Resume.job_id)
            .where(
                Resume.enqueued_at.is_(None),
                Resume.created_at < cutoff,
                Resume.status == "UPLOADED",
                Job.status == "ACTIVE",
                ~exists().where(PublicApplicationSubmission.resume_id == Resume.id),
            )
            .order_by(Resume.created_at)
            .limit(100)
            .with_for_update(skip_locked=True, of=Resume)
        )
    ).scalars().all()

    results = await asyncio.gather(
        *(queue_service.enqueue_resume(r.id, job_id=r.job_id, batch_id=r.batch_id) for r in resumes),
        return_exceptions=True,
    )

    requeued = 0
    for resume, result in zip(resumes, results):
        if isinstance(result, BaseException):
            logger.warning(
                "Recovery sweep: enqueue still failing for uploaded resume=%s; will retry next pass.",
                resume.id, exc_info=result,
            )
            continue
        resume.enqueued_at = datetime.now(timezone.utc)
        requeued += 1

    await session.commit()
    if requeued:
        logger.info("Recovery sweep: re-enqueued %d uploaded resume(s).", requeued)
    return requeued
