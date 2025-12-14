"""Tests for ChartVisionReportGenerator."""
import pytest
from datetime import datetime

from app.core.builders.report_generator import ChartVisionReportGenerator


class TestChartVisionReportGenerator:
    """Test ChartVisionReportGenerator functionality."""

    @pytest.fixture
    def generator(self):
        """Create generator instance."""
        return ChartVisionReportGenerator()

    def test_init(self, generator):
        """Test generator initializes."""
        assert generator is not None
        assert generator.date_format == "%m/%d/%Y"

    def test_format_date_valid(self, generator):
        """Test formatting valid datetime."""
        dt = datetime(2024, 1, 15)
        result = generator._format_date(dt)
        assert result == "01/15/2024"

    def test_format_date_none(self, generator):
        """Test formatting None returns empty string."""
        result = generator._format_date(None)
        assert result == ""

    def test_mask_ssn_full(self, generator):
        """Test masking full SSN."""
        result = generator._mask_ssn("123-45-6789")
        assert result == "XXX-XX-6789"

    def test_mask_ssn_last_four(self, generator):
        """Test masking SSN with only last 4."""
        result = generator._mask_ssn("6789")
        assert "6789" in result

    def test_mask_ssn_none(self, generator):
        """Test masking None SSN."""
        result = generator._mask_ssn(None)
        assert result == ""

    def test_mask_ssn_empty(self, generator):
        """Test masking empty SSN."""
        result = generator._mask_ssn("")
        assert result == ""
