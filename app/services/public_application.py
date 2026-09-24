"""Candidate-initiated application via a job's public apply link.

A submission joins the job's pool through the same path as a recruiter
upload: resume_intake -> Resume row -> process_resume queue message ->
orchestrator (extract -> local profile / LLM fallback -> identity ->
embed). It is NOT screened here - screening stays recruiter-triggered
("Screen Candidates"), gating each applicant against the job's full pool.

Queue reliability: enqueue_resume is a single XADD, and an exception from
it does not prove Redis never accepted the message - the connection can
drop (or the reply read can fail) after the server already appended the
entry. Committed rows are therefore never deleted on enqueue failure. Instead
PublicApplicationSubmission.enqueued_at records "enqueue confirmed" and
requeue_unenqueued_applications() - run periodically by the worker -
re-enqueues anything left unconfirmed. A duplicate process_resume message
is safe: process_candidate short-circuits on READY, takes a NOWAIT row lock
(a concurrent duplicate raises before touching status and is retried), and
resumes from its workflow_stage checkpoint.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.batch import ScreeningBatch
from app.models.job import Job
from app.models.public_application import PublicApplicationSubmission
from app.models.resume import Resume
from app.services import resume_intake
from app.services.queue import queue_service
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

APPLICATION_BATCH_TYPE = "APPLICATION"


async def submit_application(
    db: AsyncSession,
    *,
    job: Job,
    file: UploadFile,
    name: str,
    email: str,
    phone: Optional[str],
) -> Literal["received", "invalid"]:
    """Store one application and enqueue it for processing.

    "received" covers both a newly accepted file and a same-job duplicate
    (the caller returns the same generic response for both). "invalid" is
    a file-type/size rejection.
    """
    job_id = job.id
    batch = ScreeningBatch(job_id=job_id, batch_type=APPLICATION_BATCH_TYPE, total_resumes=1)
    db.add(batch)
    await db.flush()

    intake = await resume_intake.ingest_uploaded_file(
        db, file, job_id=job_id, batch_id=batch.id, used_basenames=set()
    )

    if intake.outcome != "accepted":
        # Nothing to keep: no Resume row was created, so drop the batch too.
        await db.rollback()
        if intake.orphaned_storage_key:
            # Lost a concurrent same-file race after writing to disk. No row
            # references this file and nothing was enqueued for it.
            storage_service.delete_file(intake.orphaned_storage_key)
        if intake.outcome == "duplicate":
            logger.info("Public application for job %s was a duplicate file; nothing stored.", job_id)
            return "received"
        return "invalid"

    resume = intake.resume
    submission = PublicApplicationSubmission(
        resume_id=resume.id,
        job_id=job_id,
        applicant_name=name,
        applicant_email=email,
        applicant_phone=phone,
        consent_at=datetime.now(timezone.utc),
    )
    db.add(submission)
    await db.commit()

    resume_id, batch_id = resume.id, batch.id
    logger.info("Public application stored: job=%s resume=%s batch=%s", job_id, resume_id, batch_id)

    try:
        await queue_service.enqueue_resume(resume_id, job_id=job_id, batch_id=batch_id)
    except Exception:
        logger.warning(
            "Enqueue not confirmed for public application resume=%s (job=%s); "
            "the recovery sweep will re-enqueue it.",
            resume_id, job_id, exc_info=True,
        )
        return "received"

    try:
        submission.enqueued_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception:
        # The message IS queued; the sweep may enqueue it once more, which
        # the pipeline tolerates (see module docstring).
        logger.warning(
            "Could not record enqueued_at for public application resume=%s; "
            "the recovery sweep may enqueue a harmless duplicate.",
            resume_id, exc_info=True,
        )
        await db.rollback()

    return "received"


async def requeue_unenqueued_applications(session: Optional[AsyncSession] = None) -> int:
    """Re-enqueue public applications whose enqueue was never confirmed.

    Only rows older than PUBLIC_APPLY_REQUEUE_MIN_AGE_SECONDS (so a request
    still between its commit and its XADD isn't raced), whose resume is
    still UPLOADED, on an ACTIVE job. A paused job's rows are left alone -
    resume_job re-enqueues its UPLOADED resumes when it's resumed. Rows are
    claimed FOR UPDATE SKIP LOCKED so concurrent worker processes never
    sweep the same row. Returns how many were re-enqueued.
    """
    if session is None:
        async with AsyncSessionLocal() as own_session:
            return await requeue_unenqueued_applications(own_session)

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.PUBLIC_APPLY_REQUEUE_MIN_AGE_SECONDS)
    rows = (
        await session.execute(
            select(PublicApplicationSubmission, Resume.batch_id)
            .join(Resume, Resume.id == PublicApplicationSubmission.resume_id)
            .join(Job, Job.id == PublicApplicationSubmission.job_id)
            .where(
                PublicApplicationSubmission.enqueued_at.is_(None),
                PublicApplicationSubmission.created_at < cutoff,
                Resume.status == "UPLOADED",
                Job.status == "ACTIVE",
            )
            .order_by(PublicApplicationSubmission.created_at)
            .limit(100)
            .with_for_update(skip_locked=True, of=PublicApplicationSubmission)
        )
    ).all()

    requeued = 0
    for submission, batch_id in rows:
        try:
            await queue_service.enqueue_resume(submission.resume_id, job_id=submission.job_id, batch_id=batch_id)
        except Exception:
            logger.warning(
                "Recovery sweep: enqueue still failing for public application resume=%s; will retry next pass.",
                submission.resume_id, exc_info=True,
            )
            continue
        submission.enqueued_at = datetime.now(timezone.utc)
        requeued += 1

    await session.commit()
    if requeued:
        logger.info("Recovery sweep: re-enqueued %d public application(s).", requeued)
    return requeued
