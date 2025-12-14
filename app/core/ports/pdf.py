"""PDF port interface.

Defines the contract for PDF operations. Core code depends only on this
abstraction, not on specific implementations like PyMuPDF.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Bookmark:
    """PDF bookmark/outline entry."""
    title: str
    page_start: int
    page_end: int
    level: int


@dataclass
class PageContent:
    """Content extracted from a single page."""
    page_num: int
    content_type: str  # "text" or "image"
    content: Any  # str for text, bytes for image
    text_len: int = 0


@dataclass
class DocumentAnalysis:
    """Analysis of document extraction strategy."""
    total_pages: int
    sample_size: int
    scanned_pages: int
    text_pages: int
    scanned_ratio: float
    requires_vision: bool
    recommendation: str  # "text", "vision", or "hybrid"


class PDFPort(ABC):
    """Abstract interface for PDF operations.

    Implementations: PyMuPDFAdapter
    """

    @abstractmethod
    def extract_text(self, path: str, start_page: int, end_page: int) -> str:
        """Extract text from page range.

        Args:
            path: Path to PDF file
            start_page: Starting page (1-indexed)
            end_page: Ending page (inclusive)

        Returns:
            Extracted text
        """
        pass

    @abstractmethod
    def extract_bookmarks(self, path: str) -> List[Bookmark]:
        """Extract bookmarks/outline from PDF.

        Args:
            path: Path to PDF file

        Returns:
            List of Bookmark objects
        """
        pass

    @abstractmethod
    def render_page_image(self, path: str, page: int, dpi: int = 150) -> bytes:
        """Render page as PNG image.

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)
            dpi: Resolution for rendering

        Returns:
            PNG image bytes
        """
        pass

    @abstractmethod
    def is_scanned_page(self, path: str, page: int) -> bool:
        """Check if page is scanned (minimal text).

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)

        Returns:
            True if page appears to be scanned
        """
        pass

    @abstractmethod
    def get_page_count(self, path: str) -> int:
        """Get total page count.

        Args:
            path: Path to PDF file

        Returns:
            Number of pages
        """
        pass

    @abstractmethod
    def strip_court_headers(self, text: str) -> str:
        """Remove court administrative headers from text.

        Args:
            text: Raw page text

        Returns:
            Text with court headers/footers removed
        """
        pass

    @abstractmethod
    def get_page_content(self, path: str, page: int) -> PageContent:
        """Get text or image content for single page.

        Auto-detects whether page is text-based or scanned.

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)

        Returns:
            PageContent with type and content
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def analyze_document(self, path: str, sample_pages: int = 20) -> DocumentAnalysis:
        """Analyze document to determine extraction strategy.

        Args:
            path: Path to PDF file
            sample_pages: Number of pages to sample

        Returns:
            DocumentAnalysis with recommendation
        """
        pass

    @abstractmethod
    def get_exhibit_page_ranges(self, path: str) -> List[Dict[str, Any]]:
        """Get page ranges for all exhibits in PDF.

        Args:
            path: Path to PDF file

        Returns:
            List of dicts with exhibit_id, title, start_page, end_page
        """
        pass
