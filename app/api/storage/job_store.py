"""
Persistent job storage with file-based backup.

Keeps jobs in memory for fast access while persisting completed jobs
to disk for recovery after server restarts.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class JobStore:
    """Persistent job storage with file-based backup.

    Keeps jobs in memory for fast access while persisting completed jobs
    to disk for recovery after server restarts.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize job store.

        Args:
            storage_dir: Directory for job persistence (default: results/)
        """
        self.storage_dir = Path(storage_dir or os.environ.get(
            "JOB_STORAGE_DIR",
            Path(__file__).parent.parent.parent.parent / "results"
        ))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, Any] = {}
        self._load_persisted_jobs()

    def _load_persisted_jobs(self) -> None:
        """Load completed jobs from disk on startup."""
        for job_file in self.storage_dir.glob("job_*.json"):
            try:
                with open(job_file) as f:
                    job_data = json.load(f)
                    job_id = job_data.get("job_id")
                    if job_id:
                        # Convert date strings back to datetime objects
                        for field in ["created_at", "started_at", "completed_at"]:
                            if job_data.get(field):
                                job_data[field] = datetime.fromisoformat(job_data[field])
                        self._jobs[job_id] = job_data
            except Exception as e:
                logger.warning(f"Failed to load {job_file}: {e}")

    def _persist_job(self, job_id: str) -> None:
        """Persist a completed job to disk."""
        job = self._jobs.get(job_id)
        if not job or job.get("status") not in ["completed", "failed"]:
            return

        job_file = self.storage_dir / f"job_{job_id}.json"

        # Create serializable copy
        job_copy = {}
        for key, value in job.items():
            if isinstance(value, datetime):
                job_copy[key] = value.isoformat()
            elif isinstance(value, Path):
                job_copy[key] = str(value)
            else:
                job_copy[key] = value

        try:
            with open(job_file, "w") as f:
                json.dump(job_copy, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to persist job {job_id}: {e}")

    def __contains__(self, job_id: str) -> bool:
        """Check if job exists."""
        return job_id in self._jobs

    def __getitem__(self, job_id: str) -> Dict[str, Any]:
        """Get job by ID."""
        return self._jobs[job_id]

    def __setitem__(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """Set job data, auto-persist if completed/failed."""
        self._jobs[job_id] = job_data
        # Auto-persist completed/failed jobs
        if job_data.get("status") in ["completed", "failed"]:
            self._persist_job(job_id)

    def __delitem__(self, job_id: str) -> None:
        """Delete job from memory and disk."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            # Also remove from disk
            job_file = self.storage_dir / f"job_{job_id}.json"
            if job_file.exists():
                job_file.unlink()

    def __len__(self) -> int:
        """Get number of jobs."""
        return len(self._jobs)

    def __iter__(self):
        """Iterate over job IDs."""
        return iter(self._jobs)

    def items(self):
        """Get job items."""
        return self._jobs.items()

    def get(self, job_id: str, default=None):
        """Get job with default."""
        return self._jobs.get(job_id, default)

    def persist(self, job_id: str) -> None:
        """Manually trigger persistence for a job."""
        self._persist_job(job_id)
