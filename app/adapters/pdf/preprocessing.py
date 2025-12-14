"""
PDF preprocessing utilities.

Infrastructure: scanned page detection and image rendering using PyMuPDF.
Uses domain patterns from core/extraction/court_patterns.py.
"""

import base64
import logging
import re
from typing import Any, Dict, List

import fitz

from app.core.extraction.court_patterns import COURT_HEADER_PATTERNS
from app.core.ports.pdf import PageContent, DocumentAnalysis

logger = logging.getLogger(__name__)

# Detection thresholds
TEXT_THRESHOLD = 150  # Max chars for raw text before density check
DENSITY_THRESHOLD = 100  # Max chars of meaningful text for scanned detection
LARGE_IMAGE_SIZE = 1000  # Min pixels for "large" image


def strip_court_headers(text: str) -> str:
    """Remove court administrative headers from page text.

    Uses patterns from core/extraction/court_patterns.py.

    Args:
        text: Raw page text

    Returns:
        Text with court headers/footers removed
    """
    result = text
    for pattern in COURT_HEADER_PATTERNS:
        result = pattern.sub('', result)

    # Remove excessive whitespace
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def is_scanned_page(
    page: fitz.Page,
    text_threshold: int = TEXT_THRESHOLD,
    density_threshold: int = DENSITY_THRESHOLD
) -> bool:
    """
    Detect if page is scanned (low meaningful text + large image).

    Uses "Content Density Check" strategy:
    1. Extract text from page
    2. Strip known court header/footer patterns
    3. Check if remaining meaningful text is below threshold
    4. Check for large embedded images

    Args:
        page: PyMuPDF page object
        text_threshold: Max chars for raw text before density check
        density_threshold: Max chars of meaningful text for scanned detection

    Returns:
        True if page appears to be scanned content
    """
    raw_text = page.get_text().strip()

    # Quick path: very little raw text
    if len(raw_text) <= text_threshold:
        for img in page.get_images():
            width, height = img[2], img[3]
            if width > LARGE_IMAGE_SIZE and height > LARGE_IMAGE_SIZE:
                return True
        return False

    # Content Density Check: Strip court headers and check remaining
    meaningful_text = strip_court_headers(raw_text)

    if len(meaningful_text) < density_threshold:
        for img in page.get_images():
            width, height = img[2], img[3]
            if width > LARGE_IMAGE_SIZE and height > LARGE_IMAGE_SIZE:
                logger.debug(
                    f"Scanned page detected: {len(raw_text)} raw chars, "
                    f"{len(meaningful_text)} meaningful chars after header strip"
                )
                return True

    return False


def render_page_to_image(page: fitz.Page, dpi: int = 150) -> bytes:
    """Render page to PNG bytes for vision model.

    Args:
        page: PyMuPDF page object
        dpi: Resolution (150 balances quality vs API size limits)

    Returns:
        PNG image as bytes
    """
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


def render_page_to_base64(page: fitz.Page, dpi: int = 150) -> str:
    """Render page to base64-encoded PNG for API payload."""
    png_bytes = render_page_to_image(page, dpi)
    return base64.b64encode(png_bytes).decode("utf-8")


def get_page_content(doc: fitz.Document, page_num: int) -> PageContent:
    """
    Get page content, automatically detecting text vs scanned.

    Args:
        doc: PyMuPDF document
        page_num: 0-indexed page number

    Returns:
        PageContent dataclass with type and content
    """
    page = doc[page_num]

    if is_scanned_page(page):
        return PageContent(
            page_num=page_num + 1,  # 1-indexed for display
            content_type="image",
            content=render_page_to_image(page),
            text_len=len(page.get_text().strip()),
        )
    else:
        return PageContent(
            page_num=page_num + 1,
            content_type="text",
            content=page.get_text(),
            text_len=len(page.get_text().strip()),
        )


def get_pages_content(
    doc: fitz.Document,
    start_page: int,
    end_page: int
) -> Dict[str, Any]:
    """
    Get content for page range, separating text and image pages.

    Args:
        doc: PyMuPDF document
        start_page: 1-indexed start page
        end_page: 1-indexed end page

    Returns:
        Dict with text_pages, image_pages, and has_scanned flag
    """
    text_pages: List[PageContent] = []
    image_pages: List[PageContent] = []

    for page_num in range(start_page - 1, min(end_page, len(doc))):
        content = get_page_content(doc, page_num)
        if content.content_type == "text":
            text_pages.append(content)
        else:
            image_pages.append(content)

    return {
        "text_pages": text_pages,
        "image_pages": image_pages,
        "has_scanned": len(image_pages) > 0,
    }


def analyze_document_content(
    doc: fitz.Document,
    sample_pages: int = 20
) -> DocumentAnalysis:
    """
    Analyze document to determine extraction strategy.

    Args:
        doc: PyMuPDF document
        sample_pages: Number of pages to sample

    Returns:
        DocumentAnalysis with recommendation
    """
    total_pages = len(doc)
    sample_size = min(sample_pages, total_pages)

    scanned_count = 0
    text_count = 0

    for i in range(sample_size):
        if is_scanned_page(doc[i]):
            scanned_count += 1
        else:
            text_count += 1

    scanned_ratio = scanned_count / sample_size if sample_size > 0 else 0

    recommendation = "text"
    if scanned_ratio > 0.5:
        recommendation = "vision"
    elif scanned_ratio > 0.1:
        recommendation = "hybrid"

    return DocumentAnalysis(
        total_pages=total_pages,
        sample_size=sample_size,
        scanned_pages=scanned_count,
        text_pages=text_count,
        scanned_ratio=scanned_ratio,
        requires_vision=scanned_ratio > 0.5,
        recommendation=recommendation,
    )
