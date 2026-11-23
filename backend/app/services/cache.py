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

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Store JSON payload in Redis with TTL (SETEX)."""
        try:
            serialized = json.dumps(value)
            await self.redis.setex(key, ttl_seconds, serialized)
            return True
        except (RedisError, Exception) as exc:
            logger.warning(f"[Cache Degradation] Redis SET failed for key '{key}': {exc}.")
            return False
    async def invalidate_merchant_cache(self, merchant_id: int) -> None:
        """
        Explicit Invalidation: Removes cached catalog and dashboard metrics
        whenever product data or stock approvals change.
        """
        try:
            keys_to_delete = [
                self.dashboard_key(merchant_id),
                self.products_key(merchant_id)
            ]
            await self.redis.delete(*keys_to_delete)
            logger.info(f"Explicitly invalidated cache for merchant {merchant_id}.")
        except (RedisError, Exception) as exc:
            logger.warning(f"[Cache Degradation] Invalidation failed for merchant {merchant_id}: {exc}.")