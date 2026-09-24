"""Shared "make sure every READY, not-yet-screened resume for this job gets
screened" trigger (Phase 4).

Used by the explicit "Screen Candidates" API action (app/api/jobs.py) and
by the orchestrator's automatic re-screen after a resume-version swap -
both cases reduce to the same thing, since screen_job's own per-(job,
resume) idempotency guard already skips anything already screened.
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume
from app.models.batch import ScreeningBatch
from app.services.queue import queue_service


async def enqueue_screen_job(db: AsyncSession, job_id: int) -> ScreeningBatch:
    ready_count_res = await db.execute(
        select(func.count(Resume.id)).where(Resume.job_id == job_id, Resume.status == "READY")
    )
    ready_count = ready_count_res.scalar_one()

    batch = ScreeningBatch(job_id=job_id, status="PROCESSING", total_resumes=ready_count, batch_type="SCREEN")
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    try:
        await queue_service.enqueue_task({
            "action": "screen_job",
            "job_id": job_id,
            "batch_id": batch.id,
        })
    except Exception:
        # Unlike a resume stuck in UPLOADED (which resume_job's re-enqueue
        # sweep can recover), nothing else ever revisits a ScreeningBatch -
        # if the enqueue itself fails (e.g. Redis briefly unreachable) after
        # the batch row already committed as PROCESSING, it would otherwise
        # stay stuck in PROCESSING forever with no task to ever complete it.
        # Marking it FAILED here surfaces that immediately instead.
        batch.status = "FAILED"
        await db.commit()
        raise

    return batch
