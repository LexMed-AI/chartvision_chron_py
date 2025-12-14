"""Tests for vision-based extraction from scanned pages."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extraction.vision_extractor import VisionExtractor
from app.core.extraction.template_loader import get_template_loader


def test_template_loader_provides_prompts():
    """Verify TemplateLoader provides system and user prompts for vision."""
    loader = get_template_loader()
    base = loader.get_base()

    assert base is not None
    assert base != {}  # Should not be empty
    assert "system_prompt" in base


class TestVisionExtractor:
    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate_with_vision = AsyncMock(
            return_value='[{"date": "2024-01-15", "exhibit_reference": "1F", "visit_type": "office_visit", "occurrence_treatment": {}}]'
        )
        return llm

    @pytest.fixture
    def extractor(self, mock_llm):
        return VisionExtractor(llm_manager=mock_llm)

    @pytest.mark.asyncio
    async def test_extract_from_images(self, extractor):
        """Test vision extraction returns entries from images."""
        entries = await extractor.extract([b"fake_png"], "1F", [100])
        assert len(entries) == 1
        assert entries[0]["date"] == "2024-01-15"
        assert entries[0]["exhibit_reference"] == "1F"

    @pytest.mark.asyncio
    async def test_empty_images_returns_empty(self, extractor):
        """Test empty image list returns empty list."""
        entries = await extractor.extract([], "1F", [])
        assert entries == []

    @pytest.mark.asyncio
    async def test_exhibit_id_injected_on_missing(self, extractor, mock_llm):
        """Test exhibit_id is injected when missing from entry."""
        mock_llm.generate_with_vision = AsyncMock(
            return_value='[{"date": "2024-01-15", "visit_type": "lab_result"}]'
        )
        entries = await extractor.extract([b"png"], "2F", [200])
        assert entries[0]["exhibit_reference"] == "2F"

    @pytest.mark.asyncio
    async def test_batching_large_image_sets(self, extractor, mock_llm):
        """Test that large image sets are processed in batches."""
        # Create 25 images (should be 3 batches with batch_size=10)
        images = [b"img"] * 25
        page_nums = list(range(1, 26))

        entries = await extractor.extract(images, "3F", page_nums)

        # Should have called generate_with_vision 3 times (10+10+5)
        assert mock_llm.generate_with_vision.call_count == 3
