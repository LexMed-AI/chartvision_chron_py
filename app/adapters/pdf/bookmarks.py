"""
PDF bookmark analysis utilities.

Infrastructure: bookmark structure analysis using PyMuPDF.
Domain logic for exhibit/section finding is in core/extraction/exhibit_finder.py.
"""

import re
import logging
from typing import Any, Dict, List

import fitz

from app.core.ports.pdf import Bookmark
from app.core.models.bookmark import BookmarkTree
from app.core.extraction.exhibit_finder import find_exhibits, extract_exhibit_id

logger = logging.getLogger(__name__)


def analyze_structure(bookmarks: List[Bookmark], page_count: int) -> BookmarkTree:
    """
    Build bookmark tree with analysis metadata.

    Args:
        bookmarks: List of Bookmark objects
        page_count: Total pages in document

    Returns:
        BookmarkTree with hierarchy stats
    """
    if not bookmarks:
        return BookmarkTree(
            root_bookmarks=[],
            total_bookmarks=0,
            max_depth=0,
            page_count=page_count,
        )

    # Find root bookmarks (level 1)
    root_bookmarks = [bm for bm in bookmarks if bm.level == 1]
    max_depth = max((bm.level for bm in bookmarks), default=0)

    return BookmarkTree(
        root_bookmarks=root_bookmarks,
        total_bookmarks=len(bookmarks),
        max_depth=max_depth,
        page_count=page_count,
    )


def map_to_content(
    pdf_path: str,
    bookmarks: List[Bookmark]
) -> Dict[str, Dict[str, Any]]:
    """
    Map bookmarks to page ranges and content sections.

    Args:
        pdf_path: Path to PDF file
        bookmarks: List of Bookmark objects

    Returns:
        Dict mapping bookmark titles to page range info
    """
    if not bookmarks:
        return {}

    content_map = {}

    for bookmark in bookmarks:
        content_map[bookmark.title] = {
            "start_page": bookmark.page_start,
            "end_page": bookmark.page_end,
            "page_count": max(1, bookmark.page_end - bookmark.page_start + 1),
            "level": bookmark.level,
        }

    return content_map


def get_exhibit_page_ranges(
    pdf_path: str,
    bookmarks: List[Bookmark]
) -> List[Dict[str, Any]]:
    """
    Get page ranges for all exhibits in the PDF.

    Uses domain logic from core/extraction/exhibit_finder.py.

    Args:
        pdf_path: Path to PDF file
        bookmarks: List of Bookmark objects

    Returns:
        List of exhibit info dicts with exhibit_id, title, start_page, end_page
    """
    if not bookmarks:
        return []

    # Use domain logic to find exhibits
    exhibits = find_exhibits(bookmarks)

    result = []
    for exhibit in exhibits:
        exhibit_id = extract_exhibit_id(exhibit.title)

        result.append({
            "exhibit_id": exhibit_id,
            "title": exhibit.title,
            "start_page": exhibit.page_start,
            "end_page": exhibit.page_end,
            "page_count": max(1, exhibit.page_end - exhibit.page_start + 1),
            "level": exhibit.level,
        })

    return sorted(result, key=lambda x: x["start_page"])
