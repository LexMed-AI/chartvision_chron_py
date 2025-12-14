"""Tests for JobStore - file-backed job persistence"""
import json
import tempfile
from datetime import datetime
from pathlib import Path
import pytest

from app.api.storage.job_store import JobStore


class TestJobStore:
    """Test JobStore persistence and retrieval"""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_job_store_initialization(self, temp_storage):
        """Should initialize with empty job dict"""
        store = JobStore(storage_dir=str(temp_storage))
        assert len(store) == 0

    def test_job_store_add_and_retrieve(self, temp_storage):
        """Should store and retrieve job data"""
        store = JobStore(storage_dir=str(temp_storage))
        job_id = "test-job-123"
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "created_at": datetime.now(),
        }
        store[job_id] = job_data
        assert job_id in store
        assert store[job_id]["status"] == "queued"

    def test_job_store_persists_completed_jobs(self, temp_storage):
        """Should auto-persist completed jobs to disk"""
        store = JobStore(storage_dir=str(temp_storage))
        job_id = "test-job-456"
        job_data = {
            "job_id": job_id,
            "status": "completed",
            "created_at": datetime.now(),
            "completed_at": datetime.now(),
        }
        store[job_id] = job_data

        # Verify file created
        job_file = temp_storage / f"job_{job_id}.json"
        assert job_file.exists()

    def test_job_store_loads_persisted_jobs_on_startup(self, temp_storage):
        """Should load completed jobs from disk on initialization"""
        # Create a persisted job manually
        job_id = "persisted-job-789"
        job_data = {
            "job_id": job_id,
            "status": "completed",
            "created_at": "2025-01-01T12:00:00",
            "completed_at": "2025-01-01T12:05:00",
        }
        job_file = temp_storage / f"job_{job_id}.json"
        with open(job_file, "w") as f:
            json.dump(job_data, f)

        # Initialize store - should load the job
        store = JobStore(storage_dir=str(temp_storage))
        assert job_id in store
        assert store[job_id]["status"] == "completed"

    def test_job_store_delete_removes_from_disk(self, temp_storage):
        """Should remove job file when deleted"""
        store = JobStore(storage_dir=str(temp_storage))
        job_id = "delete-test-999"
        job_data = {"job_id": job_id, "status": "completed"}
        store[job_id] = job_data

        job_file = temp_storage / f"job_{job_id}.json"
        assert job_file.exists()

        del store[job_id]
        assert job_id not in store
        assert not job_file.exists()
