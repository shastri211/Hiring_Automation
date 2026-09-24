"""Fixed-window request rate limiting on the existing Redis connection.

Inbound (client -> us) limiting for public, unauthenticated endpoints -
unrelated to the outbound provider RateLimitError handling in
llm_provider.py/embeddings.py. Reuses queue_service's Redis client rather
than adding a dependency; Redis is already required for the worker queue.
"""
import hashlib
import time
from typing import Tuple

from app.services.queue import queue_service


class RateLimiterUnavailable(Exception):
    """Redis couldn't be reached. Callers fail closed (503) rather than
    silently letting unlimited public traffic through."""


def hash_client_ip(ip: str) -> str:
    """Raw IPs are never written to Redis keys - a short one-way hash is
    enough to bucket requests."""
    return hashlib.sha256((ip or "unknown").encode()).hexdigest()[:16]


async def check(key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
    """Count one hit against `key` in the current fixed window.

    Returns (allowed, retry_after_seconds). The hit is counted even when
    over the limit, so hammering doesn't reset anything.
    """
    now = int(time.time())
    window = now // window_seconds
    redis_key = f"ratelimit:{key}:{window}"
    retry_after = (window + 1) * window_seconds - now
    try:
        pipe = queue_service.redis_client.pipeline(transaction=True)
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds + 60)
        count, _ = await pipe.execute()
    except Exception as e:
        raise RateLimiterUnavailable(str(e)) from e
    return int(count) <= limit, max(retry_after, 1)
