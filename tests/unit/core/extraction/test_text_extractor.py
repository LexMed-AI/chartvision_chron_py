"""Tests for LLM-based text extraction."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extraction.text_extractor import TextExtractor
from app.core.extraction.template_loader import get_template_loader


def test_template_loader_provides_prompts():
    """Verify TemplateLoader provides system and user prompts."""
    loader = get_template_loader()
    base = loader.get_base()

    assert base is not None
    assert base != {}  # Should not be empty
    assert "system_prompt" in base
    assert "user_prompt" in base


class TestTextExtractor:
    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value='[{"date": "2024-01-15", "exhibit_reference": "1F", "visit_type": "office_visit", "provider": "Dr. Smith", "facility": "Clinic", "occurrence_treatment": {}}]')
        return llm

    @pytest.fixture
    def extractor(self, mock_llm):
        return TextExtractor(llm_manager=mock_llm)

    @pytest.mark.asyncio
    async def test_extract_returns_entries(self, extractor):
        entries = await extractor.extract("Patient seen for back pain.", "1F")
        assert len(entries) == 1
        assert entries[0]["date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_validates_visit_type(self, extractor):
        extractor._llm.generate = AsyncMock(
            return_value='[{"date": "2024-01-15", "exhibit_reference": "1F", "visit_type": "invalid", "occurrence_treatment": {}}]'
        )
        entries = await extractor.extract("text", "1F")
        assert entries[0]["visit_type"] == "office_visit"  # Defaults to office_visit

    @pytest.mark.asyncio
    async def test_requires_date(self, extractor):
        extractor._llm.generate = AsyncMock(
            return_value='[{"exhibit_reference": "1F", "visit_type": "office_visit"}]'
        )
        entries = await extractor.extract("text", "1F")
        assert len(entries) == 0  # Filtered out
