"""Tests for extraction limit configuration"""
from app.config.extraction_limits import (
    MAX_EXHIBITS_PER_JOB,
    MAX_PAGES_PER_EXHIBIT,
    MAX_IMAGES_PER_EXHIBIT,
    DEFAULT_CHUNK_SIZE,
)


class TestExtractionLimits:
    """Test extraction limit constants"""

    def test_constants_are_defined(self):
        """Should define all extraction limit constants"""
        assert MAX_EXHIBITS_PER_JOB == 50
        assert MAX_PAGES_PER_EXHIBIT == 50
        assert MAX_IMAGES_PER_EXHIBIT == 20
        assert DEFAULT_CHUNK_SIZE == 40_000

    def test_constants_are_positive(self):
        """All limits should be positive integers"""
        assert MAX_EXHIBITS_PER_JOB > 0
        assert MAX_PAGES_PER_EXHIBIT > 0
        assert MAX_IMAGES_PER_EXHIBIT > 0
        assert DEFAULT_CHUNK_SIZE > 0
