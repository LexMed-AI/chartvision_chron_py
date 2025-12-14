"""
Chronology Extraction Service.

Handles extraction of chronology entries from F-section medical exhibits.
"""
import logging
import traceback
from typing import Any, Dict, List

from app.config.extraction_limits import MAX_EXHIBITS_PER_JOB, MAX_PAGES_PER_EXHIBIT

logger = logging.getLogger(__name__)


async def extract_chronology(file_path: str, job_id: str) -> List[Dict[str, Any]]:
    """
    Extract chronology entries from F-section exhibits.

    Args:
        file_path: Path to PDF file
        job_id: Job identifier for case info

    Returns:
        List of chronology entry dictionaries
    """
    try:
        from app.core.extraction.utils import extract_f_exhibits_from_pdf
        from app.core.extraction import ChronologyEngine
        from app.adapters.llm import BedrockAdapter

        f_exhibits = extract_f_exhibits_from_pdf(
            file_path,
            max_exhibits=MAX_EXHIBITS_PER_JOB,
            max_pages_per_exhibit=MAX_PAGES_PER_EXHIBIT,
        )
        logger.info(f"Extracted {len(f_exhibits)} F-section exhibits")

        if not f_exhibits:
            return []

        llm = BedrockAdapter()
        engine = ChronologyEngine(llm=llm)
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
        job: Job dictionary for progress updates

    Returns:
        List of chronology entry dictionaries
    """
    try:
        from app.core.extraction.utils import extract_f_exhibits_from_pdf
        from app.core.extraction import ChronologyEngine
        from app.adapters.llm import BedrockAdapter

        f_exhibits = extract_f_exhibits_from_pdf(
            file_path,
            max_exhibits=MAX_EXHIBITS_PER_JOB,
            max_pages_per_exhibit=MAX_PAGES_PER_EXHIBIT,
        )
        logger.info(f"Extracted {len(f_exhibits)} F-section exhibits")

        if not f_exhibits:
            return []

        job["current_step"] = "Generating medical chronology"
        job["progress"] = 0.6

        llm = BedrockAdapter()
        engine = ChronologyEngine(llm=llm)
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
