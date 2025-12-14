"""Tests for PyMuPDF adapter - direct fitz implementation."""
import pytest
from unittest.mock import MagicMock, patch
from app.adapters.pdf.pymupdf import PyMuPDFAdapter
from app.core.ports.pdf import PDFPort, Bookmark


class TestPyMuPDFAdapterInterface:
    def test_implements_pdf_port(self):
        """Adapter must implement PDFPort interface."""
        adapter = PyMuPDFAdapter()
        assert isinstance(adapter, PDFPort)


class TestPyMuPDFAdapterExtractText:
    def test_extract_text_single_page(self):
        """Should extract text from single page."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page 1 text"

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=10)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.extract_text("test.pdf", 1, 1)

            assert result == "Page 1 text"

    def test_extract_text_page_range(self):
        """Should extract text from page range."""
        pages = ["Page 1", "Page 2", "Page 3"]

        def get_page(idx):
            page = MagicMock()
            page.get_text.return_value = pages[idx]
            return page

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=10)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.__getitem__ = MagicMock(side_effect=get_page)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.extract_text("test.pdf", 1, 3)

            assert "Page 1" in result
            assert "Page 2" in result
            assert "Page 3" in result


class TestPyMuPDFAdapterBookmarks:
    def test_extract_bookmarks_returns_list(self):
        """Should return list of Bookmark objects."""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=100)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.get_toc.return_value = [
            [1, "Section A", 1],
            [2, "1F - Medical Records", 10],
            [2, "2F - Lab Results", 25],
        ]

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            bookmarks = adapter.extract_bookmarks("test.pdf")

            assert len(bookmarks) == 3
            assert all(isinstance(bm, Bookmark) for bm in bookmarks)
            assert bookmarks[0].title == "Section A"
            assert bookmarks[1].page_start == 10


class TestPyMuPDFAdapterRenderPage:
    def test_render_page_returns_png_bytes(self):
        """Should render page as PNG bytes."""
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"\x89PNG\r\n\x1a\n..."

        mock_page = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix

        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.render_page_image("test.pdf", 1)

            assert isinstance(result, bytes)
            assert result.startswith(b"\x89PNG")


class TestPyMuPDFAdapterIsScanned:
    def test_is_scanned_page_low_text(self):
        """Page with low text and large image should be detected as scanned."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Case No. 123"  # Just header
        mock_page.get_images.return_value = [(0, 0, 2000, 2000, 0, 0, 0)]  # Large image

        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.is_scanned_page("test.pdf", 1)

            assert result is True

    def test_is_scanned_page_high_text(self):
        """Page with substantial text should not be scanned."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 500  # Lots of text

        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.is_scanned_page("test.pdf", 1)

            assert result is False


class TestPyMuPDFAdapterPageCount:
    def test_get_page_count(self):
        """Should return page count."""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=42)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.get_page_count("test.pdf")

            assert result == 42
