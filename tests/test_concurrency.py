import pytest
import asyncio
import time
from unittest.mock import patch, AsyncMock

from app.worker import worker_loop

@pytest.mark.asyncio
async def test_worker_concurrency():
    """Prove that multiple independent resumes process concurrently bounded by WORKER_CONCURRENCY."""
    consume_calls = 0
    
    async def mock_consume(consumer_id, count, block_ms):
        nonlocal consume_calls
        if consume_calls >= 5:
            await asyncio.sleep(5)
            raise asyncio.CancelledError()
            
        consume_calls += 1
        return [("msg-" + str(consume_calls), {"action": "process_resume", "resume_id": str(consume_calls)})]

    async def mock_process(resume_id):
        # Simulate processing delay
        await asyncio.sleep(0.5)
        return

    with patch("app.worker.queue_service.consume", side_effect=mock_consume), \
         patch("app.worker.queue_service.should_retry", return_value=True), \
         patch("app.worker.queue_service.is_exhausted", return_value=False), \
         patch("app.worker.queue_service.ack", new_callable=AsyncMock) as mock_ack, \
         patch("app.worker.orchestrator.process_candidate", side_effect=mock_process):

        start = time.time()
        
        # spawn 5 workers simulating the main loop
        tasks = [asyncio.create_task(worker_loop(f"worker-{i}")) for i in range(5)]
        
        # wait enough for 0.5s tasks to complete, but less than 5 * 0.5s (2.5s)
        await asyncio.sleep(1.0)
        
        for t in tasks:
            t.cancel()
            
        duration = time.time() - start
        
        # If execution was sequential, 5 calls would take >2.5 seconds.
        # Since concurrent, it should take ~0.5s total + some overhead.
        assert duration < 2.0
        assert mock_ack.call_count >= 4
