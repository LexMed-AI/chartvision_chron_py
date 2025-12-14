"""Tests for LLM response parsing with truncation recovery."""
import pytest
from app.core.extraction.response_parser import ResponseParser


class TestResponseParser:
    """Test JSON parsing from LLM responses."""

    @pytest.fixture
    def parser(self):
        return ResponseParser()

    def test_parse_clean_json_array(self, parser):
        response = '[{"date": "2024-01-15", "provider": "Dr. Smith"}]'
        result = parser.parse(response)
        assert len(result) == 1
        assert result[0]["date"] == "2024-01-15"

    def test_parse_markdown_code_block(self, parser):
        response = '```json\n[{"date": "2024-01-15"}]\n```'
        result = parser.parse(response)
        assert len(result) == 1

    def test_recover_truncated_array(self, parser):
        response = '[{"date": "2024-01-15", "provider": "Dr. Smith"}, {"date": "2024-02'
        result = parser.parse(response)
        assert len(result) == 1  # First complete entry recovered

    def test_parse_entries_wrapper(self, parser):
        response = '{"entries": [{"date": "2024-01-15"}]}'
        result = parser.parse(response)
        assert len(result) == 1

    def test_parse_empty_returns_empty_list(self, parser):
        assert parser.parse("") == []
        assert parser.parse("No data found.") == []
