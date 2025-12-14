"""
Exhibit Normalization.

Converts various exhibit input formats to standard structure.
"""

import logging
from typing import Any, Dict, List, Tuple, Union

logger = logging.getLogger(__name__)


def normalize_exhibits(
    exhibits: Union[List[Tuple[str, str]], List[Dict[str, Any]], Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Normalize exhibit input to standard format with optional vision data.

    Args:
        exhibits: One of:
            - List of (text, id) tuples (legacy format)
            - List of exhibit dicts with text/images (new format from extract_f_exhibits_from_pdf)
            - Dict of {id: text} (legacy format)

    Returns:
        List of exhibit dicts with structure:
        {
            "exhibit_id": str,
            "text": str,
            "images": List[bytes],  # Empty list if no scanned pages
            "has_scanned_pages": bool
        }
    """
    normalized = []

    if isinstance(exhibits, list):
        for item in exhibits:
            if isinstance(item, tuple) and len(item) == 2:
                # Legacy (text, id) tuple format
                text, exhibit_id = item
                normalized.append({
                    "exhibit_id": exhibit_id,
                    "text": text,
                    "images": [],
                    "has_scanned_pages": False,
                })
            elif isinstance(item, dict) and "exhibit_id" in item:
                # New dict format from extract_f_exhibits_from_pdf
                normalized.append({
                    "exhibit_id": item["exhibit_id"],
                    "text": item.get("text", ""),
                    "images": item.get("images", []),
                    "has_scanned_pages": item.get("has_scanned_pages", False),
                    "scanned_page_nums": item.get("scanned_page_nums", []),
                    "page_range": item.get("page_range"),
                })
            else:
                logger.warning(f"Skipping unrecognized exhibit format: {type(item)}")

    elif isinstance(exhibits, dict):
        # Legacy dict format {id: text}
        for key, value in exhibits.items():
            if isinstance(value, str):
                normalized.append({
                    "exhibit_id": key,
                    "text": value,
                    "images": [],
                    "has_scanned_pages": False,
                })

    else:
        raise ValueError(f"Unsupported exhibit format: {type(exhibits)}")

    return normalized


def is_f_section_exhibit(exhibit_text: str, exhibit_id: str) -> bool:
    """
    Determine if exhibit belongs to F-section (medical records).

    Args:
        exhibit_text: The exhibit content
        exhibit_id: The exhibit identifier

    Returns:
        True if this is an F-section exhibit
    """
    # Check exhibit ID for F-section patterns (e.g., "1F", "2F", "10F", "F:" prefix)
    exhibit_id_upper = exhibit_id.upper()
    id_indicates_f = (
        'F:' in exhibit_id_upper or
        exhibit_id_upper.endswith('F') or  # Matches "1F", "2F", etc.
        'F@' in exhibit_id_upper  # Matches "1F@12" format
    )

    # Check content for medical indicators
    text_lower = exhibit_text.lower()
    content_indicates_medical = any([
        'medical' in text_lower,
        'doctor' in text_lower,
        'hospital' in text_lower,
        'treatment' in text_lower,
        'diagnosis' in text_lower,
        'patient' in text_lower,
    ])

    return id_indicates_f or content_indicates_medical
