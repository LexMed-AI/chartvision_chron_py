"""Tests for slim ChronologyEngine orchestrator."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extraction.engine import ChronologyEngine


class TestChronologyEngine:
    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value='[{"date": "2024-01-15", "exhibit_reference": "1F", "visit_type": "office_visit", "occurrence_treatment": {}}]'
        )
        return llm

    @pytest.fixture
    def engine(self, mock_llm):
        return ChronologyEngine(llm_manager=mock_llm)

    @pytest.mark.asyncio
    async def test_process_exhibit(self, engine):
        """Test basic exhibit processing returns entries."""
        entries = await engine.process_exhibit("Sample text", "1F", [100, 101])
        assert len(entries) >= 1
        assert entries[0]["date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_citations_injected_when_resolver_set(self, engine):
        """Test that CitationResolver overrides LLM citation guesses."""
        engine.set_exhibit_ranges([
            {"exhibit_id": "1F", "start_page": 100, "end_page": 110, "title": "Medical Records"}
        ])
        entries = await engine.process_exhibit("Sample text", "1F", [105])
        # 105 - 100 + 1 = page 6 within exhibit 1F
        assert "Ex. 1F@6" in entries[0]["exhibit_reference"]

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self, engine):
        """Test empty text returns no entries."""
        entries = await engine.process_exhibit("", "1F", [100])
        assert entries == []

    @pytest.mark.asyncio
    async def test_process_multiple_exhibits(self, engine):
        """Test processing multiple exhibits in batch."""
        exhibits = [
            {"text": "Sample 1", "exhibit_id": "1F", "pages": [100]},
            {"text": "Sample 2", "exhibit_id": "2F", "pages": [200]},
        ]
        entries = await engine.process_exhibits(exhibits)
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_page_range_set_for_multipage(self, engine):
        """Test page_range is set when multiple source pages."""
        engine.set_exhibit_ranges([
            {"exhibit_id": "1F", "start_page": 100, "end_page": 120, "title": "Medical"}
        ])
        entries = await engine.process_exhibit("Sample", "1F", [105, 106, 107])
        assert entries[0].get("page_range") == "105-107"
