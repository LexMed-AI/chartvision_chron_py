"""Tests for PDF port interface."""
import pytest
from app.core.ports.pdf import PDFPort, Bookmark, PageContent, DocumentAnalysis


class TestBookmark:
    def test_bookmark_fields(self):
        bm = Bookmark(
            title="1F",
            page_start=10,
            page_end=25,
            level=1,
        )
        assert bm.title == "1F"
        assert bm.page_start == 10
        assert bm.page_end == 25


class TestPDFPortInterface:
    def test_cannot_instantiate_abstract_port(self):
        with pytest.raises(TypeError):
            PDFPort()

    def test_concrete_implementation_works(self):
        class MockPDF(PDFPort):
            def extract_text(self, path, start_page, end_page) -> str:
                return "mock text"

            def extract_bookmarks(self, path):
                return [Bookmark("1F", 1, 10, 1)]

            def render_page_image(self, path, page, dpi=150) -> bytes:
                return b"mock image"

            def is_scanned_page(self, path, page) -> bool:
                return False

            def get_page_count(self, path) -> int:
                return 100

            def strip_court_headers(self, text) -> str:
                return text

            def get_page_content(self, path, page) -> PageContent:
                return PageContent(page_num=page, content_type="text", content="text")

            def get_pages_content(self, path, start_page, end_page):
                return {"text_pages": [], "image_pages": [], "has_scanned": False}

            def analyze_document(self, path, sample_pages=20) -> DocumentAnalysis:
                return DocumentAnalysis(
                    total_pages=100, sample_size=20, scanned_pages=0,
                    text_pages=20, scanned_ratio=0.0, requires_vision=False,
                    recommendation="text"
                )

            def get_exhibit_page_ranges(self, path):
                return []

        mock = MockPDF()
        assert mock.extract_text("test.pdf", 1, 10) == "mock text"
        assert len(mock.extract_bookmarks("test.pdf")) == 1
