import time
import logging
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from fastapi import status

from app.core.config import settings
from app.core.errors import CleanDeskException, ErrorCode

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    Redis-backed Sliding-Window rate limiter using atomic Sorted Sets (ZSET).
    Tracks failed login attempts per (IP, Email) identifier.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.max_attempts = settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS
        self.window_seconds = settings.AUTH_RATE_LIMIT_WINDOW_SECONDS

    def _get_key(self, identifier: str) -> str:
        return f"ratelimit:login:{identifier}"

    async def check_rate_limit(self, identifier: str) -> None:
        """
        Check if attempts exceed threshold in the sliding window.
        Raises CleanDeskException(429, RATE_LIMIT_EXCEEDED) if exceeded.
        """
        key = self._get_key(identifier)
        now = time.time()
        window_start = now - self.window_seconds

        try:
            # Atomic pipeline: remove old entries and count current entries
            pipe = self.redis.pipeline(transaction=True)
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = await pipe.execute()

            current_attempts = results[1]
            if current_attempts >= self.max_attempts:
                logger.warning(f"Rate limit exceeded for {identifier}: {current_attempts} failed attempts.")
                raise CleanDeskException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
                    message="Too many failed login attempts. Please try again after 60 seconds.",
                    details={
                        "max_attempts": self.max_attempts,
                        "window_seconds": self.window_seconds,
                    }
                )
        except CleanDeskException:
            raise
        except (RedisError, Exception) as exc:
            # Graceful degradation: don't block users if Redis is temporarily down
            logger.warning(f"[RateLimiter Degradation] Redis check failed: {exc}. Permitting request.")

    async def record_failed_attempt(self, identifier: str) -> None:
        """Record a failed login timestamp into the sorted set with TTL."""
        key = self._get_key(identifier)
        now = time.time()

        try:
            pipe = self.redis.pipeline(transaction=True)
            # Add current attempt with timestamp as score and member
            pipe.zadd(key, {f"{now}": now})
            # Expire set after the window duration to prevent key accumulation
            pipe.expire(key, self.window_seconds + 5)
            await pipe.execute()
        except (RedisError, Exception) as exc:
            logger.warning(f"[RateLimiter Degradation] Failed to record attempt: {exc}.")

    async def reset_attempts(self, identifier: str) -> None:
        """Clear recorded attempts on successful authentication."""
        key = self._get_key(identifier)
        try:
            await self.redis.delete(key)
        except (RedisError, Exception) as exc:
            logger.warning(f"[RateLimiter Degradation] Failed to reset attempts: {exc}.")