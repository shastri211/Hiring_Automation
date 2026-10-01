"""Fixed-window request rate limiting on the existing Redis connection.

Inbound (client -> us) limiting for public, unauthenticated endpoints -
unrelated to the outbound provider RateLimitError handling in
llm_provider.py/embeddings.py. Reuses queue_service's Redis client rather
than adding a dependency; Redis is already required for the worker queue.
"""
import hashlib
import logging
import time
from typing import Tuple

from fastapi import HTTPException

from app.services.queue import queue_service

logger = logging.getLogger(__name__)

HOUR_SECONDS = 3600


class RateLimiterUnavailable(Exception):
    """Redis couldn't be reached. Callers fail closed (503) rather than
    silently letting unlimited public traffic through."""


def hash_client_ip(ip: str) -> str:
    """Raw IPs are never written to Redis keys - a short one-way hash is
    enough to bucket requests."""
    return hashlib.sha256((ip or "unknown").encode()).hexdigest()[:16]


def hash_identifier(value: str) -> str:
    """Same idea for other personal identifiers used as limiter keys (e.g. a
    normalized email) - the raw value never appears in Redis."""
    return hashlib.sha256((value or "").encode()).hexdigest()[:16]


def _window(key: str, window_seconds: int) -> Tuple[str, int]:
    """(Redis key for the current fixed window, seconds until it ends)."""
    now = int(time.time())
    window = now // window_seconds
    return f"ratelimit:{key}:{window}", max((window + 1) * window_seconds - now, 1)


async def check(key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
    """Count one hit against `key` in the current fixed window.

    Returns (allowed, retry_after_seconds). The hit is counted even when
    over the limit, so hammering doesn't reset anything.
    """
    redis_key, retry_after = _window(key, window_seconds)
    try:
        pipe = queue_service.redis_client.pipeline(transaction=True)
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds + 60)
        count, _ = await pipe.execute()
    except Exception as e:
        raise RateLimiterUnavailable(str(e)) from e
    return int(count) <= limit, retry_after


# Counting only some requests (e.g. failed logins) instead of every one:
# peek before acting, hit when the counted outcome happens, clear on success.

async def peek(key: str, window_seconds: int) -> Tuple[int, int]:
    """(hits so far in the current window, retry_after_seconds), without
    counting a new hit."""
    redis_key, retry_after = _window(key, window_seconds)
    try:
        count = await queue_service.redis_client.get(redis_key)
    except Exception as e:
        raise RateLimiterUnavailable(str(e)) from e
    return int(count or 0), retry_after


async def hit(key: str, window_seconds: int) -> None:
    redis_key, _ = _window(key, window_seconds)
    try:
        pipe = queue_service.redis_client.pipeline(transaction=True)
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds + 60)
        await pipe.execute()
    except Exception as e:
        raise RateLimiterUnavailable(str(e)) from e


async def clear(key: str, window_seconds: int) -> None:
    redis_key, _ = _window(key, window_seconds)
    try:
        await queue_service.redis_client.delete(redis_key)
    except Exception as e:
        raise RateLimiterUnavailable(str(e)) from e


async def enforce(key: str, limit: int, window_seconds: int = HOUR_SECONDS) -> None:
    """check(), translated into the HTTP responses every public/auth caller
    uses: 429 + Retry-After when over the limit, 503 when Redis is down
    (fail closed)."""
    try:
        allowed, retry_after = await check(key, limit, window_seconds)
    except RateLimiterUnavailable:
        logger.error("Rate limiter unavailable (Redis unreachable); failing closed.")
        raise HTTPException(status_code=503, detail={"reason": "temporarily_unavailable"})
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"reason": "rate_limited"},
            headers={"Retry-After": str(retry_after)},
        )
