"""
Chronology Utilities - Stateless helper functions for medical chronology processing.

Provides utility functions for:
- Exhibit normalization and detection
- Statistics calculation
- PDF exhibit extraction

Version: 3.1.0 - Removed dead code
"""

import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Memory limits for image extraction
MAX_IMAGES_PER_EXHIBIT = 20  # Prevent memory exhaustion from large scanned exhibits


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


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime (internal helper)."""
    if not date_str:
        return None
    try:
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y']:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def calculate_confidence(
    data_completeness: float,
    providers: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]]
) -> float:
    """
    Calculate overall confidence score.

    Args:
        data_completeness: Ratio of processed to total exhibits
        providers: List of provider records
        timeline: List of timeline events

    Returns:
        Confidence score between 0.0 and 1.0
    """
    factors = []

    # Data completeness factor
    factors.append(data_completeness)

    # Provider reliability factor
    provider_count = len(set(p.get('name', '') for p in providers))
    factors.append(min(1.0, provider_count / 5.0))

    # Timeline consistency factor
    if timeline:
        dated_events = [e for e in timeline if _parse_date(e.get('date', ''))]
        factors.append(len(dated_events) / len(timeline))

    return sum(factors) / len(factors) if factors else 0.0


def calculate_quality_metrics(
    data_completeness: float,
    confidence_score: float,
    timeline: List[Dict[str, Any]],
    providers: List[Dict[str, Any]],
    diagnoses: List[Dict[str, Any]],
    treatments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate comprehensive quality metrics.

    Returns:
        Dict with quality metrics
    """
    return {
        'data_completeness': data_completeness,
        'confidence_score': confidence_score,
        'timeline_coverage': len(timeline),
        'provider_diversity': len(set(p.get('name', '') for p in providers)),
        'diagnosis_count': len(diagnoses),
        'treatment_documentation': len(treatments)
    }


def calculate_statistics(events: List) -> Dict[str, Any]:
    """
    Calculate statistics for events.

    Handles both MedicalEvent objects and dicts.

    Args:
        events: List of events (dicts or MedicalEvent objects)

    Returns:
        Statistics dict with total_events and date_range
    """
    if not events:
        return {'total_events': 0, 'date_range': 'No events'}

    dates = []
    for e in events:
        if hasattr(e, 'date'):
            date_val = e.date
        elif isinstance(e, dict):
            date_val = e.get('date')
        else:
            continue

        if date_val:
            if isinstance(date_val, str):
                parsed = _parse_date(date_val)
                if parsed:
                    dates.append(parsed)
            else:
                dates.append(date_val)

    if dates:
        date_range = f"{min(dates)} to {max(dates)}"
    else:
        date_range = "No dated events"

    return {
        'total_events': len(events),
        'date_range': date_range
    }






def create_error_result(
    error_message: str,
    processing_time: float,
    processing_mode: Any,
    analysis_level: Any
) -> Dict[str, Any]:
    """
    Create error result dict.

    Args:
        error_message: The error message
        processing_time: Time spent processing
        processing_mode: ProcessingMode enum value
        analysis_level: AnalysisLevel enum value

    Returns:
        Error result dict (to be converted to UnifiedChronologyResult)
    """
    from app.core.models.entry import MedicalTimeline

    return {
        'success': False,
        'processing_time': processing_time,
        'processing_mode': processing_mode,
        'analysis_level': analysis_level,
        'timeline': MedicalTimeline(events=[]),
        'events': [],
        'providers': [],
        'diagnoses': [],
        'treatment_gaps': [],
        'error_message': error_message
    }


def load_bookmark_metadata(metadata_path: str) -> Dict[str, Any]:
    """
    Load bookmark metadata from JSON file.

    Args:
        metadata_path: Path to metadata JSON file

    Returns:
        Bookmark metadata dict or empty dict on error
    """
    import json
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        logger.info(
            f"Loaded bookmark metadata: {metadata.get('total_bookmarks', 0)} bookmarks, "
            f"{metadata.get('exhibit_count', 0)} exhibits"
        )
        return metadata
    except Exception as e:
        logger.error(f"Failed to load bookmark metadata from {metadata_path}: {e}")
        return {}


def extract_f_exhibits_from_pdf(
    pdf_path: str,
    max_exhibits: Optional[int] = None,
    max_pages_per_exhibit: int = 50
) -> List[Dict[str, Any]]:
    """
    Extract F-section exhibits from ERE PDF using bookmarks with vision fallback.

    Parses PDF bookmarks to find individual F-section exhibits (1F, 2F, etc.)
    and extracts text from each exhibit. For scanned pages, includes image data
    for vision-based extraction.

    Args:
        pdf_path: Path to ERE PDF file
        max_exhibits: Maximum number of exhibits to extract (None for all)
        max_pages_per_exhibit: Maximum pages to extract per exhibit

    Returns:
        List of exhibit dicts with structure:
        {
            "exhibit_id": str,
            "text": str,  # Combined text from text-extractable pages
            "images": List[bytes],  # PNG images for scanned pages
            "page_range": (start, end),
            "has_scanned_pages": bool,
            "scanned_page_nums": List[int]  # 1-indexed page numbers
        }
    """
    import fitz  # PyMuPDF
    from app.adapters.pdf.preprocessing import is_scanned_page, render_page_to_image, strip_court_headers

    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()

        # Extract F-section exhibits from bookmarks (pattern: ##F: ... or ##F - ...)
        f_exhibits = []
        for level, title, page in toc:
            match = re.match(r'^(\d+F)\s*[-:]', title)
            if match:
                f_exhibits.append({
                    "exhibit_id": match.group(1),
                    "title": title,
                    "start_page": page,
                })

        # Calculate end pages based on next exhibit
        for i, ex in enumerate(f_exhibits):
            if i < len(f_exhibits) - 1:
                ex["end_page"] = f_exhibits[i + 1]["start_page"] - 1
            else:
                ex["end_page"] = len(doc)

        logger.info(f"Found {len(f_exhibits)} F-section exhibits in PDF")

        # Apply max_exhibits limit
        if max_exhibits:
            f_exhibits = f_exhibits[:max_exhibits]

        # Extract content from each exhibit (text + images for scanned pages)
        exhibits_with_content = []
        total_scanned = 0

        for ex in f_exhibits:
            start = ex["start_page"] - 1  # 0-indexed for fitz
            end = min(ex["end_page"], ex["start_page"] + max_pages_per_exhibit - 1)

            text_parts = []
            images = []
            scanned_page_nums = []

            for page_num in range(start, min(end, len(doc))):
                page = doc[page_num]

                if is_scanned_page(page):
                    # Check memory limit
                    if len(images) >= MAX_IMAGES_PER_EXHIBIT:
                        logger.warning(
                            f"Exhibit {ex['exhibit_id']} truncated at "
                            f"{MAX_IMAGES_PER_EXHIBIT} scanned pages"
                        )
                        break
                    # Scanned page - render to image for vision extraction
                    images.append(render_page_to_image(page))
                    scanned_page_nums.append(page_num + 1)  # 1-indexed
                    total_scanned += 1
                else:
                    # Text page - extract text and strip court headers
                    page_text = page.get_text()
                    # Strip court headers to send clean text to LLM
                    clean_text = strip_court_headers(page_text)
                    if clean_text.strip():
                        text_parts.append(clean_text)

            text = "\n".join(text_parts)
            has_content = text.strip() or images

            if has_content:
                exhibit_data = {
                    "exhibit_id": ex["exhibit_id"],
                    "text": text,
                    "images": images,
                    "page_range": (ex["start_page"], end),
                    "has_scanned_pages": len(images) > 0,
                    "scanned_page_nums": scanned_page_nums,
                }
                exhibits_with_content.append(exhibit_data)

                if images:
                    logger.info(
                        f"Exhibit {ex['exhibit_id']}: {len(text):,} chars text, "
                        f"{len(images)} scanned pages (pp. {scanned_page_nums})"
                    )
                else:
                    logger.debug(f"Exhibit {ex['exhibit_id']}: {len(text):,} chars text")

        doc.close()

        if total_scanned > 0:
            logger.info(
                f"Extracted {len(exhibits_with_content)} F-exhibits "
                f"({total_scanned} scanned pages requiring vision)"
            )
        else:
            logger.info(f"Extracted {len(exhibits_with_content)} F-exhibits (all text)")

        return exhibits_with_content

    except Exception as e:
        logger.error(f"Failed to extract F-exhibits from {pdf_path}: {e}")
        return []
