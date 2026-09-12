import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import app.worker
from app.services.orchestrator import orchestrator
from app.models.resume import Resume
from app.models.job import Job

@pytest.mark.asyncio
@patch("app.services.orchestrator.AsyncSessionLocal", new_callable=MagicMock)
async def test_orphaned_resume(mock_session_maker):
    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session
    
    # Mock resume finding
    mock_resume = Resume(id=1, job_id=999, status="UPLOADED", workflow_stage="UPLOADED")
    
    # When fetching resume, return mock_resume
    # When fetching job, return None
    class MockResult:
        def __init__(self, obj):
            self.obj = obj
        def scalar_one_or_none(self):
            return self.obj

    mock_session.execute.side_effect = [
        MockResult(mock_resume), # Resume fetch
        MockResult(None) # Job fetch
    ]

    await orchestrator.process_candidate(1)

    assert mock_resume.status == "FAILED"
    assert "Permanent Failure" in mock_resume.error_message
    mock_session.commit.assert_called()

@pytest.mark.asyncio
@patch("app.worker.logger.exception")
@patch("app.worker.queue_service.should_retry", new_callable=AsyncMock)
@patch("app.worker.queue_service.record_failure", new_callable=AsyncMock)
@patch("app.worker.queue_service.consume", new_callable=AsyncMock)
@patch("app.worker.orchestrator.process_candidate", new_callable=AsyncMock)
async def test_worker_transient_retry(mock_process, mock_consume, mock_record, mock_should_retry, mock_logger_exc):
    import asyncio
    from app.worker import worker_loop
    
    mock_should_retry.return_value = True
    
    mock_consume.side_effect = [
        [("msg-2", {"action": "process_resume", "resume_id": 2})],
        asyncio.CancelledError()
    ]
    
    # Simulate a transient failure (e.g., API timeout)
    mock_process.side_effect = Exception("Transient LLM error")
    mock_record.return_value = 1

    try:
        await worker_loop("test-consumer")
    except asyncio.CancelledError:
        pass
        
    # Verify that record_failure was called to increment retry count
    mock_record.assert_called_with("msg-2")
    mock_logger_exc.assert_called()
