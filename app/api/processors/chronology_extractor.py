"""
Chronology Extraction Service.

Handles extraction of chronology entries from F-section medical exhibits.
Supports format-based extraction routing (RAW_SSA, PROCESSED, COURT_TRANSCRIPT).
"""
import logging
import traceback
from typing import Any, Dict, List, Optional

from app.config.extraction_limits import MAX_EXHIBITS_PER_JOB, MAX_PAGES_PER_EXHIBIT
from app.core.extraction.format_detector import UNKNOWN

logger = logging.getLogger(__name__)


async def extract_chronology(
    file_path: str,
    job_id: str,
    ere_format: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Extract chronology entries from F-section exhibits.

    Args:
        file_path: Path to PDF file
        job_id: Job identifier for case info
        ere_format: Optional ERE format type for extraction routing

    Returns:
        List of chronology entry dictionaries
    """
    try:
        from app.core.extraction.pdf_exhibit_extractor import extract_f_exhibits_with_pages
        from app.core.extraction import ChronologyEngine
        from app.adapters.llm import BedrockAdapter

        raw_exhibits = extract_f_exhibits_with_pages(
            file_path,
            max_exhibits=MAX_EXHIBITS_PER_JOB,
            max_pages_per_exhibit=MAX_PAGES_PER_EXHIBIT,
        )
        # Adapt format: combined_text -> text for engine compatibility
        f_exhibits = []
        for ex in raw_exhibits:
            f_exhibits.append({
                "exhibit_id": ex["exhibit_id"],
                "text": ex.get("combined_text", ""),
                "pages": ex.get("pages", []),
                "images": ex.get("images", []),
                "page_range": ex.get("page_range", (0, 0)),
                "scanned_page_nums": ex.get("scanned_page_nums", []),
                "has_scanned_pages": ex.get("has_scanned_pages", False),
            })
        logger.info(f"Extracted {len(f_exhibits)} F-section exhibits (with pages)")

        if not f_exhibits:
            return []

        llm = BedrockAdapter()
        engine = ChronologyEngine(llm=llm, ere_format=ere_format)
        result = await engine.generate_chronology(
            exhibits=f_exhibits,
            case_info={"job_id": job_id},
        )

        if hasattr(result, "events"):
            entries = [e.__dict__ if hasattr(e, "__dict__") else e for e in result.events]
            logger.info(f"Extracted {len(entries)} chronology entries")
            return entries

        return []

    except Exception as e:
        logger.warning(f"Chronology extraction failed: {e}")
        return []


async def extract_chronology_with_progress(
    file_path: str,
    job_id: str,
    job: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract chronology with job progress updates.

    Args:
        file_path: Path to PDF file
        job_id: Job identifier for case info
        job: Job dictionary for progress updates (includes ere_format)

    Returns:
        List of chronology entry dictionaries
    """
    try:
        from app.core.extraction.pdf_exhibit_extractor import extract_f_exhibits_with_pages
        from app.core.extraction import ChronologyEngine
        from app.adapters.llm import BedrockAdapter

        # Get ERE format from job for extraction routing
        ere_format = job.get("ere_format", UNKNOWN)

        raw_exhibits = extract_f_exhibits_with_pages(
            file_path,
            max_exhibits=MAX_EXHIBITS_PER_JOB,
            max_pages_per_exhibit=MAX_PAGES_PER_EXHIBIT,
        )
        # Adapt format: combined_text -> text for engine compatibility
        f_exhibits = []
        for ex in raw_exhibits:
            f_exhibits.append({
                "exhibit_id": ex["exhibit_id"],
                "text": ex.get("combined_text", ""),
                "pages": ex.get("pages", []),
                "images": ex.get("images", []),
                "page_range": ex.get("page_range", (0, 0)),
                "scanned_page_nums": ex.get("scanned_page_nums", []),
                "has_scanned_pages": ex.get("has_scanned_pages", False),
            })
        logger.info(f"Extracted {len(f_exhibits)} F-section exhibits with pages (format: {ere_format})")

        if not f_exhibits:
            return []

        job["current_step"] = "Generating medical chronology"
        job["progress"] = 0.6

        llm = BedrockAdapter()
        engine = ChronologyEngine(llm=llm, ere_format=ere_format)
        result = await engine.generate_chronology(
            exhibits=f_exhibits,
            case_info={"job_id": job_id},
        )

        entries = []
        if hasattr(result, "events"):
            for event in result.events:
                if isinstance(event, dict):
                    entries.append(event)
                else:
                    entries.append(_convert_event_to_dict(event))

        logger.info(f"Extracted {len(entries)} chronology entries")
        return entries

    except Exception as e:
        logger.warning(f"Chronology extraction failed: {e}")
        logger.warning(f"Traceback: {traceback.format_exc()}")
        return []


def _convert_event_to_dict(event: Any) -> Dict[str, Any]:
    """Convert event object to dictionary."""
    return {
        "date": str(getattr(event, "date", "")) if hasattr(event, "date") else "",
        "provider": getattr(event, "provider", ""),
        "facility": getattr(event, "facility", ""),
        "occurrence": getattr(event, "occurrence_treatment", getattr(event, "summary", "")),
        "exhibit_citation": getattr(event, "exhibit_reference", getattr(event, "source", "")),
    }
