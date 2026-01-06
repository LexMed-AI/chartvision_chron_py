"""Tests for TextExtractor citation integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extraction.text_extractor import TextExtractor
from app.core.extraction.pdf_exhibit_extractor import PageText


class TestTextExtractorCitations:
    """Test citation matching integration in TextExtractor."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM that returns valid JSON response."""
        llm = MagicMock()
        llm.generate = AsyncMock(return_value='''[
            {
                "date": "03/15/2019",
                "provider": "Dr. Smith",
                "facility": "Little Rock Surgery",
                "visit_type": "office_visit",
                "occurrence_treatment": {"diagnoses": ["Chest pain"]}
            }
        ]''')
        return llm

    @pytest.fixture
    def sample_pages(self):
        """Create sample pages for citation matching."""
        return [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="03/15/2019 Dr. Smith Little Rock Surgery. Patient with chest pain.",
            ),
        ]

    @pytest.fixture
    def exhibit_context(self):
        """Create exhibit context metadata."""
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    @pytest.mark.asyncio
    async def test_extract_attaches_citations(self, mock_llm, sample_pages, exhibit_context):
        """Extracted entries have citations attached when pages provided."""
        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="03/15/2019 Dr. Smith Little Rock Surgery...",
            exhibit_id="25F",
            pages=sample_pages,
            exhibit_context=exhibit_context,
        )

        assert len(entries) == 1
        assert entries[0].get("citation") is not None
        assert entries[0]["citation"].absolute_page == 1847
        assert entries[0]["citation"].exhibit_id == "25F"

    @pytest.mark.asyncio
    async def test_extract_without_pages_no_citation(self, mock_llm):
        """Without page data, entries have no citation."""
        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="Some medical text...",
            exhibit_id="25F",
            pages=None,
        )

        assert len(entries) == 1
        assert entries[0].get("citation") is None

    @pytest.mark.asyncio
    async def test_extract_without_exhibit_context_no_citation(self, mock_llm, sample_pages):
        """Without exhibit context, entries have no citation."""
        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="Some medical text...",
            exhibit_id="25F",
            pages=sample_pages,
            exhibit_context=None,
        )

        assert len(entries) == 1
        assert entries[0].get("citation") is None

    @pytest.mark.asyncio
    async def test_citation_confidence_attached(self, mock_llm, sample_pages, exhibit_context):
        """Citation confidence score is attached to entries."""
        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="03/15/2019 Dr. Smith Little Rock Surgery...",
            exhibit_id="25F",
            pages=sample_pages,
            exhibit_context=exhibit_context,
        )

        assert len(entries) == 1
        assert "citation_confidence" in entries[0]
        # Should have a reasonable match score (date + provider + facility)
        assert entries[0]["citation_confidence"] >= 0

    @pytest.mark.asyncio
    async def test_citation_relative_page(self, mock_llm, sample_pages, exhibit_context):
        """Citation includes correct relative page within exhibit."""
        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="03/15/2019 Dr. Smith Little Rock Surgery...",
            exhibit_id="25F",
            pages=sample_pages,
            exhibit_context=exhibit_context,
        )

        assert len(entries) == 1
        citation = entries[0]["citation"]
        assert citation.relative_page == 33

    @pytest.mark.asyncio
    async def test_multiple_entries_get_citations(self, mock_llm, exhibit_context):
        """Multiple extracted entries each get their own citation."""
        # Mock LLM to return multiple entries
        mock_llm.generate = AsyncMock(return_value='''[
            {
                "date": "03/15/2019",
                "provider": "Dr. Smith",
                "facility": "Little Rock Surgery",
                "visit_type": "office_visit",
                "occurrence_treatment": {}
            },
            {
                "date": "04/20/2019",
                "provider": "Dr. Jones",
                "facility": "Memorial Hospital",
                "visit_type": "hospitalization",
                "occurrence_treatment": {}
            }
        ]''')

        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="03/15/2019 Dr. Smith Little Rock Surgery. Patient visit.",
            ),
            PageText(
                absolute_page=1855,
                relative_page=41,
                exhibit_id="25F",
                text="04/20/2019 Dr. Jones Memorial Hospital admission.",
            ),
        ]

        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="Medical records text...",
            exhibit_id="25F",
            pages=pages,
            exhibit_context=exhibit_context,
        )

        assert len(entries) == 2
        # Each entry should have its own citation
        assert entries[0].get("citation") is not None
        assert entries[1].get("citation") is not None
        # Citations should point to different pages based on matching
        assert entries[0]["citation"].absolute_page == 1847
        assert entries[1]["citation"].absolute_page == 1855

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty_list(self, mock_llm, sample_pages, exhibit_context):
        """Empty text returns empty list without calling citation matcher."""
        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="   ",
            exhibit_id="25F",
            pages=sample_pages,
            exhibit_context=exhibit_context,
        )

        assert entries == []
        # LLM should not be called for empty text
        mock_llm.generate.assert_not_called()
