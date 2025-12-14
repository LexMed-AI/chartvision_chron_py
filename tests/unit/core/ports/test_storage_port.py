"""Tests for storage port interface."""
import pytest
from app.core.ports.storage import JobStoragePort


class TestStoragePortInterface:
    def test_cannot_instantiate_abstract_port(self):
        with pytest.raises(TypeError):
            JobStoragePort()

    def test_concrete_implementation_works(self):
        class MockStorage(JobStoragePort):
            def __init__(self):
                self._data = {}

            async def save_job(self, job_id, data):
                self._data[job_id] = data

            async def get_job(self, job_id):
                return self._data.get(job_id)

            async def update_job(self, job_id, updates):
                if job_id in self._data:
                    self._data[job_id].update(updates)

            async def delete_job(self, job_id):
                self._data.pop(job_id, None)

        mock = MockStorage()
        assert mock._data == {}
