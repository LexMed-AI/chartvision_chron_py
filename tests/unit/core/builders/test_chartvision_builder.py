"""Tests for ChartVisionBuilder."""
import pytest
from datetime import date, datetime

from app.core.builders.chartvision_builder import ChartVisionBuilder


class TestChartVisionBuilder:
    """Test ChartVisionBuilder functionality."""

    def test_init_creates_empty_builder(self):
        """Test builder initializes with empty state."""
        builder = ChartVisionBuilder()
        assert builder is not None
        assert builder._claimant is None
        assert builder._chronology == []

    def test_set_claimant(self):
        """Test setting claimant data."""
        builder = ChartVisionBuilder()
        result = builder.set_claimant(
            full_name="John Doe",
            date_of_birth=date(1980, 1, 15),
            case_file_reference="123456789",
            total_document_pages=500,
            ssn_last_four="1234",
        )

        # Returns self for chaining
        assert result is builder
        assert builder._claimant is not None
        assert builder._claimant.full_name == "John Doe"

    def test_set_administrative(self):
        """Test setting administrative data."""
        builder = ChartVisionBuilder()
        result = builder.set_administrative(
            claim_type="DIB",
            protective_filing_date=date(2023, 6, 1),
            alleged_onset_date=date(2022, 1, 15),
        )

        assert result is builder
        assert builder._administrative is not None
        assert builder._administrative.claim_type == "DIB"

    def test_add_chronology_entry(self):
        """Test adding chronology entry."""
        builder = ChartVisionBuilder()

        result = builder.add_chronology_entry(
            date=date(2024, 1, 15),
            provider="Dr. Smith",
            facility="City Clinic",
            occurrence="Back pain evaluation",
            source="1F",
        )

        assert result is builder
        assert len(builder._chronology) == 1

    def test_method_chaining(self):
        """Test fluent interface with method chaining."""
        builder = ChartVisionBuilder()

        result = (
            builder
            .set_claimant(
                full_name="John Doe",
                date_of_birth=date(1980, 1, 15),
                case_file_reference="123456789",
                total_document_pages=500,
            )
            .set_administrative(
                claim_type="DIB",
                protective_filing_date=date(2023, 6, 1),
                alleged_onset_date=date(2022, 1, 15),
            )
        )

        assert result is builder
        assert builder._claimant is not None
        assert builder._administrative is not None

    def test_build_returns_report_data(self):
        """Test build produces ChartVisionReportData."""
        builder = ChartVisionBuilder()
        builder.set_claimant(
            full_name="John Doe",
            date_of_birth=date(1980, 1, 15),
            case_file_reference="123456789",
            total_document_pages=500,
        )
        builder.set_administrative(
            claim_type="DIB",
            protective_filing_date=date(2023, 6, 1),
            alleged_onset_date=date(2022, 1, 15),
        )

        result = builder.build()

        assert result is not None
        assert result.claimant.full_name == "John Doe"
        assert result.administrative.claim_type == "DIB"
