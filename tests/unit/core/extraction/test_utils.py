"""Tests for extraction utility functions."""
import pytest
from datetime import datetime

from app.core.extraction.utils import (
    normalize_exhibits,
    is_f_section_exhibit,
    calculate_confidence,
    calculate_quality_metrics,
    calculate_statistics,
)


class TestNormalizeExhibits:
    """Test normalize_exhibits function."""

    def test_normalizes_legacy_tuple_format(self):
        """Test normalizing list of (text, id) tuples."""
        exhibits = [("Patient seen for back pain.", "1F"), ("Lab results normal.", "2F")]
        result = normalize_exhibits(exhibits)

        assert len(result) == 2
        assert result[0]["exhibit_id"] == "1F"
        assert result[0]["text"] == "Patient seen for back pain."
        assert result[0]["images"] == []
        assert result[0]["has_scanned_pages"] is False

    def test_normalizes_dict_format(self):
        """Test normalizing list of exhibit dicts."""
        exhibits = [
            {"exhibit_id": "1F", "text": "Some text", "images": [b"img1"], "has_scanned_pages": True}
        ]
        result = normalize_exhibits(exhibits)

        assert len(result) == 1
        assert result[0]["exhibit_id"] == "1F"
        assert result[0]["text"] == "Some text"
        assert result[0]["images"] == [b"img1"]
        assert result[0]["has_scanned_pages"] is True

    def test_normalizes_legacy_dict_format(self):
        """Test normalizing {id: text} dict format."""
        exhibits = {"1F": "First exhibit text", "2F": "Second exhibit text"}
        result = normalize_exhibits(exhibits)

        assert len(result) == 2
        exhibit_ids = [e["exhibit_id"] for e in result]
        assert "1F" in exhibit_ids
        assert "2F" in exhibit_ids

    def test_handles_empty_list(self):
        """Test normalizing empty list."""
        result = normalize_exhibits([])
        assert result == []

    def test_handles_empty_dict(self):
        """Test normalizing empty dict."""
        result = normalize_exhibits({})
        assert result == []

    def test_raises_for_unsupported_format(self):
        """Test raises ValueError for unsupported format."""
        with pytest.raises(ValueError, match="Unsupported exhibit format"):
            normalize_exhibits("invalid")

    def test_preserves_page_range(self):
        """Test preserves page_range from dict format."""
        exhibits = [
            {"exhibit_id": "1F", "text": "Text", "page_range": (100, 120)}
        ]
        result = normalize_exhibits(exhibits)
        assert result[0]["page_range"] == (100, 120)


class TestIsFSectionExhibit:
    """Test is_f_section_exhibit function."""

    def test_detects_exhibit_id_ending_with_f(self):
        """Test detects ID ending with F."""
        assert is_f_section_exhibit("", "1F") is True
        assert is_f_section_exhibit("", "2F") is True
        assert is_f_section_exhibit("", "10F") is True

    def test_detects_f_colon_prefix(self):
        """Test detects F: prefix in ID."""
        assert is_f_section_exhibit("", "F: Medical Records") is True

    def test_detects_f_at_format(self):
        """Test detects F@ format."""
        assert is_f_section_exhibit("", "1F@12") is True

    def test_detects_medical_content(self):
        """Test detects medical content indicators."""
        assert is_f_section_exhibit("Patient medical records", "1A") is True
        assert is_f_section_exhibit("Doctor visit notes", "1A") is True
        assert is_f_section_exhibit("Hospital discharge summary", "1A") is True
        assert is_f_section_exhibit("Treatment plan documented", "1A") is True
        assert is_f_section_exhibit("diagnosis confirmed", "1A") is True

    def test_rejects_non_f_section(self):
        """Test rejects non-F section exhibits."""
        assert is_f_section_exhibit("Financial records", "1A") is False
        assert is_f_section_exhibit("Employment history", "2B") is False

    def test_case_insensitive_id(self):
        """Test ID check is case-insensitive."""
        assert is_f_section_exhibit("", "1f") is True
        assert is_f_section_exhibit("", "F:test") is True


class TestCalculateConfidence:
    """Test calculate_confidence function."""

    def test_full_confidence_factors(self):
        """Test confidence with all factors present."""
        providers = [{"name": "Dr. Smith"}, {"name": "Dr. Jones"}, {"name": "Dr. Brown"},
                     {"name": "Dr. White"}, {"name": "Dr. Green"}]
        timeline = [{"date": "2024-01-15"}, {"date": "2024-02-20"}]

        result = calculate_confidence(1.0, providers, timeline)

        assert 0.0 <= result <= 1.0
        assert result > 0.5  # Should be reasonable confidence

    def test_low_confidence_incomplete_data(self):
        """Test low confidence with incomplete data."""
        result = calculate_confidence(0.2, [], [])
        assert result < 0.5

    def test_empty_timeline(self):
        """Test confidence with empty timeline."""
        result = calculate_confidence(0.5, [{"name": "Dr. Smith"}], [])
        assert 0.0 <= result <= 1.0

    def test_undated_events_reduce_confidence(self):
        """Test undated events reduce timeline confidence factor."""
        timeline = [{"date": "2024-01-15"}, {"note": "no date"}]
        result = calculate_confidence(0.5, [], timeline)
        assert 0.0 <= result <= 1.0


class TestCalculateQualityMetrics:
    """Test calculate_quality_metrics function."""

    def test_returns_all_metrics(self):
        """Test returns all expected metric keys."""
        result = calculate_quality_metrics(
            data_completeness=0.8,
            confidence_score=0.7,
            timeline=[{"date": "2024-01-15"}],
            providers=[{"name": "Dr. Smith"}, {"name": "Dr. Jones"}],
            diagnoses=[{"code": "M54.5"}],
            treatments=[{"type": "medication"}],
        )

        assert result["data_completeness"] == 0.8
        assert result["confidence_score"] == 0.7
        assert result["timeline_coverage"] == 1
        assert result["provider_diversity"] == 2
        assert result["diagnosis_count"] == 1
        assert result["treatment_documentation"] == 1

    def test_handles_empty_lists(self):
        """Test handles empty lists gracefully."""
        result = calculate_quality_metrics(
            data_completeness=0.5,
            confidence_score=0.5,
            timeline=[],
            providers=[],
            diagnoses=[],
            treatments=[],
        )

        assert result["timeline_coverage"] == 0
        assert result["provider_diversity"] == 0


class TestCalculateStatistics:
    """Test calculate_statistics function."""

    def test_empty_events(self):
        """Test with empty events list."""
        result = calculate_statistics([])
        assert result["total_events"] == 0
        assert result["date_range"] == "No events"

    def test_events_with_string_dates(self):
        """Test with events containing string dates."""
        events = [
            {"date": "2024-01-15"},
            {"date": "2024-06-20"},
        ]
        result = calculate_statistics(events)

        assert result["total_events"] == 2
        assert "2024" in result["date_range"]

    def test_events_without_dates(self):
        """Test with events lacking dates."""
        events = [{"note": "no date"}, {"note": "also no date"}]
        result = calculate_statistics(events)

        assert result["total_events"] == 2
        assert result["date_range"] == "No dated events"

    def test_mixed_date_formats(self):
        """Test with various date formats."""
        events = [
            {"date": "2024-01-15"},  # ISO format
            {"date": "06/20/2024"},  # US format
        ]
        result = calculate_statistics(events)

        assert result["total_events"] == 2
        # Both dates should parse
        assert "No dated events" not in result["date_range"]

    def test_events_with_datetime_objects(self):
        """Test with events containing datetime objects."""
        events = [
            {"date": datetime(2024, 1, 15)},
            {"date": datetime(2024, 6, 20)},
        ]
        result = calculate_statistics(events)

        assert result["total_events"] == 2
        assert "2024" in result["date_range"]
