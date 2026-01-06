"""Tests for ParallelExtractor exhibit context passing."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extraction.parallel_extractor import ParallelExtractor


class TestParallelExtractorContext:
    """Tests for exhibit context passing to extractors."""

    @pytest.fixture
    def mock_text_extractor(self):
        """Create mock text extractor with async extract method."""
        extractor = MagicMock()
        extractor.extract = AsyncMock(return_value=[
            {"date": "2019-03-15", "provider": "Dr. Smith"}
        ])
        return extractor

    @pytest.fixture
    def mock_vision_extractor(self):
        """Create mock vision extractor with async extract method."""
        extractor = MagicMock()
        extractor.extract = AsyncMock(return_value=[
            {"date": "2019-03-16", "provider": "Dr. Jones"}
        ])
        return extractor

    @pytest.mark.asyncio
    async def test_passes_exhibit_context_to_text_extractor(
        self, mock_text_extractor, mock_vision_extractor
    ):
        """ParallelExtractor passes exhibit context to TextExtractor."""
        parallel = ParallelExtractor(
            text_extractor=mock_text_extractor,
            vision_extractor=mock_vision_extractor,
        )

        exhibit = {
            "exhibit_id": "25F",
            "pages": [],
            "text": "Medical text...",
            "combined_text": "Medical text...",
            "page_range": (1815, 1888),
            "images": [],
            "scanned_page_nums": [],
            "has_scanned_pages": False,
        }

        await parallel._process_exhibit(exhibit)

        # Verify context was passed
        mock_text_extractor.extract.assert_called_once()
        call_kwargs = mock_text_extractor.extract.call_args.kwargs
        assert "exhibit_context" in call_kwargs
        assert call_kwargs["exhibit_context"]["exhibit_id"] == "25F"
        assert call_kwargs["exhibit_context"]["exhibit_start"] == 1815
        assert call_kwargs["exhibit_context"]["exhibit_end"] == 1888
        assert call_kwargs["exhibit_context"]["total_pages"] == 74

    @pytest.mark.asyncio
    async def test_passes_exhibit_context_to_vision_extractor(
        self, mock_text_extractor, mock_vision_extractor
    ):
        """ParallelExtractor passes exhibit context to VisionExtractor."""
        parallel = ParallelExtractor(
            text_extractor=mock_text_extractor,
            vision_extractor=mock_vision_extractor,
        )

        exhibit = {
            "exhibit_id": "25F",
            "pages": [],
            "text": "",
            "combined_text": "",
            "page_range": (1815, 1888),
            "images": [b"fake_image"],
            "scanned_page_nums": [1815],
            "has_scanned_pages": True,
        }

        await parallel._process_exhibit(exhibit)

        # Verify context was passed
        mock_vision_extractor.extract.assert_called_once()
        call_kwargs = mock_vision_extractor.extract.call_args.kwargs
        assert "exhibit_context" in call_kwargs
        assert call_kwargs["exhibit_context"]["exhibit_id"] == "25F"
        assert call_kwargs["exhibit_context"]["exhibit_start"] == 1815
        assert call_kwargs["exhibit_context"]["exhibit_end"] == 1888
        assert call_kwargs["exhibit_context"]["total_pages"] == 74

    @pytest.mark.asyncio
    async def test_passes_pages_to_text_extractor(
        self, mock_text_extractor, mock_vision_extractor
    ):
        """ParallelExtractor passes pages list to TextExtractor."""
        parallel = ParallelExtractor(
            text_extractor=mock_text_extractor,
            vision_extractor=mock_vision_extractor,
        )

        mock_pages = [
            MagicMock(page_num=1815, text="Page 1 text"),
            MagicMock(page_num=1816, text="Page 2 text"),
        ]

        exhibit = {
            "exhibit_id": "25F",
            "pages": mock_pages,
            "text": "Medical text...",
            "page_range": (1815, 1888),
            "images": [],
            "scanned_page_nums": [],
        }

        await parallel._process_exhibit(exhibit)

        # Verify pages was passed
        call_kwargs = mock_text_extractor.extract.call_args.kwargs
        assert "pages" in call_kwargs
        assert call_kwargs["pages"] == mock_pages

    @pytest.mark.asyncio
    async def test_build_exhibit_context_with_valid_range(self):
        """Test _build_exhibit_context builds correct context from page_range."""
        parallel = ParallelExtractor(
            text_extract_fn=AsyncMock(return_value=[]),
        )

        exhibit = {
            "exhibit_id": "10F",
            "page_range": (100, 150),
        }

        context = parallel._build_exhibit_context(exhibit)

        assert context["exhibit_id"] == "10F"
        assert context["exhibit_start"] == 100
        assert context["exhibit_end"] == 150
        assert context["total_pages"] == 51

    @pytest.mark.asyncio
    async def test_build_exhibit_context_with_missing_range(self):
        """Test _build_exhibit_context handles missing page_range."""
        parallel = ParallelExtractor(
            text_extract_fn=AsyncMock(return_value=[]),
        )

        exhibit = {
            "exhibit_id": "5F",
        }

        context = parallel._build_exhibit_context(exhibit)

        assert context["exhibit_id"] == "5F"
        assert context["exhibit_start"] == 0
        assert context["exhibit_end"] == 0
        assert context["total_pages"] == 0

    @pytest.mark.asyncio
    async def test_build_exhibit_context_with_zero_start(self):
        """Test _build_exhibit_context handles zero start page correctly."""
        parallel = ParallelExtractor(
            text_extract_fn=AsyncMock(return_value=[]),
        )

        exhibit = {
            "exhibit_id": "1F",
            "page_range": (0, 10),
        }

        context = parallel._build_exhibit_context(exhibit)

        assert context["exhibit_id"] == "1F"
        assert context["exhibit_start"] == 0
        assert context["exhibit_end"] == 10
        # total_pages should be 11 (10 - 0 + 1), not 0
        assert context["total_pages"] == 11

    @pytest.mark.asyncio
    async def test_function_based_extraction_still_works(self):
        """Test that function-based extraction (legacy) still works."""
        text_fn_called = []
        vision_fn_called = []

        async def mock_text_fn(text, exhibit_id):
            text_fn_called.append((text, exhibit_id))
            return [{"date": "2024-01-01"}]

        async def mock_vision_fn(images, exhibit_id, page_nums):
            vision_fn_called.append((images, exhibit_id, page_nums))
            return [{"date": "2024-01-02"}]

        parallel = ParallelExtractor(
            text_extract_fn=mock_text_fn,
            vision_extract_fn=mock_vision_fn,
        )

        exhibit = {
            "exhibit_id": "1F",
            "text": "Test text",
            "images": [b"img"],
            "page_range": (1, 10),
        }

        result = await parallel._process_exhibit(exhibit)

        # Legacy function-based approach should still be called
        assert len(text_fn_called) == 1
        assert text_fn_called[0] == ("Test text", "1F")
        assert len(vision_fn_called) == 1
        assert vision_fn_called[0][1] == "1F"  # exhibit_id
        assert len(result.entries) == 2

    @pytest.mark.asyncio
    async def test_object_based_extractors_take_precedence(
        self, mock_text_extractor, mock_vision_extractor
    ):
        """Test that object-based extractors are preferred over function-based."""
        legacy_called = []

        async def legacy_fn(text, exhibit_id):
            legacy_called.append(exhibit_id)
            return []

        parallel = ParallelExtractor(
            text_extract_fn=legacy_fn,  # Legacy
            text_extractor=mock_text_extractor,  # Object-based (preferred)
            vision_extractor=mock_vision_extractor,
        )

        exhibit = {
            "exhibit_id": "1F",
            "text": "Test text",
            "images": [],
            "page_range": (1, 10),
        }

        await parallel._process_exhibit(exhibit)

        # Object-based should be used, not legacy
        assert len(legacy_called) == 0
        mock_text_extractor.extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_includes_all_required_fields(
        self, mock_text_extractor, mock_vision_extractor
    ):
        """Test that exhibit context contains all required fields."""
        parallel = ParallelExtractor(
            text_extractor=mock_text_extractor,
            vision_extractor=mock_vision_extractor,
        )

        exhibit = {
            "exhibit_id": "15F",
            "text": "Some medical content",
            "page_range": (500, 550),
            "images": [],
        }

        await parallel._process_exhibit(exhibit)

        call_kwargs = mock_text_extractor.extract.call_args.kwargs
        context = call_kwargs["exhibit_context"]

        # Verify all required fields are present
        required_fields = ["exhibit_id", "exhibit_start", "exhibit_end", "total_pages"]
        for field in required_fields:
            assert field in context, f"Missing required field: {field}"

        # Verify values are correct
        assert context["exhibit_id"] == "15F"
        assert context["exhibit_start"] == 500
        assert context["exhibit_end"] == 550
        assert context["total_pages"] == 51
