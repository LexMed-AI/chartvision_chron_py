"""Redis implementation of JobStoragePort.

Provides job state persistence using Redis as the backing store.
"""
import json
from typing import Optional

from app.core.ports.storage import JobStoragePort


class RedisAdapter(JobStoragePort):
    """Redis implementation of JobStoragePort.

    Args:
        redis_client: Configured redis.Redis instance
        key_prefix: Prefix for all job keys (default: "job:")
        ttl_seconds: Time-to-live for job data (default: 86400 = 24h)
    """

    def __init__(
        self,
        redis_client,
        key_prefix: str = "job:",
        ttl_seconds: int = 86400,
    ):
        self._redis = redis_client
        self._prefix = key_prefix
        self._ttl = ttl_seconds

    def _key(self, job_id: str) -> str:
        """Build Redis key for job."""
        return f"{self._prefix}{job_id}"

    async def save_job(self, job_id: str, data: dict) -> None:
        """Save job data to Redis with TTL."""
        key = self._key(job_id)
        self._redis.set(key, json.dumps(data), ex=self._ttl)

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Retrieve job data from Redis."""
        key = self._key(job_id)
        raw = self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def update_job(self, job_id: str, updates: dict) -> None:
        """Update job data in Redis (merge with existing)."""
        existing = await self.get_job(job_id)
        if existing is None:
            existing = {}
        existing.update(updates)
        await self.save_job(job_id, existing)

    async def delete_job(self, job_id: str) -> None:
        """Delete job data from Redis."""
        key = self._key(job_id)
        self._redis.delete(key)
