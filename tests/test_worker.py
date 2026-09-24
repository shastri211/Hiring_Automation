import asyncio
import logging

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.models.job import Job
from app.services.orchestrator import orchestrator
from app.worker import worker_loop, fail_task_permanently
from unittest.mock import patch, MagicMock, AsyncMock
from tenancy_fixtures import TEST_ORG_ID

@pytest.mark.asyncio
async def test_process_candidate_not_found():
    # Calling with invalid ID should just print and return
    await orchestrator.process_candidate(9999)


# -- unmatched action handling -------------------------------------------------
# Previously an action string with no matching elif branch fell straight
# through to `await queue_service.ack(msg_id)` with nothing logged - a
# structurally-unmatched task (never fixed by retrying) would silently
# vanish. It must now be logged loudly and still acked (retrying can't help
# a message no handler will ever match), not left to loop forever either.

@pytest.mark.asyncio
async def test_unknown_action_is_logged_and_acked_not_silently_dropped(caplog):
    call_count = {"n": 0}

    async def mock_consume(consumer_id, count, block_ms):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return [("msg-unknown-1", {"action": "totally_unknown_action", "job_id": "1"})]
        await asyncio.sleep(5)
        return []

    mock_ack = AsyncMock()

    with patch("app.worker.queue_service.consume", side_effect=mock_consume), \
         patch("app.worker.queue_service.should_retry", return_value=True), \
         patch("app.worker.queue_service.is_exhausted", return_value=False), \
         patch("app.worker.queue_service.ack", mock_ack), \
         patch("app.worker.queue_service.heartbeat", new_callable=AsyncMock), \
         caplog.at_level(logging.ERROR, logger="app.worker"):

        task = asyncio.create_task(worker_loop("test-worker-unknown-action"))
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    mock_ack.assert_awaited_once_with("msg-unknown-1")
    assert any(
        "Unknown action" in record.message and "totally_unknown_action" in record.message
        for record in caplog.records
    )


# -- fail_task_permanently: migrate_job ----------------------------------------

@pytest.mark.asyncio
async def test_fail_task_permanently_marks_job_embedding_status_failed(db_session):
    job = Job(organization_id=TEST_ORG_ID, title="Migration Failure Test", description="d", embedding_status="MIGRATING")
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    await fail_task_permanently("migrate_job", job.id, "boom")

    result = await db_session.execute(
        select(Job).where(Job.id == job.id).execution_options(populate_existing=True)
    )
    refreshed = result.scalar_one()
    assert refreshed.embedding_status == "FAILED"
