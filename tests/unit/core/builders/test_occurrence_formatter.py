"""Tests for OccurrenceFormatter."""
import pytest

from app.core.builders.occurrence_formatter import OccurrenceFormatter


class TestOccurrenceFormatter:
    """Test OccurrenceFormatter functionality."""

    @pytest.fixture
    def formatter(self):
        """Create formatter instance."""
        return OccurrenceFormatter()

    def test_init_loads_config(self, formatter):
        """Test formatter loads configuration."""
        assert formatter is not None
        assert formatter._config is not None
        assert len(formatter._config) > 0

    def test_format_empty_occurrence(self, formatter):
        """Test formatting empty occurrence returns empty string."""
        result = formatter.format("office_visit", {})
        assert result == ""

    def test_format_none_occurrence(self, formatter):
        """Test formatting None occurrence returns empty string."""
        result = formatter.format("office_visit", None)
        assert result == ""

    def test_format_office_visit(self, formatter):
        """Test formatting office visit occurrence."""
        occurrence = {
            "chief_complaint": "Back pain",
            "assessment_diagnoses": ["M54.5 - Low back pain"],
            "plan_of_care": "Physical therapy referral",
        }
        result = formatter.format("office_visit", occurrence)

        assert "**CC:**" in result
        assert "Back pain" in result
        assert "**Dx:**" in result
        assert "M54.5" in result

    def test_format_imaging_report(self, formatter):
        """Test formatting imaging report occurrence."""
        occurrence = {
            "imaging_type": "MRI",
            "body_part": "Lumbar spine",
            "findings": "Disc herniation at L4-L5",
            "impression": "Moderate degenerative changes",
        }
        result = formatter.format("imaging_report", occurrence)

        assert "**Type:**" in result
        assert "MRI" in result
        assert "**Findings:**" in result
        assert "L4-L5" in result

    def test_format_unknown_visit_type_uses_generic(self, formatter):
        """Test unknown visit type uses generic formatter."""
        occurrence = {
            "some_field": "Some value",
            "another_field": "Another value",
        }
        result = formatter.format("unknown_type", occurrence)

        assert "Some Field" in result or "some_field" in result.lower()
        assert "Some value" in result

    def test_format_truncates_long_values(self, formatter):
        """Test long values are truncated."""
        long_text = "x" * 500
        occurrence = {
            "chief_complaint": long_text,
        }
        result = formatter.format("office_visit", occurrence)

        # Value should be truncated (max 300 chars in config)
        assert len(result) < len(long_text) + 50
        assert "..." in result

    def test_format_list_values(self, formatter):
        """Test list values are joined."""
        occurrence = {
            "assessment_diagnoses": ["Diagnosis 1", "Diagnosis 2", "Diagnosis 3"],
        }
        result = formatter.format("office_visit", occurrence)

        assert "Diagnosis 1" in result
        assert "Diagnosis 2" in result

    def test_format_uses_html_separator(self):
        """Test default separator is <br>."""
        formatter = OccurrenceFormatter(separator="<br>")
        occurrence = {
            "chief_complaint": "Pain",
            "assessment_diagnoses": ["Diagnosis"],
        }
        result = formatter.format("office_visit", occurrence)

        assert "<br>" in result

    def test_format_custom_separator(self):
        """Test custom separator."""
        formatter = OccurrenceFormatter(separator="\n")
        occurrence = {
            "chief_complaint": "Pain",
            "assessment_diagnoses": ["Diagnosis"],
        }
        result = formatter.format("office_visit", occurrence)

        assert "\n" in result
        assert "<br>" not in result
