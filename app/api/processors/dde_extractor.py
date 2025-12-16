"""
DDE Extraction Service.

Handles extraction of DDE (Disability Determination Explanation) data
from Section A exhibits in ERE documents.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.core.parsers.dde_normalizer import normalize_dde_result

logger = logging.getLogger(__name__)

# Import DDE parser from core
try:
    from app.core.parsers.dde_parser import create_dde_parser

    DDE_PARSER_AVAILABLE = True
except ImportError:
    DDE_PARSER_AVAILABLE = False
    logger.warning("DDEParser not available")


# Patterns that identify Section A DDE documents
DDE_PATTERNS = [
    "DDE",
    "DISABILITY DETERMINATION",
    "RFC ASSESSMENT",
    "RESIDUAL FUNCTIONAL CAPACITY",
    "PRTF",
    "PSYCHIATRIC REVIEW TECHNIQUE",
    "STATE AGENCY",
    "MEDICAL CONSULTANT",
    "PSYCHOLOGICAL CONSULTANT",
    "CASE ANALYSIS",
    "RATIONALE",
    "4734",  # Physical RFC form
]


def is_dde_exhibit(exhibit: Dict[str, Any]) -> bool:
    """
    Check if an exhibit is a DDE document.

    Args:
        exhibit: Exhibit dictionary with 'title' field

    Returns:
        True if exhibit title contains DDE-related patterns
    """
    title = exhibit.get("title", "").upper()
    return any(pattern in title for pattern in DDE_PATTERNS)


def find_latest_dde_exhibit(section_a_exhibits: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find the latest DDE exhibit from Section A.

    Args:
        section_a_exhibits: List of Section A exhibits

    Returns:
        Latest DDE exhibit by page number, or None if no DDE found
    """
    logger.info(f"Searching {len(section_a_exhibits)} Section A exhibits for DDE")
    for e in section_a_exhibits:
        logger.debug(f"  Section A exhibit: {e.get('title', 'No title')[:80]}")

    dde_exhibits = [e for e in section_a_exhibits if is_dde_exhibit(e)]

    if not dde_exhibits:
        logger.warning(
            f"No DDE documents found in Section A. "
            f"Exhibit titles: {[e.get('title', '')[:50] for e in section_a_exhibits]}"
        )
        return None

    # Get the latest DDE by page number (most recent determination)
    return max(dde_exhibits, key=lambda x: x.get("start_page", 0))


async def extract_dde(
    file_path: str,
    section_a_exhibits: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Extract DDE data from Section A exhibits.

    Args:
        file_path: Path to PDF file
        section_a_exhibits: List of Section A exhibits

    Returns:
        Tuple of (normalized_result, raw_result)
        - normalized_result: Flat structure for API responses
        - raw_result: Full parser output for builder (preserves MDIs, determinationHistory)
    """
    if not section_a_exhibits or not DDE_PARSER_AVAILABLE:
        return {}, {}

    try:
        latest_dde = find_latest_dde_exhibit(section_a_exhibits)
        if not latest_dde:
            return {}, {}

        logger.info(
            f"Selected DDE exhibit: {latest_dde.get('title', 'Unknown')[:60]} "
            f"pages {latest_dde.get('start_page')}-{latest_dde.get('end_page')}"
        )

        parser = create_dde_parser()
        raw_result = await parser.parse(
            pdf_path=file_path,
            page_start=latest_dde.get("start_page", 1),
            page_end=latest_dde.get("end_page"),
        )

        extraction_mode = raw_result.get("extraction_mode", "text")
        confidence = raw_result.get("confidence", 0.0)

        # Normalize for API response (flat structure)
        normalized = normalize_dde_result(
            raw_result.get("fields", {}),
            extraction_mode,
            confidence,
        )

        logger.info(f"DDE extraction: confidence={confidence:.2f}, mode={extraction_mode}")
        return normalized, raw_result

    except Exception as e:
        logger.warning(f"DDE extraction failed: {e}")
        return {}, {}


def get_section_exhibits(
    exhibits: List[Dict[str, Any]],
    section_id: str,
) -> List[Dict[str, Any]]:
    """
    Filter exhibits by section ID.

    Args:
        exhibits: List of all exhibits
        section_id: Section letter (A, B, D, E, F)

    Returns:
        List of exhibits matching the section ID
    """
    return [
        e for e in exhibits
        if e.get("section_id", "").upper() == section_id.upper()
    ]
