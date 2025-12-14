"""
Background job processors for ERE PDF Processing Pipeline.

Contains async job processing logic for ERE and ChartVision documents.
"""
import logging
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

from prometheus_client import Histogram

from app.config.extraction_limits import MAX_EXHIBITS_PER_JOB, MAX_PAGES_PER_EXHIBIT

logger = logging.getLogger(__name__)

# Prometheus metrics
PROCESSING_TIME = Histogram(
    "ere_pdf_processing_duration_seconds", "PDF processing time"
)

# Import DDE parser from core
try:
    from app.core.parsers import DDEParser
    from app.core.parsers.dde_parser import create_dde_parser
    DDE_PARSER_AVAILABLE = True
except ImportError:
    DDE_PARSER_AVAILABLE = False
    logger.warning("DDEParser not available")


def normalize_dde_result(fields: Dict[str, Any], extraction_mode: str, confidence: float) -> Dict[str, Any]:
    """
    Normalize DDE extraction result to consistent API structure.

    Vision extraction returns nested structure (case_metadata, physical_rfc_assessment, etc.)
    Text extraction returns flat fields. This normalizes both to a consistent structure.
    """
    result = {
        "extraction_mode": extraction_mode,
        "confidence": confidence,
    }

    # Check for nested structure (vision extraction)
    case_metadata = fields.get("case_metadata", {})
    if case_metadata:
        # Vision extraction - extract from nested structure
        result["claimant_name"] = case_metadata.get("claimant_name")
        result["date_of_birth"] = case_metadata.get("date_of_birth")
        result["claim_type"] = case_metadata.get("claim_type")
        result["alleged_onset_date"] = case_metadata.get("alleged_onset_date")
        result["protective_filing_date"] = case_metadata.get("protective_filing_date")
        result["date_last_insured"] = case_metadata.get("date_last_insured")
        result["age_category"] = case_metadata.get("age_category")
        result["determination_level"] = case_metadata.get("determination_level")
        result["case_number"] = case_metadata.get("case_number")
        result["ssn_last_4"] = case_metadata.get("ssn_last_4")

        # RFC Assessment (Physical)
        rfc = fields.get("physical_rfc_assessment", {})
        if rfc:
            result["assessment_type"] = rfc.get("rfc_assessment_type", "Physical RFC")
            result["medical_consultant"] = rfc.get("medical_consultant")
            result["exertional_limitations"] = rfc.get("exertional_limitations")
            result["postural_limitations"] = rfc.get("postural_limitations")
            result["manipulative_limitations"] = rfc.get("manipulative_limitations")
            result["visual_limitations"] = rfc.get("visual_limitations")
            result["communicative_limitations"] = rfc.get("communicative_limitations")
            result["environmental_limitations"] = rfc.get("environmental_limitations")

            # Extract exertional capacity from limitations
            exertional = rfc.get("exertional_limitations", {})
            if exertional:
                occ_lift = exertional.get("lift_carry_occasional", {})
                if isinstance(occ_lift, dict):
                    amount = occ_lift.get("amount", "")
                else:
                    amount = str(occ_lift)
                if "50" in str(amount):
                    result["exertional_capacity"] = "Medium"
                elif "20" in str(amount):
                    result["exertional_capacity"] = "Light"
                elif "10" in str(amount):
                    result["exertional_capacity"] = "Sedentary"
                else:
                    result["exertional_capacity"] = "Unknown"

        # Mental RFC Assessment
        mental_rfc = fields.get("mental_rfc_assessment", {})
        if mental_rfc:
            result["paragraph_b_criteria"] = mental_rfc.get("paragraph_b_criteria")
            result["section_1_activities"] = mental_rfc.get("section_1_activities")

        # Impairments - handle various structures
        impairments_data = fields.get("medical_impairments", fields.get("impairments", []))
        diagnoses = []

        if isinstance(impairments_data, list):
            # List of impairments
            for imp in impairments_data:
                diagnoses.append({
                    "description": imp.get("impairment", imp.get("description", "")),
                    "code": imp.get("code", ""),
                    "severity": imp.get("severity", imp.get("priority", ""))
                })
        elif isinstance(impairments_data, dict):
            # Dict with primary_diagnosis, secondary_diagnosis
            for key in ["primary_diagnosis", "secondary_diagnosis"]:
                if imp := impairments_data.get(key):
                    diagnoses.append({
                        "description": imp.get("description", imp.get("impairment", "")),
                        "code": imp.get("code", ""),
                        "severity": imp.get("severity", imp.get("priority", ""))
                    })

        if diagnoses:
            result["primary_diagnoses"] = diagnoses

        # Determination - handle various field names
        determination = fields.get("determination_decision", {})
        if determination:
            # Try multiple possible field names
            decision = (determination.get("decision") or
                       determination.get("disability_status") or
                       determination.get("level"))
            result["determination_decision"] = decision
            result["determination_basis"] = determination.get("basis")

        # Findings of fact (clinical summary)
        findings = fields.get("findings_of_fact", {})
        if findings:
            result["clinical_summary"] = findings.get("clinical_summary")
            result["adl_limitations"] = findings.get("adl_limitations")

        # Evidence received
        result["evidence_received"] = fields.get("evidence_received", [])

        # Consultative examination
        result["consultative_examination"] = fields.get("consultative_examination")

        # Keep original nested structure for detailed views
        result["raw_fields"] = fields

    else:
        # Flat structure (text extraction) - pass through
        result.update(fields)

    return result


async def process_ere_job(
    job_id: str,
    active_jobs: Dict[str, Any],
    chronology_engine: Any,
) -> None:
    """
    Background task to process ERE document using core engine directly.

    Args:
        job_id: Unique job identifier
        active_jobs: Dictionary tracking all active jobs
        chronology_engine: ChronologyEngine instance
    """
    if job_id not in active_jobs:
        return

    job = active_jobs[job_id]
    job["status"] = "processing"
    job["started_at"] = datetime.now()

    try:
        file_path = job["file_path"]
        import fitz  # PyMuPDF

        # Step 1: Segment PDF by bookmarks
        job["current_step"] = "Segmenting PDF by bookmarks"
        job["progress"] = 10
        job["steps_completed"] = []

        from app.adapters.pdf import PyMuPDFAdapter
        pdf_adapter = PyMuPDFAdapter()
        exhibits = pdf_adapter.get_exhibit_page_ranges(file_path)
        segments = [{"section_id": e.get("exhibit_id", "")[-1].upper() if e.get("exhibit_id") else "", **e} for e in exhibits]
        job["steps_completed"].append("bookmark_segmentation")

        # Step 2: Extract DDE from Section A (if available)
        job["current_step"] = "Extracting DDE from Section A"
        job["progress"] = 25

        section_a = [s for s in segments if s.get("section_id", "").upper() == "A"]
        dde_result = {}

        dde_extraction_mode = "none"
        dde_confidence = 0.0

        if section_a and DDE_PARSER_AVAILABLE:
            try:
                # Filter to only DDE documents (not court orders, complaints, etc.)
                # Match "DDE" or "Disability Determination Explanation"
                def is_dde_exhibit(exhibit):
                    title = exhibit.get("title", "").upper()
                    return "DDE" in title or "DISABILITY DETERMINATION EXPLANATION" in title
                dde_exhibits = [s for s in section_a if is_dde_exhibit(s)]
                if not dde_exhibits:
                    logger.warning("No DDE documents found in Section A, skipping DDE extraction")
                else:
                    # Get the latest DDE by page number (most recent determination)
                    latest_a = max(dde_exhibits, key=lambda x: x.get("start_page", 0))
                    logger.info(f"Selected DDE exhibit: {latest_a.get('title', 'Unknown')[:60]} pages {latest_a.get('start_page')}-{latest_a.get('end_page')}")
                    parser = create_dde_parser()
                    result = await parser.parse(
                        pdf_path=file_path,
                        page_start=latest_a.get("start_page", 1),
                        page_end=latest_a.get("end_page"),
                    )
                    dde_result = result.get("fields", {})
                    dde_extraction_mode = result.get("extraction_mode", "text")
                    dde_confidence = result.get("confidence", 0.0)

                    # Normalize nested structure to flat fields for API compatibility
                    dde_result = normalize_dde_result(dde_result, dde_extraction_mode, dde_confidence)

                    logger.info(f"DDE extraction: confidence={dde_confidence:.2f}, mode={dde_extraction_mode}")
            except Exception as e:
                logger.warning(f"DDE extraction failed: {e}")
                dde_result = {}

        job["steps_completed"].append("dde_extraction")

        # Step 3: Extract chronology from F-section exhibits
        # FIX: Use per-exhibit extraction to prevent context bleeding
        job["current_step"] = "Extracting medical chronology"
        job["progress"] = 50

        chronology_entries = []
        try:
            from app.core.extraction.utils import extract_f_exhibits_from_pdf
            from app.core.extraction import ChronologyEngine
            from app.adapters.llm import BedrockAdapter

            f_exhibits = extract_f_exhibits_from_pdf(file_path, max_exhibits=MAX_EXHIBITS_PER_JOB, max_pages_per_exhibit=MAX_PAGES_PER_EXHIBIT)
            logger.info(f"Extracted {len(f_exhibits)} F-section exhibits")

            if f_exhibits:
                llm = BedrockAdapter()
                engine = ChronologyEngine(llm=llm)
                result = await engine.generate_chronology(
                    exhibits=f_exhibits,
                    case_info={"job_id": job_id}
                )
                if hasattr(result, 'events'):
                    chronology_entries = [e.__dict__ if hasattr(e, '__dict__') else e for e in result.events]
                logger.info(f"Extracted {len(chronology_entries)} chronology entries")
        except Exception as e:
            logger.warning(f"Chronology extraction failed: {e}")

        job["steps_completed"].append("chronology_extraction")

        # Step 4: Build ChartVision report
        job["current_step"] = "Building report"
        job["progress"] = 70

        from app.core.builders import ChartVisionBuilder

        builder = ChartVisionBuilder()

        # Populate from DDE if available
        if dde_result:
            builder.from_dde_result(
                {"fields": dde_result},
                case_reference=job_id,
                total_pages=len(segments),
            )
        else:
            # Fallback to basic info
            builder.set_claimant(
                full_name="Pending Extraction",
                date_of_birth=date(1900, 1, 1),
                case_file_reference=job_id,
                total_document_pages=len(segments),
            )

        # Add chronology entries
        if chronology_entries:
            builder.from_llm_chronology_entries(chronology_entries)

        report = builder.build()
        job["steps_completed"].append("report_build")

        # Step 5: Export to markdown and PDF
        job["current_step"] = "Exporting report"
        job["progress"] = 85

        from app.adapters.export import ReportExporter

        exporter = ReportExporter(output_dir="results")

        # Export markdown (legacy format)
        md_path = exporter.export_markdown(
            report_data=report,
            job_id=job_id,
        )

        # Build results dict first (needed for HTML generation)
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

        # Export PDF using HTML generation (matches UI styling)
        claimant_name = dde_result.get("claimant_name", "Unknown") if dde_result else "Unknown"
        pdf_path = exporter.export_pdf_from_results(
            results=results,
            job_id=job_id,
            title=f"Medical Chronology - {claimant_name}",
        )
        results["pdf_path"] = pdf_path

        job["steps_completed"].append("report_export")

        # Store final results
        job["results"] = results
        job["steps_completed"].append("report_generation")

        # Complete
        job["status"] = "completed"
        job["progress"] = 100
        job["current_step"] = "Complete"
        job["completed_at"] = datetime.now()

        # Record processing time
        if job.get("started_at"):
            processing_time = (job["completed_at"] - job["started_at"]).total_seconds()
            PROCESSING_TIME.observe(processing_time)

        # Persist completed job to disk
        if hasattr(active_jobs, 'persist'):
            active_jobs.persist(job_id)

        logger.info(f"ERE job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"ERE processing failed for job {job_id}: {e}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["traceback"] = traceback.format_exc()
        # Persist failed job to disk
        if hasattr(active_jobs, 'persist'):
            active_jobs.persist(job_id)


async def process_chartvision_job(
    job_id: str,
    active_jobs: Dict[str, Any],
) -> None:
    """
    Background task to process ChartVision job using full pipeline.

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
        from app.core.builders import ChartVisionBuilder

        pdf_adapter = PyMuPDFAdapter()
        exhibits = pdf_adapter.get_exhibit_page_ranges(file_path)
        logger.info(f"Extracted {len(exhibits)} exhibits from bookmarks")

        # Step 2: Categorize exhibits by section (A, B, D, E, F)
        job["current_step"] = "Categorizing exhibits by section"
        job["progress"] = 0.2

        # Add section_id based on exhibit_id pattern
        for exhibit in exhibits:
            exhibit_id = exhibit.get("exhibit_id", "")
            # Extract section letter from exhibit_id (e.g., "1F" -> "F", "2A" -> "A")
            if exhibit_id:
                section_match = exhibit_id[-1].upper() if exhibit_id[-1].isalpha() else ""
                exhibit["section_id"] = section_match

        # Step 3: Filter exhibits (keep all for now)
        job["current_step"] = "Filtering exhibits"
        job["progress"] = 0.3

        filtered_exhibits = exhibits
        logger.info(f"Processing {len(filtered_exhibits)} exhibits")

        # Helper to get section exhibits
        def get_section_exhibits(exhibits_list: List[Dict], section_id: str) -> List[Dict]:
            return [e for e in exhibits_list if e.get("section_id", "").upper() == section_id.upper()]

        # Step 4: Parse DDE from Section A for claimant/administrative data
        job["current_step"] = "Parsing DDE data"
        job["progress"] = 0.4

        section_a = get_section_exhibits(filtered_exhibits, "A")
        dde_result = {}

        if section_a and DDE_PARSER_AVAILABLE:
            try:
                # Filter to only DDE documents (not court orders, complaints, etc.)
                # Match "DDE" or "Disability Determination Explanation"
                def is_dde_exhibit(exhibit):
                    title = exhibit.get("title", "").upper()
                    return "DDE" in title or "DISABILITY DETERMINATION EXPLANATION" in title
                dde_exhibits = [s for s in section_a if is_dde_exhibit(s)]

                if not dde_exhibits:
                    logger.warning("No DDE documents found in Section A, skipping DDE extraction")
                else:
                    # Get the latest DDE by page number (most recent determination)
                    latest_a = max(dde_exhibits, key=lambda x: x.get("start_page", 0))
                    logger.info(f"Selected DDE exhibit: {latest_a.get('title', 'Unknown')[:60]} pages {latest_a.get('start_page')}-{latest_a.get('end_page')}")

                    # Use DDEParser with vision fallback for scanned pages
                    dde_parser = create_dde_parser()
                    parse_result = await dde_parser.parse(
                        pdf_path=file_path,
                        page_start=latest_a.get("start_page", 1),
                        page_end=latest_a.get("end_page"),
                    )
                    # Normalize to consistent API structure
                    dde_result = {
                        "fields": normalize_dde_result(
                            parse_result.get("fields", {}),
                            parse_result.get("extraction_mode", "text"),
                            parse_result.get("confidence", 0.0)
                        )
                    }
                    logger.info(f"DDE parsing completed: mode={parse_result.get('extraction_mode', 'text')}, confidence={parse_result.get('confidence', 0.0):.2f}")
            except Exception as e:
                logger.warning(f"DDE parsing failed: {e}")
                traceback.print_exc()
                dde_result = {}

        # Step 4.5: Extract F-section exhibits using bookmark-based extraction
        job["current_step"] = "Extracting F-section exhibits"
        job["progress"] = 0.5

        chronology_entries = []
        try:
            # Use the new utility to extract individual F-exhibits from bookmarks
            from app.core.extraction.utils import extract_f_exhibits_from_pdf
            from app.core.extraction import ChronologyEngine
            from app.adapters.llm import BedrockAdapter

            # Extract F-exhibits (limit to prevent timeout)
            f_exhibits = extract_f_exhibits_from_pdf(
                file_path,
                max_exhibits=MAX_EXHIBITS_PER_JOB,
                max_pages_per_exhibit=MAX_PAGES_PER_EXHIBIT
            )
            logger.info(f"Extracted {len(f_exhibits)} F-section exhibits")

            if f_exhibits:
                # Generate chronology via LLM
                job["current_step"] = "Generating medical chronology"
                job["progress"] = 0.6

                llm = BedrockAdapter()
                engine = ChronologyEngine(llm=llm)
                result = await engine.generate_chronology(
                    exhibits=f_exhibits,
                    case_info={"job_id": job_id}
                )

                # Extract entries from result
                if hasattr(result, 'events'):
                    for event in result.events:
                        if isinstance(event, dict):
                            chronology_entries.append(event)
                        else:
                            chronology_entries.append({
                                "date": str(getattr(event, 'date', '')) if hasattr(event, 'date') else "",
                                "provider": getattr(event, 'provider', ""),
                                "facility": getattr(event, 'facility', ""),
                                "occurrence": getattr(event, 'occurrence_treatment', getattr(event, 'summary', "")),
                                "exhibit_citation": getattr(event, 'exhibit_reference', getattr(event, 'source', "")),
                            })

            logger.info(f"Extracted {len(chronology_entries)} chronology entries")
        except Exception as e:
            logger.warning(f"Chronology extraction failed: {e}")
            logger.warning(f"Traceback: {traceback.format_exc()}")
            chronology_entries = []

        # Step 5: Build ChartVision report
        job["current_step"] = "Building ChartVision report"
        job["progress"] = 0.8

        builder = ChartVisionBuilder()

        # Populate from DDE if available
        if dde_result and dde_result.get("fields"):
            builder.from_dde_result(
                dde_result,
                case_reference=job_id,
                total_pages=len(exhibits),
            )
            logger.info("Populated builder from DDE result")
        else:
            # Fallback to basic info
            builder.set_claimant(
                full_name="Pending Extraction",
                date_of_birth=date(1900, 1, 1),
                case_file_reference=job_id,
                total_document_pages=len(exhibits),
            )
            builder.set_administrative(
                claim_type="Unknown",
                protective_filing_date=date.today(),
                alleged_onset_date=date.today(),
            )

        # Add chronology entries to builder
        if chronology_entries:
            builder.from_llm_chronology_entries(chronology_entries)

        report = builder.build()

        # Step 6: Generate PDF if enabled (default: true)
        pdf_path = None
        if job.get("options", {}).get("pdf_output", True):
            job["current_step"] = "Generating PDF report"
            job["progress"] = 0.9

            try:
                output_dir = Path("/tmp/chartvision_reports")
                output_dir.mkdir(exist_ok=True)
                pdf_output_path = str(output_dir / f"{job_id}.pdf")

                # Use MarkdownToPDFConverter for PDF generation
                from app.adapters.export import MarkdownToPDFConverter

                converter = MarkdownToPDFConverter()
                markdown_content = report.to_markdown()

                # Get claimant name for metadata if available
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
            except Exception as e:
                logger.warning(f"PDF generation failed (non-fatal): {e}")
                pdf_path = None

        # Store result
        job["status"] = "completed"
        job["progress"] = 1.0
        job["current_step"] = "Complete"
        job["completed_at"] = datetime.now()
        job["result"] = report.to_dict()
        job["pdf_path"] = pdf_path
        job["metadata"] = {
            "total_exhibits": len(exhibits),
            "filtered_exhibits": len(filtered_exhibits),
            "dde_parsed": bool(dde_result.get("fields")),
            "sections_processed": list(set(e.get("section_id") for e in filtered_exhibits)),
            "chronology_entries_count": len(chronology_entries),
            "pdf_generated": pdf_path is not None,
        }

        # Persist completed job to disk
        if hasattr(active_jobs, 'persist'):
            active_jobs.persist(job_id)

        logger.info(f"ChartVision job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"ChartVision processing failed for job {job_id}: {e}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["traceback"] = traceback.format_exc()
        # Persist failed job to disk
        if hasattr(active_jobs, 'persist'):
            active_jobs.persist(job_id)


__all__ = [
    "process_ere_job",
    "process_chartvision_job",
]
