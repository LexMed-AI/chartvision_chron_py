"""Tests for Citation data model."""
import pytest
from app.core.models.citation import Citation


class TestCitationFormat:
    """Test citation formatting in various styles."""

    def test_format_full_with_exhibit(self):
        """Full format includes exhibit, relative page, and absolute page."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            total_pages=74,
        )
        assert citation.format() == "25F@33 (p.1847)"

    def test_format_estimated_shows_tilde(self):
        """Estimated citations show ~ prefix on relative page."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            is_estimated=True,
        )
        assert citation.format() == "25F@~33 (p.1847)"

    def test_format_page_range(self):
        """Multi-page entries show range."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            end_relative_page=35,
            end_absolute_page=1849,
        )
        assert citation.format() == "25F@33-35 (pp.1847-1849)"

    def test_format_exhibit_style(self):
        """Exhibit-only style for short citations."""
        citation = Citation(
            exhibit_id="5F",
            relative_page=3,
            absolute_page=1847,
        )
        assert citation.format("exhibit") == "Ex. 5F@3"

    def test_format_absolute_style(self):
        """Absolute-only style."""
        citation = Citation(
            exhibit_id="5F",
            relative_page=3,
            absolute_page=1847,
        )
        assert citation.format("absolute") == "p.1847"

    def test_format_no_exhibit_fallback(self):
        """Without exhibit, falls back to absolute page only."""
        citation = Citation(absolute_page=1847)
        assert citation.format() == "p.1847"

    def test_format_bates_number(self):
        """Bates-stamped documents use bates number."""
        citation = Citation(
            absolute_page=1847,
            bates_number="ABC000123",
            source_type="bates",
        )
        assert citation.format() == "ABC000123"


class TestCitationValidation:
    """Test citation validation and edge cases."""

    def test_absolute_page_required(self):
        """Absolute page is always required."""
        with pytest.raises(TypeError):
            Citation()  # Missing absolute_page

    def test_is_valid_with_exhibit(self):
        """Citation with exhibit data is valid."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
        )
        assert citation.is_valid() is True

    def test_is_valid_absolute_only(self):
        """Citation with only absolute page is valid."""
        citation = Citation(absolute_page=1847)
        assert citation.is_valid() is True

    def test_confidence_default(self):
        """Default confidence is 1.0."""
        citation = Citation(absolute_page=1847)
        assert citation.confidence == 1.0
