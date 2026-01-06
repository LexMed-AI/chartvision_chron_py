"""Tests for page-level PDF extraction."""
import pytest

from app.core.extraction.pdf_exhibit_extractor import (
    build_combined_text,
    PageText,
)


class TestBuildCombinedText:
    """Test build_combined_text function."""

    def test_build_combined_text_with_headers(self):
        """Pages with headers use natural text."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="25F - 33 of 74    Medical Evidence\nPatient content...",
                header_info={"source_type": "ere", "confidence": 0.95},
            ),
            PageText(
                absolute_page=1848,
                relative_page=34,
                exhibit_id="25F",
                text="25F - 34 of 74    Medical Evidence\nMore content...",
                header_info={"source_type": "ere", "confidence": 0.95},
            ),
        ]
        combined = build_combined_text(pages)
        assert "25F - 33 of 74" in combined
        assert "25F - 34 of 74" in combined
        assert "[PAGE" not in combined

    def test_build_combined_text_without_headers(self):
        """Pages without headers get markers."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="Patient presented with symptoms...",
                header_info=None,
            ),
            PageText(
                absolute_page=1848,
                relative_page=34,
                exhibit_id="25F",
                text="Lab results showed...",
                header_info=None,
            ),
        ]
        combined = build_combined_text(pages)
        assert "[PAGE 1847]" in combined
        assert "[PAGE 1848]" in combined

    def test_build_combined_text_mixed(self):
        """Mixed pages: some with headers, some without."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="25F - 33 of 74    Header present\nContent...",
                header_info={"source_type": "ere", "confidence": 0.95},
            ),
            PageText(
                absolute_page=1848,
                relative_page=34,
                exhibit_id="25F",
                text="No header on this page\nMore content...",
                header_info=None,
            ),
        ]
        combined = build_combined_text(pages)
        assert "[PAGE 1847]" not in combined
        assert "[PAGE 1848]" in combined

    def test_build_combined_text_low_confidence_header(self):
        """Pages with low confidence headers get markers."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="Some text with uncertain header...",
                header_info={"source_type": "generic", "confidence": 0.3},
            ),
        ]
        combined = build_combined_text(pages)
        # Low confidence (0.3 <= 0.5) should inject marker
        assert "[PAGE 1847]" in combined

    def test_build_combined_text_empty_pages(self):
        """Empty page list returns empty string."""
        combined = build_combined_text([])
        assert combined == ""

    def test_build_combined_text_single_page(self):
        """Single page returns just that page's text."""
        pages = [
            PageText(
                absolute_page=100,
                relative_page=1,
                exhibit_id="1F",
                text="Single page content",
                header_info=None,
            ),
        ]
        combined = build_combined_text(pages)
        assert "[PAGE 100]" in combined
        assert "Single page content" in combined

    def test_build_combined_text_boundary_confidence(self):
        """Test confidence threshold boundary (exactly 0.5)."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="Text at boundary confidence",
                header_info={"source_type": "ere", "confidence": 0.5},
            ),
        ]
        combined = build_combined_text(pages)
        # 0.5 is NOT > 0.5, so marker should be injected
        assert "[PAGE 1847]" in combined

    def test_build_combined_text_just_above_threshold(self):
        """Test confidence just above threshold (0.51)."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="Text just above threshold",
                header_info={"source_type": "ere", "confidence": 0.51},
            ),
        ]
        combined = build_combined_text(pages)
        # 0.51 > 0.5, so no marker
        assert "[PAGE 1847]" not in combined
        assert "Text just above threshold" in combined

    def test_build_combined_text_separates_pages_with_newlines(self):
        """Pages are separated by double newlines."""
        pages = [
            PageText(
                absolute_page=1,
                relative_page=1,
                exhibit_id="1F",
                text="First page",
                header_info={"source_type": "ere", "confidence": 0.9},
            ),
            PageText(
                absolute_page=2,
                relative_page=2,
                exhibit_id="1F",
                text="Second page",
                header_info={"source_type": "ere", "confidence": 0.9},
            ),
        ]
        combined = build_combined_text(pages)
        assert "First page\n\nSecond page" in combined
