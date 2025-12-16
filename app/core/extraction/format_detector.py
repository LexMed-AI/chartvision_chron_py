"""
ERE Format Detection.

Detects the type of ERE (Electronic Records Express) PDF:
- RAW_SSA: Direct SSA export (~94% searchable, page bookmarks with exhibit prefix)
- PROCESSED: Third-party processed (100% searchable, Table of Contents)
- COURT_TRANSCRIPT: Federal court filing (images only, C-prefix exhibits)

Detection is additive - stores format as metadata without changing processing.
Future optimizations can use this to route extraction appropriately.
"""
import logging
import re
from typing import List, Tuple

import fitz

logger = logging.getLogger(__name__)

# ERE format types
RAW_SSA = "RAW_SSA"
PROCESSED = "PROCESSED"
COURT_TRANSCRIPT = "COURT_TRANSCRIPT"
UNKNOWN = "UNKNOWN"


def detect_ere_format(pdf_path: str) -> str:
    """
    Detect ERE format type from PDF structure.

    Uses bookmark patterns to identify format:
    - Court Transcript: C-prefix exhibits, "Certification Page" bookmark
    - Processed: First bookmark is "Table of Contents"
    - Raw SSA: Default (section headers with "Section X." format)

    Args:
        pdf_path: Path to PDF file

    Returns:
        Format type: RAW_SSA, PROCESSED, COURT_TRANSCRIPT, or UNKNOWN
    """
    try:
        with fitz.open(pdf_path) as doc:
            toc = doc.get_toc()

            if not toc:
                logger.warning(f"No bookmarks found in {pdf_path}")
                return UNKNOWN

            detected = _detect_from_bookmarks(toc)
            logger.info(f"Detected ERE format: {detected} for {pdf_path}")
            return detected

    except Exception as e:
        logger.warning(f"Format detection failed for {pdf_path}: {e}")
        return UNKNOWN


def _detect_from_bookmarks(toc: List[Tuple[int, str, int]]) -> str:
    """
    Detect format from table of contents structure.

    Args:
        toc: List of (level, title, page) tuples from PDF

    Returns:
        Detected format type
    """
    if not toc:
        return UNKNOWN

    first_bookmark = toc[0][1] if toc else ""
    first_five = [t[1].lower() for t in toc[:5]]

    # Court Transcript detection (check first - most distinctive)
    if _is_court_transcript(toc, first_five):
        return COURT_TRANSCRIPT

    # Processed detection (Table of Contents as first bookmark)
    if _is_processed(first_bookmark, toc):
        return PROCESSED

    # Default to Raw SSA
    return RAW_SSA


def _is_court_transcript(
    toc: List[Tuple[int, str, int]],
    first_five_lower: List[str]
) -> bool:
    """
    Check if PDF is a court transcript.

    Markers:
    - Has "Certification Page" or "Court Transcript Index" in first 5 bookmarks
    - Level 2 exhibits have C prefix (C1F, C22F, etc.)
    - Section headers are descriptive ("Medical Records" not "F. Medical")
    """
    # Check for court-specific bookmarks
    has_certification = any("certification" in t for t in first_five_lower)
    has_court_index = any("court" in t and "index" in t for t in first_five_lower)

    if has_certification or has_court_index:
        return True

    # Check for C-prefix exhibits (C1F, C22F, etc.)
    c_prefix_pattern = re.compile(r"^C\d+[A-F]\s*-", re.IGNORECASE)
    level_2_bookmarks = [t[1] for t in toc if t[0] == 2]

    c_prefix_count = sum(1 for title in level_2_bookmarks if c_prefix_pattern.match(title))
    if c_prefix_count >= 3:  # Multiple C-prefix exhibits = court transcript
        return True

    return False


def _is_processed(first_bookmark: str, toc: List[Tuple[int, str, int]]) -> bool:
    """
    Check if PDF is a processed ERE (Assure, Atlas, Chronicle Legal).

    Markers:
    - First bookmark is "Table of Contents"
    - Page bookmarks lack exhibit ID prefix: "(page X of Y)" not "1F (Page X of Y)"
    """
    # Table of Contents as first bookmark
    if first_bookmark.lower() == "table of contents":
        return True

    # Check for lowercase page bookmarks without exhibit prefix
    # Processed: "(page 1 of 235)"
    # Raw SSA: "1F (Page 1 of 4)"
    page_bookmark_pattern = re.compile(r"^\(page\s+\d+\s+of\s+\d+\)", re.IGNORECASE)

    level_3_bookmarks = [t[1] for t in toc if t[0] == 3]
    lowercase_page_bookmarks = sum(
        1 for title in level_3_bookmarks[:20]
        if page_bookmark_pattern.match(title) and title.startswith("(")
    )

    # If we have lowercase page bookmarks starting with "(", it's processed
    if lowercase_page_bookmarks >= 3:
        return True

    return False


def get_format_characteristics(format_type: str) -> dict:
    """
    Get processing characteristics for a format type.

    Returns dict with recommended settings for the format.
    This is informational - not enforced by current processing.

    Args:
        format_type: RAW_SSA, PROCESSED, or COURT_TRANSCRIPT

    Returns:
        Dict with format characteristics
    """
    characteristics = {
        RAW_SSA: {
            "text_searchable_pct": 94,
            "has_page_bookmarks": True,
            "page_bookmark_has_exhibit_id": True,
            "recommended_extraction": "text_with_vision_fallback",
            "vision_expected_pct": 6,
        },
        PROCESSED: {
            "text_searchable_pct": 100,
            "has_page_bookmarks": True,
            "page_bookmark_has_exhibit_id": False,
            "recommended_extraction": "text_only",
            "vision_expected_pct": 0,
        },
        COURT_TRANSCRIPT: {
            "text_searchable_pct": 0,
            "has_page_bookmarks": False,
            "page_bookmark_has_exhibit_id": False,
            "recommended_extraction": "vision_only",
            "vision_expected_pct": 100,
        },
        UNKNOWN: {
            "text_searchable_pct": None,
            "has_page_bookmarks": None,
            "page_bookmark_has_exhibit_id": None,
            "recommended_extraction": "text_with_vision_fallback",
            "vision_expected_pct": None,
        },
    }

    return characteristics.get(format_type, characteristics[UNKNOWN])
