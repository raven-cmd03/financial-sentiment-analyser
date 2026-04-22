import json
import logging
from typing import Any, Callable, Optional

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Async Redis cache with JSON serialization and cache-aside pattern."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        settings = get_settings()
        self._redis = redis_client or redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )

    async def get(self, key: str) -> Optional[str]:
        try:
            value = await self._redis.get(key)
            if value is not None:
                logger.debug("Cache HIT: %s", key)
                return json.loads(value)
            logger.debug("Cache MISS: %s", key)
            return None
        except (redis.RedisError, json.JSONDecodeError) as exc:
            logger.warning("Cache get failed for key=%s: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        try:
            serialized = json.dumps(value, default=str)
            await self._redis.set(key, serialized, ex=ttl)
            logger.debug("Cache SET: %s (ttl=%ds)", key, ttl)
        except (redis.RedisError, TypeError) as exc:
            logger.warning("Cache set failed for key=%s: %s", key, exc)

    async def invalidate(self, key: str) -> None:
        try:
            await self._redis.delete(key)
            logger.debug("Cache INVALIDATE: %s", key)
        except redis.RedisError as exc:
            logger.warning("Cache invalidate failed for key=%s: %s", key, exc)

    async def get_or_set(
        self, key: str, factory: Callable, ttl: int = 3600
    ) -> Any:
        """Cache-aside: return cached value or call *factory*, cache the result, and return it."""
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = factory() if not callable(getattr(factory, "__await__", None)) else await factory()
        await self.set(key, value, ttl=ttl)
        return value

    async def close(self) -> None:
        await self._redis.close()
