import json
import logging
from typing import Any, Optional
import redis.asyncio as aioredis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis Cache-Aside service featuring:
    1. Tenant-scoped key naming (merchant:{merchant_id}:...)
    2. Explicit invalidation helpers
    3. Graceful degradation: never throws 500 if Redis connection fails.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    @staticmethod
    def dashboard_key(merchant_id: int) -> str:
        return f"merchant:{merchant_id}:dashboard:metrics"

    @staticmethod
    def products_key(merchant_id: int) -> str:
        return f"merchant:{merchant_id}:products:default"

    async def get_json(self, key: str) -> Optional[Any]:
        """
        Attempt to fetch from Redis.
        If Redis is down, catches error and returns None (Graceful Degradation).
        """
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except (RedisError, Exception) as exc:
            logger.warning(f"[Cache Degradation] Redis GET failed for key '{key}': {exc}. Falling back to PostgreSQL.")
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Store