"""Tests for VisionExtractor citation tracking integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extraction.vision_extractor import VisionExtractor


class TestVisionExtractorCitations:
    """Test citation attachment in VisionExtractor."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM that returns a single entry."""
        llm = MagicMock()
        llm.generate_with_vision = AsyncMock(return_value='''[
            {
                "date": "03/15/2019",
                "provider": "Dr. Smith",
                "visit_type": "office_visit"
            }
        ]''')
        return llm

    @pytest.fixture
    def exhibit_context(self):
        """Standard exhibit context for testing."""
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    @pytest.mark.asyncio
    async def test_single_page_deterministic_citation(self, mock_llm, exhibit_context):
        """Single page batch has deterministic citation."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[1847],
            exhibit_context=exhibit_context,
        )

        assert len(entries) == 1
        assert entries[0].get("citation") is not None
        citation = entries[0]["citation"]
        assert citation.absolute_page == 1847
        assert citation.relative_page == 33  # 1847 - 1815 + 1
        assert citation.exhibit_id == "25F"
        assert citation.is_estimated is False
        assert citation.confidence == 0.95

    @pytest.mark.asyncio
    async def test_multi_page_batch_attribution(self, mock_llm, exhibit_context):
        """Multi-page batch attributes to first page with range."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"img1", b"img2", b"img3"],
            exhibit_id="25F",
            page_nums=[1847, 1848, 1849],
            exhibit_context=exhibit_context,
        )

        assert len(entries) == 1
        citation = entries[0]["citation"]
        # Primary page is first in batch
        assert citation.absolute_page == 1847
        assert citation.relative_page == 33
        # Range extends to last page
        assert citation.end_absolute_page == 1849
        assert citation.end_relative_page == 35  # 1849 - 1815 + 1

    @pytest.mark.asyncio
    async def test_no_citation_without_exhibit_context(self, mock_llm):
        """No citation attached when exhibit_context is not provided."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[1847],
            # No exhibit_context provided
        )

        assert len(entries) == 1
        # Citation should not be present
        assert entries[0].get("citation") is None

    @pytest.mark.asyncio
    async def test_no_citation_without_page_nums(self, mock_llm, exhibit_context):
        """No citation attached when page_nums is empty."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[],  # Empty page numbers
            exhibit_context=exhibit_context,
        )

        # Entries are still extracted, but no citation (empty batch_pages)
        assert len(entries) == 1
        assert entries[0].get("citation") is None

    @pytest.mark.asyncio
    async def test_citation_format_full(self, mock_llm, exhibit_context):
        """Citation formats correctly in full style."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[1847],
            exhibit_context=exhibit_context,
        )

        citation = entries[0]["citation"]
        formatted = citation.format("full")
        assert formatted == "25F@33 (p.1847)"

    @pytest.mark.asyncio
    async def test_citation_source_type_is_ere(self, mock_llm, exhibit_context):
        """Citation source_type is set to 'ere' for ERE format."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[1847],
            exhibit_context=exhibit_context,
        )

        citation = entries[0]["citation"]
        assert citation.source_type == "ere"

    @pytest.mark.asyncio
    async def test_citation_with_total_pages(self, mock_llm, exhibit_context):
        """Citation includes total_pages from exhibit context."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[1847],
            exhibit_context=exhibit_context,
        )

        citation = entries[0]["citation"]
        assert citation.total_pages == 74

    @pytest.mark.asyncio
    async def test_first_page_of_exhibit(self, mock_llm, exhibit_context):
        """First page of exhibit has relative_page=1."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[1815],  # First page of exhibit
            exhibit_context=exhibit_context,
        )

        citation = entries[0]["citation"]
        assert citation.relative_page == 1
        assert citation.absolute_page == 1815

    @pytest.mark.asyncio
    async def test_backward_compatibility_without_context(self, mock_llm):
        """Existing code without exhibit_context continues to work."""
        extractor = VisionExtractor(mock_llm)

        # Call without exhibit_context (backward compatible)
        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[1847],
        )

        # Should still return entries
        assert len(entries) == 1
        assert entries[0]["date"] == "03/15/2019"
        # But no citation
        assert "citation" not in entries[0]


class TestBuildCitationMethod:
    """Direct tests for _build_citation helper method."""

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        return llm

    def test_build_citation_single_page(self, mock_llm):
        """_build_citation creates correct citation for single page."""
        extractor = VisionExtractor(mock_llm)
        exhibit_context = {
            "exhibit_start": 1815,
            "total_pages": 74,
        }

        citation = extractor._build_citation(
            page_nums=[1847],
            exhibit_id="25F",
            exhibit_context=exhibit_context,
        )

        assert citation.exhibit_id == "25F"
        assert citation.absolute_page == 1847
        assert citation.relative_page == 33
        assert citation.total_pages == 74
        assert citation.is_estimated is False
        assert citation.confidence == 0.95
        assert citation.end_absolute_page is None

    def test_build_citation_multi_page(self, mock_llm):
        """_build_citation creates correct citation for multi-page batch."""
        extractor = VisionExtractor(mock_llm)
        exhibit_context = {
            "exhibit_start": 1815,
            "total_pages": 74,
        }

        citation = extractor._build_citation(
            page_nums=[1847, 1848, 1849],
            exhibit_id="25F",
            exhibit_context=exhibit_context,
        )

        assert citation.absolute_page == 1847
        assert citation.relative_page == 33
        assert citation.end_absolute_page == 1849
        assert citation.end_relative_page == 35

    def test_build_citation_fallback_exhibit_start(self, mock_llm):
        """_build_citation uses first page as fallback for exhibit_start."""
        extractor = VisionExtractor(mock_llm)
        exhibit_context = {
            # No exhibit_start provided
            "total_pages": 74,
        }

        citation = extractor._build_citation(
            page_nums=[1847],
            exhibit_id="25F",
            exhibit_context=exhibit_context,
        )

        # Should fall back to first page number
        assert citation.relative_page == 1  # 1847 - 1847 + 1
        assert citation.absolute_page == 1847

    def test_build_citation_no_total_pages(self, mock_llm):
        """_build_citation works without total_pages."""
        extractor = VisionExtractor(mock_llm)
        exhibit_context = {
            "exhibit_start": 1815,
            # No total_pages
        }

        citation = extractor._build_citation(
            page_nums=[1847],
            exhibit_id="25F",
            exhibit_context=exhibit_context,
        )

        assert citation.total_pages is None
        assert citation.is_valid()  # Still valid without total_pages
