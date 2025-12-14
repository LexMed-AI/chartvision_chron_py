"""
Job processors and extraction services.

Modular components for processing ERE and ChartVision documents.
"""
from app.api.processors.dde_extractor import (
    extract_dde,
    get_section_exhibits,
    is_dde_exhibit,
    find_latest_dde_exhibit,
    DDE_PARSER_AVAILABLE,
)
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

__all__ = [
    # DDE extraction
    "extract_dde",
    "get_section_exhibits",
    "is_dde_exhibit",
    "find_latest_dde_exhibit",
    "DDE_PARSER_AVAILABLE",
    # Chronology extraction
    "extract_chronology",
    "extract_chronology_with_progress",
    # Report building
    "build_report",
    "build_chartvision_report",
    "export_ere_report",
    "generate_chartvision_pdf",
    # Job lifecycle
    "add_section_ids",
    "add_section_ids_inplace",
    "complete_job",
    "complete_chartvision_job",
    "fail_job",
]
