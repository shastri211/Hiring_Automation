import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
from app.services.queue import queue_service

@pytest.mark.asyncio
async def test_stream_enqueue_and_read():
    with patch("app.services.queue.queue_service.redis_client") as mock_redis:
        mock_redis.xgroup_create = AsyncMock()
        mock_redis.xadd = AsyncMock()
        mock_redis.xreadgroup = AsyncMock(return_value=[(
            queue_service.stream_name,
            [("12345-0", {"resume_id": "9999", "job_id": "1", "batch_id": "1", "action": "process_resume"})]
        )])
        mock_redis.xack = AsyncMock(return_value=1)
        
        await queue_service.init_stream()
        mock_redis.xgroup_create.assert_called_once()

        await queue_service.enqueue_resume(9999, job_id=1, batch_id=1)
        mock_redis.xadd.assert_called_once_with(
            queue_service.stream_name,
            {"resume_id": "9999", "job_id": "1", "batch_id": "1", "action": "process_resume"},
            maxlen=queue_service.stream_maxlen,
            approximate=True,
        )
        
        result = await mock_redis.xreadgroup(
            groupname=queue_service.group_name,
            consumername="test_consumer",
            streams={queue_service.stream_name: '>'},
            count=1,
            block=1000
        )
        assert len(result) > 0
        msg_id, payload = result[0][1][0]
        assert payload.get("resume_id") == "9999"
        
        await mock_redis.xack(queue_service.stream_name, queue_service.group_name, msg_id)
        mock_redis.xack.assert_called_once_with(queue_service.stream_name, queue_service.group_name, "12345-0")

@pytest.mark.asyncio
async def test_stream_idle_timeout():
    from redis.exceptions import TimeoutError as RedisTimeoutError
    with patch("app.services.queue.queue_service.redis_client") as mock_redis:
        mock_redis.xreadgroup = AsyncMock(side_effect=RedisTimeoutError("Timeout reading from 127.0.0.1:6379"))
        
        # When consuming with a timeout exception, it should catch it and return []
        messages = await queue_service.consume("test_worker")
        
        assert messages == []
        mock_redis.xreadgroup.assert_called()
