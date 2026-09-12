import pytest
import asyncio
import time
import uuid
import json
from app.services.queue import QueueService
from app.core.config import settings
import redis.asyncio as redis

@pytest.fixture
async def redis_client():
    client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    yield client
    await client.close()

@pytest.fixture
async def test_queue(redis_client):
    # Use a unique stream name for testing to avoid conflicts
    unique_id = str(uuid.uuid4())
    queue = QueueService()
    queue.stream_name = f"test_stream_{unique_id}"
    queue.group_name = f"test_group_{unique_id}"
    queue.retry_hash = f"test_retries_{unique_id}"
    queue.max_retries = 3
    queue.base_backoff_sec = 1
    
    await queue.init_stream()
    yield queue
    
    # Cleanup
    await redis_client.delete(queue.stream_name)
    await redis_client.delete(queue.retry_hash)

@pytest.mark.asyncio
async def test_enqueue_and_consume(test_queue):
    worker_id = "test_worker_1"
    
    # Enqueue a resume
    await test_queue.enqueue_resume(101, job_id=1, batch_id=1)
    
    # Consume it
    messages = await test_queue.consume(worker_id, count=1, block_ms=1000)
    assert len(messages) == 1
    
    msg_id, payload = messages[0]
    assert payload["resume_id"] == "101"
    assert payload["action"] == "process_resume"
    
    # Ack it
    await test_queue.ack(msg_id)
    
    # Check it's not pending anymore
    pending = await test_queue.redis_client.xpending(test_queue.stream_name, test_queue.group_name)
    assert pending["pending"] == 0

@pytest.mark.asyncio
async def test_retry_and_exponential_backoff(test_queue):
    worker_id = "test_worker_2"
    
    await test_queue.enqueue_resume(102, job_id=1, batch_id=1)
    messages = await test_queue.consume(worker_id, count=1, block_ms=1000)
    msg_id, _ = messages[0]
    
    # Initially allowed
    assert await test_queue.should_retry(msg_id) is True
    
    # Record failure (attempt 1, backoff = 1 * 2^0 = 1 sec)
    attempt = await test_queue.record_failure(msg_id)
    assert attempt == 1
    
    # should_retry should be False immediately after failure
    assert await test_queue.should_retry(msg_id) is False
    
    # Wait for backoff to expire
    await asyncio.sleep(1.1)
    
    # should_retry should be True now
    assert await test_queue.should_retry(msg_id) is True
    
    # Record failure again (attempt 2, backoff = 1 * 2^1 = 2 sec)
    attempt = await test_queue.record_failure(msg_id)
    assert attempt == 2
    
    # should_retry should be False again
    assert await test_queue.should_retry(msg_id) is False
    
    # Wait 2.1 secs
    await asyncio.sleep(2.1)
    assert await test_queue.should_retry(msg_id) is True

@pytest.mark.asyncio
async def test_retry_exhaustion(test_queue):
    worker_id = "test_worker_3"
    
    await test_queue.enqueue_resume(103, job_id=1, batch_id=1)
    messages = await test_queue.consume(worker_id, count=1, block_ms=1000)
    msg_id, _ = messages[0]
    
    # Fail max_retries times
    for i in range(test_queue.max_retries):
        await test_queue.record_failure(msg_id)
        
    assert await test_queue.is_exhausted(msg_id) is True
    assert await test_queue.should_retry(msg_id) is False

@pytest.mark.asyncio
async def test_claim_stuck_messages(test_queue):
    worker_1 = "test_worker_4_a"
    worker_2 = "test_worker_4_b"
    
    await test_queue.enqueue_resume(104, job_id=1, batch_id=1)
    
    # Worker 1 consumes but crashes (no ack)
    messages = await test_queue.consume(worker_1, count=1, block_ms=1000)
    assert len(messages) == 1
    
    # Worker 2 tries to claim stuck messages. We set min_idle_ms very low for the test
    await asyncio.sleep(1) # Let it idle for a second
    claimed = await test_queue.claim_stuck_messages(worker_2, min_idle_ms=500)
    
    assert len(claimed) == 1
    c_msg_id, payload = claimed[0]
    assert payload["resume_id"] == "104"
    
    # Ack by worker 2
    await test_queue.ack(c_msg_id)
    
    # Verify no pending messages
    pending = await test_queue.redis_client.xpending(test_queue.stream_name, test_queue.group_name)
    assert pending["pending"] == 0

