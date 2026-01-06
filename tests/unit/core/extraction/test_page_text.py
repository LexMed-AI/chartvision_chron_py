"""Tests for PageText dataclass."""

from app.core.extraction.pdf_exhibit_extractor import PageText


class TestPageText:
    """Tests for PageText data structure."""

    def test_create_page_text(self):
        """PageText holds page content with metadata."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Patient presented with chest pain...",
        )
        assert page.absolute_page == 1847
        assert page.relative_page == 33
        assert page.exhibit_id == "25F"
        assert "chest pain" in page.text

    def test_header_info_optional(self):
        """Header info is optional."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Content here",
        )
        assert page.header_info is None

    def test_with_header_info(self):
        """PageText can store detected header info."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Content here",
            header_info={
                "source_type": "ere",
                "confidence": 0.95,
                "raw_match": "25F - 33 of 74",
            },
        )
        assert page.header_info["source_type"] == "ere"
        assert page.header_info["confidence"] == 0.95
