import hashlib

import pytest
from app.services.orchestrator import RecruitmentOrchestrator, update_batch_progress

@pytest.mark.asyncio
async def test_orchestrator_initialization():
    orchestrator = RecruitmentOrchestrator()
    assert hasattr(orchestrator, "process_candidate")


@pytest.mark.asyncio
async def test_update_batch_progress_counts_failed_resumes(db_session):
    """A resume that permanently fails must be reflected in batch.failed
    immediately, not only once some other resume in the batch succeeds -
    previously the failure path never touched the batch counters at all."""
    from app.models.job import Job
    from app.models.batch import ScreeningBatch
    from app.models.resume import Resume

    job = Job(title="Batch Progress Job", description="x", job_profile={"title": "x"})
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    batch = ScreeningBatch(job_id=job.id, total_resumes=2)
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)

    ready = Resume(
        batch_id=batch.id, job_id=job.id, filename="ok.pdf",
        file_hash=hashlib.sha256(b"ok").hexdigest(), storage_key="x", status="READY",
    )
    failed = Resume(
        batch_id=batch.id, job_id=job.id, filename="bad.pdf",
        file_hash=hashlib.sha256(b"bad").hexdigest(), storage_key="y", status="FAILED",
    )
    db_session.add_all([ready, failed])
    await db_session.commit()

    await update_batch_progress(db_session, batch.id)

    await db_session.refresh(batch)
    assert batch.processed == 1
    assert batch.failed == 1
    assert batch.status == "COMPLETED"


@pytest.mark.asyncio
async def test_update_batch_progress_allow_complete_false_keeps_status(db_session):
    """A resume's per-attempt (possibly still-retrying) failure must update
    the visible counters but never mark the batch COMPLETED - only a truly
    terminal outcome (success, or retries exhausted) may do that."""
    from app.models.job import Job
    from app.models.batch import ScreeningBatch
    from app.models.resume import Resume

    job = Job(title="Batch Progress Job 2", description="x", job_profile={"title": "x"})
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    batch = ScreeningBatch(job_id=job.id, total_resumes=1, status="PROCESSING")
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)

    failed = Resume(
        batch_id=batch.id, job_id=job.id, filename="retrying.pdf",
        file_hash=hashlib.sha256(b"retrying").hexdigest(), storage_key="z", status="FAILED",
    )
    db_session.add(failed)
    await db_session.commit()

    await update_batch_progress(db_session, batch.id, allow_complete=False)

    await db_session.refresh(batch)
    assert batch.failed == 1
    assert batch.status == "PROCESSING"
