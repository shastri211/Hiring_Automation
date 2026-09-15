import redis.asyncio as redis
from redis.exceptions import ResponseError
from app.core.config import settings
import json
import time

class QueueService:
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.stream_name = "screening_jobs_stream"
        self.group_name = settings.WORKER_CONSUMER_GROUP
        self.retry_hash = "screening_jobs_retries"
        self.max_retries = settings.WORKER_MAX_RETRIES
        self.base_backoff_sec = settings.WORKER_RETRY_BACKOFF_SECONDS
        # Acked entries aren't removed from a Redis stream on their own (only
        # from the consumer group's pending list) - without a cap the stream
        # grows forever. Approximate trimming (~) is O(1)-ish and doesn't
        # require exact accounting; comfortably larger than any realistic
        # backlog so it never trims anything still pending.
        self.stream_maxlen = 100_000

    async def init_stream(self):
        try:
            await self.redis_client.xgroup_create(self.stream_name, self.group_name, id='0', mkstream=True)
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise e

    async def enqueue_task(self, payload: dict):
        redis = self.redis_client
        str_payload = {k: str(v) for k, v in payload.items()}
        await redis.xadd(self.stream_name, str_payload, maxlen=self.stream_maxlen, approximate=True)

    async def enqueue_resume(self, resume_id: int, job_id: int, batch_id: int):
        payload = {
            "resume_id": str(resume_id),
            "job_id": str(job_id),
            "batch_id": str(batch_id),
            "action": "process_resume"
        }
        await self.redis_client.xadd(self.stream_name, payload, maxlen=self.stream_maxlen, approximate=True)

    async def consume(self, worker_id: str, count: int = 1, block_ms: int = 5000):
        """Block for new messages first, then redeliver this consumer's own
        pending backlog (e.g. after a restart) if there's nothing new.

        Checking '0' (already-delivered-to-this-consumer, unacked) first
        would starve new work: a message still in retry backoff stays
        pending until should_retry() allows another attempt, so '0' keeps
        returning that same message on every call and '>' - where new work
        arrives - is never reached. New work takes priority; stuck pending
        messages from a *different* dead consumer are separately reclaimed
        by recover_stuck_messages().
        """
        from redis.exceptions import TimeoutError as RedisTimeoutError
        import asyncio
        try:
            result = await self.redis_client.xreadgroup(
                groupname=self.group_name,
                consumername=worker_id,
                streams={self.stream_name: '>'},
                count=count,
                block=block_ms
            )

            if not result or not result[0][1]:
                result = await self.redis_client.xreadgroup(
                    groupname=self.group_name,
                    consumername=worker_id,
                    streams={self.stream_name: '0'},
                    count=count
                )

            if result and result[0][1]:
                stream_name, messages = result[0]
                return messages
            return []
        except (RedisTimeoutError, asyncio.TimeoutError):
            return []
        
    async def ack(self, msg_id: str):
        """Acknowledge message and clear its retry metadata."""
        await self.redis_client.xack(self.stream_name, self.group_name, msg_id)
        await self.clear_retry_metadata(msg_id)

    async def claim_stuck_messages(self, worker_id: str, min_idle_ms: int = 300000):
        """Scan for stuck messages and claim them."""
        pending = await self.redis_client.xpending_range(
            name=self.stream_name,
            groupname=self.group_name,
            min='-',
            max='+',
            count=100,
            idle=min_idle_ms
        )
        
        claimed_messages = []
        for msg_info in pending:
            msg_id = msg_info['message_id']
            claimed = await self.redis_client.xclaim(
                name=self.stream_name,
                groupname=self.group_name,
                consumername=worker_id,
                min_idle_time=min_idle_ms,
                message_ids=[msg_id]
            )
            claimed_messages.extend(claimed)
        return claimed_messages
        
    async def get_retry_metadata(self, msg_id: str) -> dict:
        data = await self.redis_client.hget(self.retry_hash, msg_id)
        if data:
            return json.loads(data)
        return {"attempt": 0, "next_retry_at": 0}
        
    async def should_retry(self, msg_id: str) -> bool:
        """Check if message is allowed to be retried right now."""
        meta = await self.get_retry_metadata(msg_id)
        if meta["attempt"] >= self.max_retries:
            return False
        return time.time() >= meta["next_retry_at"]

    async def is_exhausted(self, msg_id: str) -> bool:
        meta = await self.get_retry_metadata(msg_id)
        return meta["attempt"] >= self.max_retries

    async def record_failure(self, msg_id: str) -> int:
        """Increments attempt count, sets exponential backoff, returns new attempt count."""
        meta = await self.get_retry_metadata(msg_id)
        attempt = meta["attempt"] + 1
        
        # Exponential backoff: base * 2^(attempt-1)
        backoff = self.base_backoff_sec * (2 ** (attempt - 1))
        next_retry_at = time.time() + backoff
        
        new_meta = {"attempt": attempt, "next_retry_at": next_retry_at}
        await self.redis_client.hset(self.retry_hash, msg_id, json.dumps(new_meta))
        return attempt

    async def clear_retry_metadata(self, msg_id: str):
        await self.redis_client.hdel(self.retry_hash, msg_id)

queue_service = QueueService()
