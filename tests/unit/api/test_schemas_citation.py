"""Tests for CitationSchema and ChronologyEntrySchema in API schemas."""
import pytest
from pydantic import ValidationError

from app.api.schemas import CitationSchema, ChronologyEntrySchema


class TestCitationSchema:
    """Test CitationSchema Pydantic model."""

    def test_citation_schema_full(self):
        """Full citation with all fields populated."""
        citation = CitationSchema(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            total_pages=74,
            end_relative_page=35,
            end_absolute_page=1849,
            is_estimated=False,
            confidence=0.95,
            formatted="25F@33-35 (pp.1847-1849)",
        )

        assert citation.exhibit_id == "25F"
        assert citation.relative_page == 33
        assert citation.absolute_page == 1847
        assert citation.total_pages == 74
        assert citation.end_relative_page == 35
        assert citation.end_absolute_page == 1849
        assert citation.is_estimated is False
        assert citation.confidence == 0.95
        assert citation.formatted == "25F@33-35 (pp.1847-1849)"

    def test_citation_schema_minimal(self):
        """Minimal citation with only required fields."""
        citation = CitationSchema(
            absolute_page=1847,
            formatted="p.1847",
        )

        assert citation.exhibit_id is None
        assert citation.relative_page is None
        assert citation.absolute_page == 1847
        assert citation.total_pages is None
        assert citation.end_relative_page is None
        assert citation.end_absolute_page is None
        assert citation.is_estimated is False  # default
        assert citation.confidence == 1.0  # default
        assert citation.formatted == "p.1847"

    def test_citation_schema_missing_absolute_page(self):
        """absolute_page is required."""
        with pytest.raises(ValidationError) as exc_info:
            CitationSchema(formatted="p.1847")

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("absolute_page",) for err in errors)

    def test_citation_schema_missing_formatted(self):
        """formatted field is required."""
        with pytest.raises(ValidationError) as exc_info:
            CitationSchema(absolute_page=1847)

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("formatted",) for err in errors)

    def test_citation_schema_confidence_bounds(self):
        """Confidence must be between 0 and 1."""
        # Valid confidence
        citation = CitationSchema(
            absolute_page=1847,
            formatted="p.1847",
            confidence=0.5,
        )
        assert citation.confidence == 0.5

        # Invalid: too high
        with pytest.raises(ValidationError):
            CitationSchema(
                absolute_page=1847,
                formatted="p.1847",
                confidence=1.5,
            )

        # Invalid: negative
        with pytest.raises(ValidationError):
            CitationSchema(
                absolute_page=1847,
                formatted="p.1847",
                confidence=-0.1,
            )

    def test_citation_schema_to_dict(self):
        """Schema can be converted to dict for JSON serialization."""
        citation = CitationSchema(
            exhibit_id="5F",
            relative_page=10,
            absolute_page=500,
            formatted="5F@10 (p.500)",
        )

        data = citation.model_dump()
        assert data["exhibit_id"] == "5F"
        assert data["relative_page"] == 10
        assert data["absolute_page"] == 500
        assert data["formatted"] == "5F@10 (p.500)"


class TestChronologyEntrySchema:
    """Test ChronologyEntrySchema Pydantic model."""

    def test_chronology_entry_with_citation(self):
        """Chronology entry with full citation data."""
        citation = CitationSchema(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            formatted="25F@33 (p.1847)",
        )

        entry = ChronologyEntrySchema(
            date="03/15/2023",
            provider="Dr. Smith",
            facility="General Hospital",
            event_type="Office Visit",
            description="Follow-up for chronic back pain",
            exhibit_id="25F",
            citation=citation,
        )

        assert entry.date == "03/15/2023"
        assert entry.provider == "Dr. Smith"
        assert entry.facility == "General Hospital"
        assert entry.event_type == "Office Visit"
        assert entry.description == "Follow-up for chronic back pain"
        assert entry.exhibit_id == "25F"
        assert entry.citation is not None
        assert entry.citation.formatted == "25F@33 (p.1847)"

    def test_chronology_entry_without_citation(self):
        """Chronology entry without citation (citation is optional)."""
        entry = ChronologyEntrySchema(
            description="Medical event without source tracking",
        )

        assert entry.date is None
        assert entry.provider is None
        assert entry.facility is None
        assert entry.event_type is None
        assert entry.description == "Medical event without source tracking"
        assert entry.exhibit_id is None
        assert entry.citation is None

    def test_chronology_entry_description_required(self):
        """Description field is required."""
        with pytest.raises(ValidationError) as exc_info:
            ChronologyEntrySchema()

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("description",) for err in errors)

    def test_chronology_entry_to_dict_with_citation(self):
        """Entry with citation can be serialized to dict."""
        citation = CitationSchema(
            exhibit_id="5F",
            relative_page=1,
            absolute_page=100,
            formatted="5F@1 (p.100)",
        )

        entry = ChronologyEntrySchema(
            date="01/01/2024",
            description="Test event",
            citation=citation,
        )

        data = entry.model_dump()
        assert data["date"] == "01/01/2024"
        assert data["description"] == "Test event"
        assert data["citation"]["exhibit_id"] == "5F"
        assert data["citation"]["formatted"] == "5F@1 (p.100)"

    def test_chronology_entry_from_dict(self):
        """Entry can be created from dict (e.g., JSON deserialization)."""
        data = {
            "date": "02/14/2024",
            "provider": "Dr. Jones",
            "description": "Annual checkup",
            "citation": {
                "exhibit_id": "10F",
                "relative_page": 5,
                "absolute_page": 250,
                "formatted": "10F@5 (p.250)",
            },
        }

        entry = ChronologyEntrySchema(**data)
        assert entry.provider == "Dr. Jones"
        assert entry.citation.exhibit_id == "10F"
