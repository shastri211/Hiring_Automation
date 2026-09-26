import os
import logging
import zipfile
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.config import settings
from app.db.session import get_db
from app.models.batch import ScreeningBatch
from app.models.resume import Resume
from app.schemas.resume import UploadResponse
from app.services.storage import storage_service
from app.services.queue import queue_service
from app.services import zip_ingest, resume_intake, tenancy
from app.api.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

# Re-exported for existing importers (app/api/jobs.py's JD upload check).
from app.services.resume_intake import ALLOWED_CONTENT_TYPES, ALLOWED_EXTENSIONS, MAX_RESUME_FILE_SIZE_BYTES  # noqa: F401

ZIP_EXTENSION = ".zip"
MAX_ZIP_FILE_SIZE_BYTES = int(settings.max_zip_file_size_mb * 1024 * 1024)


def _is_zip_file(file: UploadFile) -> bool:
    """Extension only, not Content-Type: browsers/OSes are inconsistent
    about the MIME type they send for ZIP files (application/zip,
    application/x-zip-compressed, or a generic application/octet-stream
    are all common). zipfile.is_zipfile() is the authoritative check,
    applied right before opening (see bulk_upload_resumes)."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    return ext == ZIP_EXTENSION


def _peek_file_size(file: UploadFile) -> int:
    """Real byte size via the underlying spooled file, without buffering
    the whole upload into application memory - same trick already used for
    the per-resume-file size check below."""
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    return size


@router.post("/upload/{job_id}", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def bulk_upload_resumes(
    job_id: int,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # The job must exist within the caller's organization.
    await tenancy.get_job_for_org_or_404(db, job_id, current_user.organization_id)

    if len(files) > settings.MAX_RESUMES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files in one upload (max {settings.MAX_RESUMES_PER_UPLOAD}). Split into smaller batches.",
        )

    # Phase 5: a single ZIP file counts as "1" in len(files) above but can
    # smuggle in far more than MAX_RESUMES_PER_UPLOAD resumes - compute the
    # real combined total (direct files + every ZIP's supported entries)
    # before extracting anything, and reject the whole request up front if
    # it's over the cap, matching the all-or-nothing style above rather
    # than accepting some and silently dropping the rest. A ZIP that's
    # oversized or not actually a valid archive just contributes 0 here -
    # it's reported as invalid in the main loop below either way.
    effective_total = 0
    for file in files:
        if _is_zip_file(file):
            if _peek_file_size(file) > MAX_ZIP_FILE_SIZE_BYTES:
                continue
            try:
                with zipfile.ZipFile(file.file) as zf:
                    effective_total += zip_ingest.count_supported_entries(zf)
            except zipfile.BadZipFile:
                continue
            finally:
                file.file.seek(0)
        else:
            effective_total += 1

    if effective_total > settings.MAX_RESUMES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many files/entries in one upload (max {settings.MAX_RESUMES_PER_UPLOAD} across "
                f"direct files and ZIP contents combined). Split into smaller batches."
            ),
        )

    # Create ScreeningBatch
    batch = ScreeningBatch(job_id=job_id, batch_type="UPLOAD")
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    accepted_files = 0
    duplicate_files = 0
    invalid_files = 0
    failed_files = 0
    added_resumes = []
    # Shared across every direct file AND every ZIP below - they all land
    # under the same job_id/batch_id storage prefix, so two different
    # sources sanitizing to the same basename (e.g. two files both named
    # "resume.pdf") would otherwise silently overwrite each other on disk.
    used_basenames: set = set()

    # Process files
    for file in files:
        if _is_zip_file(file):
            if _peek_file_size(file) == 0 or _peek_file_size(file) > MAX_ZIP_FILE_SIZE_BYTES:
                invalid_files += 1
                continue
            if not zipfile.is_zipfile(file.file):
                file.file.seek(0)
                invalid_files += 1
                continue
            file.file.seek(0)
            try:
                with zipfile.ZipFile(file.file) as zf:
                    zip_result = await zip_ingest.extract_zip_into_batch(
                        db, zf, job_id=job_id, batch_id=batch.id, used_basenames=used_basenames
                    )
            except zipfile.BadZipFile:
                invalid_files += 1
                continue

            accepted_files += zip_result.accepted
            duplicate_files += zip_result.duplicate
            invalid_files += zip_result.unsupported
            failed_files += zip_result.failed
            added_resumes.extend(zip_result.accepted_resume_ids)
            continue

        intake = await resume_intake.ingest_uploaded_file(
            db, file, job_id=job_id, batch_id=batch.id, used_basenames=used_basenames
        )
        if intake.outcome == "invalid":
            invalid_files += 1
            continue
        if intake.outcome == "duplicate":
            duplicate_files += 1
            continue
        added_resumes.append(intake.resume.id)
        accepted_files += 1

    batch.total_resumes = accepted_files
    if accepted_files == 0:
        # Nothing to process (all duplicates/invalid) - otherwise the batch
        # would stay "live" forever, since no resume ever completes it.
        batch.status = "COMPLETED"
    await db.commit()

    # A failed enqueue must not fail the request - the resumes are already
    # committed. Only confirmed enqueues get enqueued_at; the worker's
    # recovery sweep (resume_intake.requeue_unenqueued_uploads) re-enqueues
    # the rest.
    enqueued_ids = []
    for r_id in added_resumes:
        try:
            await queue_service.enqueue_resume(r_id, job_id=job_id, batch_id=batch.id)
            enqueued_ids.append(r_id)
        except Exception:
            logger.warning(
                "Enqueue not confirmed for uploaded resume=%s (job=%s); the recovery sweep will re-enqueue it.",
                r_id, job_id, exc_info=True,
            )
    if enqueued_ids:
        try:
            await db.execute(
                update(Resume).where(Resume.id.in_(enqueued_ids)).values(enqueued_at=datetime.now(timezone.utc))
            )
            await db.commit()
        except Exception:
            # The messages ARE queued; the sweep may enqueue harmless duplicates.
            logger.warning("Could not record enqueued_at for batch %s.", batch.id, exc_info=True)
            await db.rollback()

    return UploadResponse(
        message="Upload received and batch created",
        batch_id=batch.id,
        job_id=job_id,
        accepted_files=accepted_files,
        duplicate_files=duplicate_files,
        invalid_files=invalid_files,
        failed_files=failed_files,
    )

from fastapi.responses import FileResponse

@router.get("/file/{resume_id}")
async def get_resume_file(
    resume_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    resume = await tenancy.get_resume_in_org_or_404(db, resume_id, current_user.organization_id)
        
    file_path = storage_service.get_secure_path(resume.storage_key)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    return FileResponse(
        path=file_path,
        filename=resume.filename,
        media_type="application/octet-stream"
    )
