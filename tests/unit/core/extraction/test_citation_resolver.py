"""Tests for citation_resolver module."""
import pytest

from app.core.extraction.citation_resolver import (
    CitationResolver,
    ResolvedCitation,
)


class TestResolvedCitation:
    """Test ResolvedCitation dataclass."""

    def test_fields(self):
        """Test ResolvedCitation has expected fields."""
        citation = ResolvedCitation(
            exhibit_id="4F",
            relative_page=3,
            absolute_page=1403,
        )
        assert citation.exhibit_id == "4F"
        assert citation.relative_page == 3
        assert citation.absolute_page == 1403

    def test_immutable(self):
        """Test ResolvedCitation is frozen/immutable."""
        citation = ResolvedCitation("4F", 3, 1403)
        with pytest.raises(AttributeError):
            citation.exhibit_id = "5F"


class TestCitationResolver:
    """Test CitationResolver class."""

    @pytest.fixture
    def sample_ranges(self):
        """Sample exhibit ranges for testing."""
        return [
            {"exhibit_id": "1F", "start_page": 100, "end_page": 110},
            {"exhibit_id": "2F", "start_page": 111, "end_page": 150},
            {"exhibit_id": "3F", "start_page": 151, "end_page": 200},
        ]

    @pytest.fixture
    def resolver(self, sample_ranges):
        """Create resolver with sample ranges."""
        return CitationResolver(sample_ranges)

    def test_init_with_exhibit_ranges(self, resolver):
        """Test initialization builds page index."""
        assert resolver is not None
        # Internal index should be populated
        assert len(resolver._index) > 0

    def test_init_with_empty_ranges(self):
        """Test initialization with empty list."""
        resolver = CitationResolver([])
        assert len(resolver._index) == 0

    def test_init_skips_invalid_ranges(self):
        """Test initialization skips ranges without exhibit_id or start_page."""
        ranges = [
            {"exhibit_id": "", "start_page": 100, "end_page": 110},  # no id
            {"exhibit_id": "2F", "start_page": 0, "end_page": 150},  # no start
            {"exhibit_id": "3F", "start_page": 151, "end_page": 200},  # valid
        ]
        resolver = CitationResolver(ranges)
        # Only the valid range should be indexed
        assert 151 in resolver._index
        assert 100 not in resolver._index

    def test_resolve_returns_citation_for_known_page(self, resolver):
        """Test resolve returns ResolvedCitation for page in exhibit."""
        result = resolver.resolve(105)
        assert result is not None
        assert result.exhibit_id == "1F"
        assert result.relative_page == 6  # 105 - 100 + 1 = 6
        assert result.absolute_page == 105

    def test_resolve_returns_none_for_unknown_page(self, resolver):
        """Test resolve returns None for page not in any exhibit."""
        result = resolver.resolve(50)  # Before any exhibit
        assert result is None

    def test_resolve_first_page_of_exhibit(self, resolver):
        """Test resolve for first page of exhibit has relative_page=1."""
        result = resolver.resolve(100)
        assert result.relative_page == 1
        assert result.exhibit_id == "1F"

    def test_resolve_last_page_of_exhibit(self, resolver):
        """Test resolve for last page of exhibit."""
        result = resolver.resolve(110)
        assert result.relative_page == 11  # 110 - 100 + 1 = 11
        assert result.exhibit_id == "1F"

    def test_format_known_page(self, resolver):
        """Test format returns exhibit citation string."""
        result = resolver.format(105)
        assert result == "Ex. 1F@6 (p.105)"

    def test_format_unknown_page(self, resolver):
        """Test format returns simple page number for unknown page."""
        result = resolver.format(50)
        assert result == "p.50"

    def test_format_range_same_exhibit(self, resolver):
        """Test format_range for pages in same exhibit."""
        result = resolver.format_range(100, 105)
        assert result == "Ex. 1F@1-6 (pp.100-105)"

    def test_format_range_different_exhibits(self, resolver):
        """Test format_range for pages spanning exhibits."""
        result = resolver.format_range(105, 115)  # 1F to 2F
        assert result == "pp.105-115"

    def test_format_range_unknown_pages(self, resolver):
        """Test format_range for unknown pages."""
        result = resolver.format_range(10, 20)
        assert result == "pp.10-20"

    def test_format_range_partial_match(self, resolver):
        """Test format_range where start is known but end is not."""
        result = resolver.format_range(100, 300)  # 1F start, unknown end
        assert result == "pp.100-300"
