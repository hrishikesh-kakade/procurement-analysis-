"""Redis-backed read cache with namespace versioning.

Entries are keyed by (namespace version, hash of parameters). Invalidating a namespace just bumps
its version, so stale entries become unreachable and expire via TTL. Fails open: if Redis is
unavailable the producer is called directly.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from functools import lru_cache
from typing import Any

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Cache:
    def __init__(self, client: redis.Redis | None = None, ttl: int = 300) -> None:
        self.client = client
        self.ttl = ttl

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def get_or_set(self, namespace: str, params: dict, producer: Callable[[], Any]) -> Any:
        if self.client is None:
            return producer()
        key = None
        try:
            version = self.client.get(f"cache:{namespace}:version") or "0"
            digest = hashlib.sha256(
                json.dumps(params, sort_keys=True, default=str).encode()
            ).hexdigest()[:32]
            key = f"cache:{namespace}:{version}:{digest}"
            hit = self.client.get(key)
            if hit is not None:
                return json.loads(hit)
        except redis.RedisError:
            logger.warning("cache read failed; falling back to database", exc_info=True)
            return producer()
        value = producer()
        try:
            self.client.set(key, json.dumps(value, default=str), ex=self.ttl)
        except redis.RedisError:
            logger.warning("cache write failed", exc_info=True)
        return value

    def invalidate(self, namespace: str) -> None:
        if self.client is None:
            return
        try:
            self.client.incr(f"cache:{namespace}:version")
        except redis.RedisError:
            logger.warning("cache invalidation failed", exc_info=True)


@lru_cache
def get_cache() -> Cache:
    settings = get_settings()
    if not settings.redis_url:
        return Cache(None)
    client = redis.Redis.from_url(
        settings.redis_url, decode_responses=True, socket_timeout=1, socket_connect_timeout=1
    )
    return Cache(client, settings.cache_ttl_seconds)


def invalidate_analytics() -> None:
    get_cache().invalidate("analytics")
