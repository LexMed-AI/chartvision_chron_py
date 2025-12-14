"""
Job Lifecycle Management.

Handles job state transitions, completion, and failure handling.
"""
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from prometheus_client import Histogram

logger = logging.getLogger(__name__)

# Prometheus metrics
PROCESSING_TIME = Histogram(
    "ere_pdf_processing_duration_seconds", "PDF processing time"
)


def add_section_ids(exhibits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Add section_id to each exhibit based on exhibit_id pattern.

    Args:
        exhibits: List of exhibits from PDF extraction

    Returns:
        New list with section_id added to each exhibit
    """
    return [
        {
            "section_id": e.get("exhibit_id", "")[-1].upper() if e.get("exhibit_id") else "",
            **e,
        }
        for e in exhibits
    ]


def add_section_ids_inplace(exhibits: List[Dict[str, Any]]) -> None:
    """
    Add section_id to exhibits in place.

    Args:
        exhibits: List of exhibits to modify
    """
    for exhibit in exhibits:
        exhibit_id = exhibit.get("exhibit_id", "")
        if exhibit_id:
            exhibit["section_id"] = exhibit_id[-1].upper() if exhibit_id[-1].isalpha() else ""


def complete_job(job: Dict[str, Any], active_jobs: Any, job_id: str) -> None:
    """
    Mark job as completed and persist.

    Args:
        job: Job dictionary to update
        active_jobs: Active jobs store (may have persist method)
        job_id: Job identifier for persistence
    """
    job["status"] = "completed"
    job["progress"] = 100
    job["current_step"] = "Complete"
    job["completed_at"] = datetime.now()

    if job.get("started_at"):
        processing_time = (job["completed_at"] - job["started_at"]).total_seconds()
        PROCESSING_TIME.observe(processing_time)

    if hasattr(active_jobs, "persist"):
        active_jobs.persist(job_id)


def complete_chartvision_job(
    job: Dict[str, Any],
    active_jobs: Any,
    job_id: str,
    report: Any,
    exhibits: List[Dict[str, Any]],
    dde_result: Dict[str, Any],
    chronology_entries: List[Dict[str, Any]],
    pdf_path: Optional[str],
) -> None:
    """
    Mark ChartVision job as completed with metadata.

    Args:
        job: Job dictionary to update
        active_jobs: Active jobs store
        job_id: Job identifier
        report: ChartVisionReportData instance
        exhibits: List of exhibits processed
        dde_result: Normalized DDE result
        chronology_entries: List of chronology entries
        pdf_path: Path to generated PDF (or None)
    """
    job["status"] = "completed"
    job["progress"] = 1.0
    job["current_step"] = "Complete"
    job["completed_at"] = datetime.now()
    job["result"] = report.to_dict()
    job["pdf_path"] = pdf_path
    job["metadata"] = {
        "total_exhibits": len(exhibits),
        "filtered_exhibits": len(exhibits),
        "dde_parsed": bool(dde_result.get("fields") if isinstance(dde_result, dict) else False),
        "sections_processed": list(set(e.get("section_id") for e in exhibits)),
        "chronology_entries_count": len(chronology_entries),
        "pdf_generated": pdf_path is not None,
    }

    if hasattr(active_jobs, "persist"):
        active_jobs.persist(job_id)


def fail_job(job: Dict[str, Any], active_jobs: Any, job_id: str, error: Exception) -> None:
    """
    Mark job as failed and persist.

    Args:
        job: Job dictionary to update
        active_jobs: Active jobs store
        job_id: Job identifier
        error: Exception that caused failure
    """
    logger.error(f"Processing failed for job {job_id}: {error}")
    job["status"] = "failed"
    job["error"] = str(error)
    job["traceback"] = traceback.format_exc()

    if hasattr(active_jobs, "persist"):
        active_jobs.persist(job_id)
