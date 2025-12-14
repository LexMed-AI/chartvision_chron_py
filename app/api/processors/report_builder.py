"""
Report Building Service.

Handles building ChartVision reports from extracted data.
"""
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_report(
    raw_dde_result: Dict[str, Any],
    chronology_entries: List[Dict[str, Any]],
    job_id: str,
    total_pages: int,
) -> Any:
    """
    Build ChartVision report from extracted data.

    Args:
        raw_dde_result: Raw DDE parser output (preserves MDIs, determinationHistory)
        chronology_entries: List of chronology entries
        job_id: Job identifier for case reference
        total_pages: Total document page count

    Returns:
        ChartVisionReportData instance
    """
    from app.core.builders import ChartVisionBuilder

    builder = ChartVisionBuilder()

    if raw_dde_result and raw_dde_result.get("fields"):
        builder.from_dde_result(
            raw_dde_result,
            case_reference=job_id,
            total_pages=total_pages,
        )
    else:
        builder.set_claimant(
            full_name="Pending Extraction",
            date_of_birth=date(1900, 1, 1),
            case_file_reference=job_id,
            total_document_pages=total_pages,
        )

    if chronology_entries:
        builder.from_llm_chronology_entries(chronology_entries)

    return builder.build()


def build_chartvision_report(
    raw_dde_result: Dict[str, Any],
    chronology_entries: List[Dict[str, Any]],
    job_id: str,
    total_pages: int,
) -> Any:
    """
    Build ChartVision report with administrative fallback.

    Args:
        raw_dde_result: Raw DDE parser output
        chronology_entries: List of chronology entries
        job_id: Job identifier for case reference
        total_pages: Total document page count

    Returns:
        ChartVisionReportData instance
    """
    from app.core.builders import ChartVisionBuilder

    builder = ChartVisionBuilder()

    if raw_dde_result and raw_dde_result.get("fields"):
        builder.from_dde_result(
            raw_dde_result,
            case_reference=job_id,
            total_pages=total_pages,
        )
        logger.info("Populated builder from DDE result")
    else:
        builder.set_claimant(
            full_name="Pending Extraction",
            date_of_birth=date(1900, 1, 1),
            case_file_reference=job_id,
            total_document_pages=total_pages,
        )
        builder.set_administrative(
            claim_type="Unknown",
            protective_filing_date=date.today(),
            alleged_onset_date=date.today(),
        )

    if chronology_entries:
        builder.from_llm_chronology_entries(chronology_entries)

    return builder.build()


def export_ere_report(
    report: Any,
    dde_result: Dict[str, Any],
    chronology_entries: List[Dict[str, Any]],
    segments: List[Dict[str, Any]],
    job_id: str,
) -> Dict[str, Any]:
    """
    Export ERE report to markdown and PDF.

    Args:
        report: ChartVisionReportData instance
        dde_result: Normalized DDE result for API response
        chronology_entries: List of chronology entries
        segments: List of document segments
        job_id: Job identifier

    Returns:
        Results dictionary with paths and metadata
    """
    from app.adapters.export import ReportExporter

    exporter = ReportExporter(output_dir="results")

    md_path = exporter.export_markdown(report_data=report, job_id=job_id)

    results = {
        "segments": len(segments),
        "chronology_entries": len(chronology_entries),
        "entries": chronology_entries,
        "sections_found": list(set(s.get("section_id") for s in segments)),
        "dde_extraction": dde_result,
        "dde_extracted": bool(dde_result),
        "report": report.to_dict(),
        "markdown_path": md_path,
    }

    claimant_name = dde_result.get("claimant_name", "Unknown") if dde_result else "Unknown"
    pdf_path = exporter.export_pdf_from_results(
        results=results,
        job_id=job_id,
        title=f"Medical Chronology - {claimant_name}",
    )
    results["pdf_path"] = pdf_path

    return results


def generate_chartvision_pdf(report: Any, job_id: str) -> Optional[str]:
    """
    Generate PDF for ChartVision report.

    Args:
        report: ChartVisionReportData instance
        job_id: Job identifier for filename

    Returns:
        Path to generated PDF, or None if generation failed
    """
    try:
        output_dir = Path("/tmp/chartvision_reports")
        output_dir.mkdir(exist_ok=True)
        pdf_output_path = str(output_dir / f"{job_id}.pdf")

        from app.adapters.export import MarkdownToPDFConverter

        converter = MarkdownToPDFConverter()
        markdown_content = report.to_markdown()

        metadata = {"title": "Medical Chronology"}
        if hasattr(report, "claimant_identification"):
            claimant = report.claimant_identification
            if hasattr(claimant, "full_name"):
                metadata["patient_name"] = claimant.full_name

        pdf_path = converter.convert_chartvision_to_pdf(
            markdown_content=markdown_content,
            output_path=pdf_output_path,
            metadata=metadata,
        )

        if pdf_path:
            logger.info(f"Generated PDF: {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.warning(f"PDF generation failed (non-fatal): {e}")
        return None
