"""
ERE exhibit and section identification.

Domain logic for identifying SSA disability case structure from bookmarks.
These are pure functions operating on the Bookmark model from ports/pdf.py.
"""

import re
from typing import Dict, List, Optional

from app.core.ports.pdf import Bookmark

# ERE-specific exhibit patterns (domain knowledge)
EXHIBIT_PATTERNS = [
    r"\d+[A-F]\s*[-:]",      # "1F:", "2A:", "1F -", etc.
    r"Exhibit\s+[A-Z0-9]+",
    r"Ex\.\s*[A-Z0-9]+",
    r"Attachment\s+[A-Z0-9]+",
    r"Appendix\s+[A-Z0-9]+",
    r"Tab\s+[A-Z0-9]+",
]

# SSA section patterns (domain knowledge)
SECTION_PATTERNS = {
    "A": r"^[A-Z]?\.\s*Payment|Section\s*A|^\s*A\.",
    "B": r"^[A-Z]?\.\s*Jurisdictional|Section\s*B|^\s*B\.",
    "D": r"^[A-Z]?\.\s*Earnings|Section\s*D|^\s*D\.",
    "E": r"^[A-Z]?\.\s*Disability|Section\s*E|^\s*E\.",
    "F": r"^[A-Z]?\.\s*Medical|Section\s*F|^\s*F\.",
}


def find_exhibits(
    bookmarks: List[Bookmark],
    patterns: Optional[List[str]] = None
) -> List[Bookmark]:
    """
    Find bookmarks that represent exhibits.

    Args:
        bookmarks: List of Bookmark objects from PDFPort
        patterns: Optional custom regex patterns (defaults to EXHIBIT_PATTERNS)

    Returns:
        List of bookmarks identified as exhibits
    """
    if patterns is None:
        patterns = EXHIBIT_PATTERNS

    exhibit_bookmarks = []

    for bookmark in bookmarks:
        for pattern in patterns:
            if re.search(pattern, bookmark.title, re.IGNORECASE):
                exhibit_bookmarks.append(bookmark)
                break

    return exhibit_bookmarks


def find_sections(bookmarks: List[Bookmark]) -> Dict[str, List[Bookmark]]:
    """
    Find ERE sections (A, B, D, E, F) from bookmarks.

    Args:
        bookmarks: List of Bookmark objects from PDFPort

    Returns:
        Dictionary mapping section letters to their bookmarks
    """
    sections: Dict[str, List[Bookmark]] = {k: [] for k in SECTION_PATTERNS}

    for bookmark in bookmarks:
        for section, pattern in SECTION_PATTERNS.items():
            if re.search(pattern, bookmark.title, re.IGNORECASE):
                sections[section].append(bookmark)
                break

    return sections


def extract_exhibit_id(title: str) -> str:
    """
    Extract exhibit ID from bookmark title.

    Args:
        title: Bookmark title like "1F: Medical Records from Dr. Smith"

    Returns:
        Exhibit ID like "1F" or first 10 chars if no match
    """
    match = re.match(r"(\d+[A-F])", title)
    return match.group(1) if match else title[:10]


def is_medical_exhibit(bookmark: Bookmark) -> bool:
    """
    Check if bookmark represents a medical exhibit (F section).

    Args:
        bookmark: Bookmark object

    Returns:
        True if this is an F-section exhibit (medical records)
    """
    return bool(re.match(r"\d+F", bookmark.title))
