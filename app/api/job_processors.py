"""
Background job processors for ERE PDF Processing Pipeline.

Orchestrates async job processing for ERE and ChartVision documents.
Uses extracted modules for DDE parsing, chronology extraction, and report building.
"""
import logging
from datetime import datetime
from typing import Any, Dict

from app.api.processors.dde_extractor import extract_dde, get_section_exhibits
from app.api.processors.chronology_extractor import (
    extract_chronology,
    extract_chronology_with_progress,
)
from app.api.processors.report_builder import (
    build_report,
    build_chartvision_report,
    export_ere_report,
    generate_chartvision_pdf,
)
from app.api.processors.job_lifecycle import (
    add_section_ids,
    add_section_ids_inplace,
    complete_job,
    complete_chartvision_job,
    fail_job,
)

logger = logging.getLogger(__name__)


async def process_ere_job(
    job_id: str,
    active_jobs: Dict[str, Any],
    chronology_engine: Any,
) -> None:
    """
    Background task to process ERE document.

    Args:
        job_id: Unique job identifier
        active_jobs: Dictionary tracking all active jobs
        chronology_engine: ChronologyEngine instance (unused, kept for API compatibility)
    """
    if job_id not in active_jobs:
        return

    job = active_jobs[job_id]
    job["status"] = "processing"
    job["started_at"] = datetime.now()

    try:
        file_path = job["file_path"]

        # Step 1: Segment PDF by bookmarks
        job["current_step"] = "Segmenting PDF by bookmarks"
        job["progress"] = 10
        job["steps_completed"] = []

        from app.adapters.pdf import PyMuPDFAdapter

        pdf_adapter = PyMuPDFAdapter()
        exhibits = pdf_adapter.get_exhibit_page_ranges(file_path)
        segments = add_section_ids(exhibits)
        job["steps_completed"].append("bookmark_segmentation")

        # Step 2: Extract DDE from Section A
        job["current_step"] = "Extracting DDE from Section A"
        job["progress"] = 25

        section_a = get_section_exhibits(segments, "A")
        dde_result, raw_dde_result = await extract_dde(file_path, section_a)
        job["steps_completed"].append("dde_extraction")

        # Step 3: Extract chronology from F-section exhibits
        job["current_step"] = "Extracting medical chronology"
        job["progress"] = 50

        chronology_entries = await extract_chronology(file_path, job_id)
        job["steps_completed"].append("chronology_extraction")

        # Step 4: Build ChartVision report
        job["current_step"] = "Building report"
        job["progress"] = 70

        report = build_report(
            raw_dde_result=raw_dde_result,
            chronology_entries=chronology_entries,
            job_id=job_id,
            total_pages=len(segments),
        )
        job["steps_completed"].append("report_build")

        # Step 5: Export to markdown and PDF
        job["current_step"] = "Exporting report"
        job["progress"] = 85

        results = export_ere_report(
            report=report,
            dde_result=dde_result,
            chronology_entries=chronology_entries,
            segments=segments,
            job_id=job_id,
        )
        job["steps_completed"].append("report_export")

        # Store final results
        job["results"] = results
        job["steps_completed"].append("report_generation")

        complete_job(job, active_jobs, job_id)
        logger.info(f"ERE job {job_id} completed successfully")

    except Exception as e:
        fail_job(job, active_jobs, job_id, e)


async def process_chartvision_job(
    job_id: str,
    active_jobs: Dict[str, Any],
) -> None:
    """
    Background task to process ChartVision job.

    Args:
        job_id: Unique job identifier
        active_jobs: Dictionary tracking all active jobs
    """
    if job_id not in active_jobs:
        return

    job = active_jobs[job_id]
    job["status"] = "processing"
    job["started_at"] = datetime.now()

    try:
        file_path = job["file_path"]

        # Step 1: Extract exhibits from PDF bookmarks
        job["current_step"] = "Extracting exhibits from bookmarks"
        job["progress"] = 0.1

        from app.adapters.pdf import PyMuPDFAdapter

        pdf_adapter = PyMuPDFAdapter()
        exhibits = pdf_adapter.get_exhibit_page_ranges(file_path)
        add_section_ids_inplace(exhibits)
        logger.info(f"Extracted {len(exhibits)} exhibits from bookmarks")

        # Step 2: Parse DDE from Section A
        job["current_step"] = "Parsing DDE data"
        job["progress"] = 0.4

        section_a = get_section_exhibits(exhibits, "A")
        dde_result, raw_dde_result = await extract_dde(file_path, section_a)

        # Step 3: Extract F-section chronology
        job["current_step"] = "Extracting F-section exhibits"
        job["progress"] = 0.5

        chronology_entries = await extract_chronology_with_progress(file_path, job_id, job)

        # Step 4: Build ChartVision report
        job["current_step"] = "Building ChartVision report"
        job["progress"] = 0.8

        report = build_chartvision_report(
            raw_dde_result=raw_dde_result,
            chronology_entries=chronology_entries,
            job_id=job_id,
            total_pages=len(exhibits),
        )

        # Step 5: Generate PDF if enabled
        pdf_path = None
        if job.get("options", {}).get("pdf_output", True):
            job["current_step"] = "Generating PDF report"
            job["progress"] = 0.9
            pdf_path = generate_chartvision_pdf(report, job_id)

        # Store result
        complete_chartvision_job(
            job=job,
            active_jobs=active_jobs,
            job_id=job_id,
            report=report,
            exhibits=exhibits,
            dde_result=dde_result,
            chronology_entries=chronology_entries,
            pdf_path=pdf_path,
        )
        logger.info(f"ChartVision job {job_id} completed successfully")

    except Exception as e:
        fail_job(job, active_jobs, job_id, e)


__all__ = [
    "process_ere_job",
    "process_chartvision_job",
]
