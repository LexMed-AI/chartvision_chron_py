"""Storage port interface.

Defines the contract for job state persistence. Core code depends only on this
abstraction, not on specific implementations like Redis.
"""
from abc import ABC, abstractmethod
from typing import Optional


class JobStoragePort(ABC):
    """Abstract interface for job state persistence.

    Implementations: RedisAdapter
    """

    @abstractmethod
    async def save_job(self, job_id: str, data: dict) -> None:
        """Save job data.

        Args:
            job_id: Unique job identifier
            data: Job data dictionary
        """
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[dict]:
        """Retrieve job data.

        Args:
            job_id: Unique job identifier

        Returns:
            Job data or None if not found
        """
        pass

    @abstractmethod
    async def update_job(self, job_id: str, updates: dict) -> None:
        """Update job data.

        Args:
            job_id: Unique job identifier
            updates: Fields to update
        """
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> None:
        """Delete job data.

        Args:
            job_id: Unique job identifier
        """
        pass
