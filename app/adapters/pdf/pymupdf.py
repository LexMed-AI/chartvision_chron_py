"""PyMuPDF adapter.

Implements PDFPort interface using fitz (PyMuPDF).
Composes preprocessing and bookmarks modules for complex operations.
"""
import logging
from typing import Any, Dict, List

import fitz

from app.core.ports.pdf import PDFPort, Bookmark, PageContent, DocumentAnalysis
from app.core.exceptions import PDFError
from app.adapters.pdf import preprocessing, bookmarks

logger = logging.getLogger(__name__)


class PyMuPDFAdapter(PDFPort):
    """PyMuPDF implementation of PDFPort.

    Directly uses fitz library for PDF operations.
    """

    # Thresholds for scanned page detection
    SCANNED_TEXT_THRESHOLD = 100  # Characters
    LARGE_IMAGE_SIZE = 1000  # Pixels

    def extract_text(self, path: str, start_page: int, end_page: int) -> str:
        """Extract text from page range.

        Args:
            path: Path to PDF file
            start_page: Starting page (1-indexed)
            end_page: Ending page (inclusive)

        Returns:
            Extracted text from all pages joined with newlines
        """
        try:
            with fitz.open(path) as doc:
                parts = []
                # Convert to 0-indexed
                for i in range(start_page - 1, min(end_page, len(doc))):
                    text = doc[i].get_text() or ""
                    parts.append(text)
                return "\n".join(parts)
        except Exception as e:
            raise PDFError(f"Failed to extract text from {path}: {e}") from e

    def extract_bookmarks(self, path: str) -> List[Bookmark]:
        """Extract bookmarks from PDF.

        Args:
            path: Path to PDF file

        Returns:
            List of Bookmark objects with title, pages, and level
        """
        try:
            with fitz.open(path) as doc:
                toc = doc.get_toc()
                page_count = len(doc)

                bookmarks = []
                for i, (level, title, page) in enumerate(toc):
                    # Find next bookmark at same or higher level (sibling/parent)
                    # Skip child bookmarks when calculating end page
                    end_page = page_count
                    for j in range(i + 1, len(toc)):
                        next_level, _, next_page = toc[j]
                        if next_level <= level:
                            # Found sibling or parent - use its start page - 1
                            end_page = next_page - 1
                            break

                    bookmarks.append(Bookmark(
                        title=title,
                        page_start=page,
                        page_end=max(end_page, page),  # Ensure end >= start
                        level=level,
                    ))
                return bookmarks
        except Exception as e:
            raise PDFError(f"Failed to extract bookmarks from {path}: {e}") from e

    def render_page_image(self, path: str, page: int, dpi: int = 150) -> bytes:
        """Render page as PNG image.

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)
            dpi: Resolution for rendering

        Returns:
            PNG image bytes
        """
        try:
            with fitz.open(path) as doc:
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = doc[page - 1].get_pixmap(matrix=mat)
                return pix.tobytes("png")
        except Exception as e:
            raise PDFError(f"Failed to render page {page} from {path}: {e}") from e

    def is_scanned_page(self, path: str, page: int) -> bool:
        """Check if page is scanned (minimal text + large image).

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)

        Returns:
            True if page appears to be a scanned image
        """
        try:
            with fitz.open(path) as doc:
                p = doc[page - 1]
                text = p.get_text() or ""
                text_len = len(text.strip())

                # Quick check: substantial text means not scanned
                if text_len > self.SCANNED_TEXT_THRESHOLD:
                    return False

                # Check for large images (scanned content)
                for img in p.get_images():
                    # img tuple: (xref, smask, width, height, bpc, colorspace, alt_colorspace)
                    width, height = img[2], img[3]
                    if width > self.LARGE_IMAGE_SIZE and height > self.LARGE_IMAGE_SIZE:
                        return True

                return False
        except Exception as e:
            raise PDFError(f"Failed to check page {page} from {path}: {e}") from e

    def get_page_count(self, path: str) -> int:
        """Get total page count.

        Args:
            path: Path to PDF file

        Returns:
            Number of pages in the PDF
        """
        try:
            with fitz.open(path) as doc:
                return len(doc)
        except Exception as e:
            raise PDFError(f"Failed to get page count from {path}: {e}") from e

    def strip_court_headers(self, text: str) -> str:
        """Remove court administrative headers from text.

        Args:
            text: Raw page text

        Returns:
            Text with court headers/footers removed
        """
        return preprocessing.strip_court_headers(text)

    def get_page_content(self, path: str, page: int) -> PageContent:
        """Get text or image content for single page.

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)

        Returns:
            PageContent with type and content
        """
        try:
            with fitz.open(path) as doc:
                return preprocessing.get_page_content(doc, page - 1)
        except Exception as e:
            raise PDFError(f"Failed to get content from page {page} of {path}: {e}") from e

    def get_pages_content(
        self, path: str, start_page: int, end_page: int
    ) -> Dict[str, Any]:
        """Get content for page range, separating text and images.

        Args:
            path: Path to PDF file
            start_page: Starting page (1-indexed)
            end_page: Ending page (inclusive)

        Returns:
            Dict with text_pages, image_pages, and has_scanned flag
        """
        try:
            with fitz.open(path) as doc:
                return preprocessing.get_pages_content(doc, start_page, end_page)
        except Exception as e:
            raise PDFError(f"Failed to get pages content from {path}: {e}") from e

    def analyze_document(self, path: str, sample_pages: int = 20) -> DocumentAnalysis:
        """Analyze document to determine extraction strategy.

        Args:
            path: Path to PDF file
            sample_pages: Number of pages to sample

        Returns:
            DocumentAnalysis with recommendation
        """
        try:
            with fitz.open(path) as doc:
                return preprocessing.analyze_document_content(doc, sample_pages)
        except Exception as e:
            raise PDFError(f"Failed to analyze document {path}: {e}") from e

    def get_exhibit_page_ranges(self, path: str) -> List[Dict[str, Any]]:
        """Get page ranges for all exhibits in PDF.

        Args:
            path: Path to PDF file

        Returns:
            List of dicts with exhibit_id, title, start_page, end_page
        """
        try:
            bms = self.extract_bookmarks(path)
            return bookmarks.get_exhibit_page_ranges(path, bms)
        except Exception as e:
            raise PDFError(f"Failed to get exhibit ranges from {path}: {e}") from e
