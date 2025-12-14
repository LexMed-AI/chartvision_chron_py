"""Tests for RedisAdapter implementing JobStoragePort."""
import pytest
from unittest.mock import MagicMock

from app.adapters.storage.redis_adapter import RedisAdapter
from app.core.ports.storage import JobStoragePort


class TestRedisAdapter:
    """Test RedisAdapter implements JobStoragePort correctly."""

    def test_implements_job_storage_port(self):
        """Verify RedisAdapter is a JobStoragePort."""
        mock_redis = MagicMock()
        adapter = RedisAdapter(mock_redis)
        assert isinstance(adapter, JobStoragePort)

    @pytest.mark.asyncio
    async def test_save_job(self):
        """Test saving job data to Redis."""
        mock_redis = MagicMock()
        mock_redis.set = MagicMock()
        adapter = RedisAdapter(mock_redis)

        await adapter.save_job("job-123", {"status": "pending"})

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "job-123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_job_returns_data(self):
        """Test retrieving job data from Redis."""
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=b'{"status": "complete"}')
        adapter = RedisAdapter(mock_redis)

        result = await adapter.get_job("job-123")

        assert result == {"status": "complete"}

    @pytest.mark.asyncio
    async def test_get_job_returns_none_when_missing(self):
        """Test get_job returns None for missing job."""
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=None)
        adapter = RedisAdapter(mock_redis)

        result = await adapter.get_job("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_job_merges_data(self):
        """Test updating job data merges with existing."""
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=b'{"status": "pending", "file": "test.pdf"}')
        mock_redis.set = MagicMock()
        adapter = RedisAdapter(mock_redis)

        await adapter.update_job("job-123", {"status": "complete"})

        # Should have merged the update
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "complete" in str(call_args)

    @pytest.mark.asyncio
    async def test_delete_job(self):
        """Test deleting job data from Redis."""
        mock_redis = MagicMock()
        mock_redis.delete = MagicMock()
        adapter = RedisAdapter(mock_redis)

        await adapter.delete_job("job-123")

        mock_redis.delete.assert_called_once()
        call_args = mock_redis.delete.call_args
        assert "job-123" in call_args[0][0]
