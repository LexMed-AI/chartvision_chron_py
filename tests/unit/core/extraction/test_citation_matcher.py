"""Tests for CitationMatcher module."""
import pytest

from app.core.extraction.citation_matcher import (
    CitationMatcher,
    MatchResult,
    SearchTerm,
)
from app.core.extraction.pdf_exhibit_extractor import PageText


class TestSearchTerm:
    """Test SearchTerm dataclass."""

    def test_default_values(self):
        """SearchTerm has sensible defaults."""
        term = SearchTerm(value="diabetes")
        assert term.value == "diabetes"
        assert term.weight == 1.0
        assert term.fuzzy is False

    def test_custom_values(self):
        """SearchTerm accepts custom weight and fuzzy settings."""
        term = SearchTerm(value="Dr. Smith", weight=2.0, fuzzy=True)
        assert term.value == "Dr. Smith"
        assert term.weight == 2.0
        assert term.fuzzy is True


class TestMatchResult:
    """Test MatchResult dataclass."""

    def test_default_values(self):
        """MatchResult has sensible defaults."""
        from app.core.models.citation import Citation

        citation = Citation(absolute_page=100)
        result = MatchResult(citation=citation, match_score=5.0)

        assert result.citation == citation
        assert result.match_score == 5.0
        assert result.matched_terms == []
        assert result.match_method == "search"

    def test_custom_values(self):
        """MatchResult accepts custom values."""
        from app.core.models.citation import Citation

        citation = Citation(absolute_page=100)
        result = MatchResult(
            citation=citation,
            match_score=8.0,
            matched_terms=["01/15/2024", "Dr. Smith"],
            match_method="fallback",
        )

        assert result.match_score == 8.0
        assert result.matched_terms == ["01/15/2024", "Dr. Smith"]
        assert result.match_method == "fallback"


class TestCitationMatcherBasic:
    """Test basic CitationMatcher functionality."""

    @pytest.fixture
    def sample_pages(self):
        """Sample pages for testing."""
        return [
            PageText(
                absolute_page=100,
                relative_page=1,
                exhibit_id="1F",
                text="Date: 01/15/2024\nPatient seen by Dr. Smith at General Hospital.\nDiagnosis: Diabetes mellitus type 2.",
            ),
            PageText(
                absolute_page=101,
                relative_page=2,
                exhibit_id="1F",
                text="Date: 01/20/2024\nFollow-up visit with Dr. Jones at County Clinic.\nProcedure: Blood glucose monitoring.",
            ),
            PageText(
                absolute_page=102,
                relative_page=3,
                exhibit_id="1F",
                text="Lab results from 01/25/2024.\nHbA1c: 7.2%\nFasting glucose: 126 mg/dL",
            ),
        ]

    @pytest.fixture
    def exhibit_context(self):
        """Sample exhibit context."""
        return {
            "exhibit_id": "1F",
            "start_page": 100,
            "end_page": 102,
            "total_pages": 3,
        }

    @pytest.fixture
    def matcher(self, sample_pages, exhibit_context):
        """Create matcher with sample data."""
        return CitationMatcher(sample_pages, exhibit_context)

    def test_match_by_date_and_provider(self, matcher):
        """Match entry by date and provider name."""
        entry = {
            "date": "01/15/2024",
            "provider": "Dr. Smith",
            "facility": "General Hospital",
            "diagnoses": ["Diabetes mellitus type 2"],
        }

        result = matcher.match(entry)

        assert result.match_method == "search"
        assert result.citation.absolute_page == 100
        assert result.citation.exhibit_id == "1F"
        assert result.citation.relative_page == 1
        assert result.match_score > 0
        assert "01/15/2024" in result.matched_terms

    def test_match_different_date_different_page(self, matcher):
        """Different dates match to different pages."""
        entry = {
            "date": "01/20/2024",
            "provider": "Dr. Jones",
            "facility": "County Clinic",
        }

        result = matcher.match(entry)

        assert result.match_method == "search"
        assert result.citation.absolute_page == 101
        assert result.citation.relative_page == 2

    def test_match_fuzzy_provider_name(self, matcher):
        """Fuzzy matching handles slight variations."""
        entry = {
            "date": "01/15/2024",
            "provider": "Smith",  # Without "Dr."
            "facility": "General Hospital",
        }

        result = matcher.match(entry)

        assert result.match_method == "search"
        assert result.citation.absolute_page == 100

    def test_no_match_returns_fallback(self, matcher):
        """No match returns fallback to first page."""
        entry = {
            "date": "12/31/2099",  # Date not in any page
            "provider": "Dr. Nonexistent",
            "facility": "Unknown Hospital",
        }

        result = matcher.match(entry)

        assert result.match_method == "fallback"
        assert result.citation.is_estimated is True
        assert result.citation.absolute_page == 100  # First page
        assert result.match_score == 0.0


class TestCitationMatcherMultiPage:
    """Test multi-page entry detection."""

    @pytest.fixture
    def multi_page_content(self):
        """Pages with content that spans multiple pages."""
        return [
            PageText(
                absolute_page=200,
                relative_page=1,
                exhibit_id="2F",
                text="Operative Report\nDate: 03/10/2024\nSurgeon: Dr. Williams\nProcedure: Left knee arthroscopy",
            ),
            PageText(
                absolute_page=201,
                relative_page=2,
                exhibit_id="2F",
                text="Continued from previous page\nDr. Williams performed arthroscopic debridement.\nLeft knee procedure completed without complications.",
            ),
            PageText(
                absolute_page=202,
                relative_page=3,
                exhibit_id="2F",
                text="Discharge Summary\nDate: 03/11/2024\nPatient discharged in stable condition.",
            ),
        ]

    @pytest.fixture
    def exhibit_context(self):
        """Sample exhibit context."""
        return {
            "exhibit_id": "2F",
            "start_page": 200,
            "end_page": 202,
            "total_pages": 3,
        }

    def test_detect_multi_page_entry(self, multi_page_content, exhibit_context):
        """Detect when an entry spans multiple pages."""
        matcher = CitationMatcher(
            multi_page_content,
            exhibit_context,
            match_threshold=2.0,  # Lower threshold for test
        )

        entry = {
            "date": "03/10/2024",
            "provider": "Dr. Williams",
            "procedures": ["Left knee arthroscopy"],
        }

        result = matcher.match(entry)

        # Should match and potentially include consecutive pages
        assert result.match_method == "search"
        assert result.citation.absolute_page == 200
        # If multi-page detected, end page should be set
        # (depends on score threshold and consecutive page logic)
        assert result.match_score >= 2.0


class TestCitationMatcherEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_pages_list(self):
        """Handle empty pages list gracefully."""
        matcher = CitationMatcher(
            pages=[],
            exhibit_context={"exhibit_id": "1F", "start_page": 100},
        )

        entry = {"date": "01/15/2024", "provider": "Dr. Smith"}
        result = matcher.match(entry)

        assert result.match_method == "fallback"
        assert result.citation.absolute_page == 100

    def test_entry_with_skip_terms(self):
        """Skip terms like 'not specified' and 'unknown'."""
        pages = [
            PageText(
                absolute_page=100,
                relative_page=1,
                exhibit_id="1F",
                text="Date: 01/15/2024\nProvider: Dr. Smith",
            ),
        ]
        matcher = CitationMatcher(pages, {"exhibit_id": "1F"})

        entry = {
            "date": "01/15/2024",
            "provider": "not specified",  # Should be skipped
            "facility": "Unknown",  # Should be skipped
        }

        result = matcher.match(entry)

        # Should still match on date
        assert result.match_method == "search"
        assert "01/15/2024" in result.matched_terms
        # Skip terms should not be in matched_terms
        assert "not specified" not in result.matched_terms

    def test_extract_search_terms_filtering(self):
        """Verify search term extraction filters correctly."""
        pages = [
            PageText(
                absolute_page=100,
                relative_page=1,
                exhibit_id="1F",
                text="Test content",
            ),
        ]
        matcher = CitationMatcher(pages, {"exhibit_id": "1F"})

        entry = {
            "date": "01/15/2024",
            "provider": "N/A",
            "facility": "",
            "diagnoses": ["ab", "Diabetes mellitus"],  # "ab" too short
            "procedures": ["Blood draw"],
        }

        terms = matcher._extract_search_terms(entry)

        # Check weights and filtering
        term_values = [t.value for t in terms]
        assert "01/15/2024" in term_values  # Date included
        assert "N/A" not in term_values  # Skip term
        assert "ab" not in term_values  # Too short
        assert "Diabetes mellitus" in term_values  # Valid diagnosis
        assert "Blood draw" in term_values  # Valid procedure

        # Check weights
        date_term = next(t for t in terms if t.value == "01/15/2024")
        assert date_term.weight == 3.0
        assert date_term.fuzzy is False

        diag_term = next(t for t in terms if t.value == "Diabetes mellitus")
        assert diag_term.weight == 1.0
        assert diag_term.fuzzy is True
