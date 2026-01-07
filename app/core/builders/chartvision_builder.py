"""
ChartVision Report Builder

Assembles ChartVision reports from extracted ERE section data.
Follows builder pattern for flexible construction.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.models.chartvision import (
    ChartVisionReportData,
    ClaimantData,
    AdministrativeData,
    AllegedImpairment,
    MedicalSourceOpinion,
    ChronologyEntry,
)
from app.core.builders.occurrence_formatter import OccurrenceFormatter
from app.core.builders.date_utils import parse_date, to_datetime
from app.core.builders.source_formatter import format_source
from app.core.builders.chronology_processor import process_chronology

logger = logging.getLogger(__name__)


class ChartVisionBuilder:
    """Builder for constructing ChartVision reports."""

    def __init__(self):
        """Initialize builder with empty state."""
        self._claimant: Optional[ClaimantData] = None
        self._administrative: Optional[AdministrativeData] = None
        self._impairments: List[AllegedImpairment] = []
        self._opinions: List[MedicalSourceOpinion] = []
        self._chronology: List[ChronologyEntry] = []
        # Section-aware tracking for multi-exhibit processing
        self._section_a_results: List[Dict[str, Any]] = []
        self._section_e_results: List[Dict[str, Any]] = []
        self._section_f_results: List[Dict[str, Any]] = []
        # Data-driven occurrence formatter (replaces 12 _format_* methods)
        self._formatter = OccurrenceFormatter()

    def set_claimant(
        self,
        full_name: str,
        date_of_birth: date,
        case_file_reference: str,
        total_document_pages: int,
        ssn_last_four: Optional[str] = None,
    ) -> "ChartVisionBuilder":
        """Set claimant identification (Section 1)."""
        # Convert date to datetime if needed
        dob_datetime = to_datetime(date_of_birth)
        self._claimant = ClaimantData(
            full_name=full_name,
            date_of_birth=dob_datetime,
            case_file_reference=case_file_reference,
            total_document_pages=total_document_pages,
            ssn=ssn_last_four,
        )
        return self

    def set_administrative(
        self,
        claim_type: str,
        protective_filing_date: date,
        alleged_onset_date: date,
        date_last_insured: Optional[date] = None,
    ) -> "ChartVisionBuilder":
        """Set administrative data (Section 2)."""
        self._administrative = AdministrativeData(
            claim_type=claim_type,
            protective_filing_date=to_datetime(protective_filing_date),
            alleged_onset_date=to_datetime(alleged_onset_date),
            date_last_insured=to_datetime(date_last_insured) if date_last_insured else None,
        )
        return self

    def add_section_a(
        self,
        dde_result: Dict[str, Any],
        case_reference: str,
        total_pages: int,
    ) -> "ChartVisionBuilder":
        """
        Add Section A (DDE) result with tracking.

        Tracks all DDE results for later last-2 filtering.
        Also populates claimant and administrative data.

        Args:
            dde_result: Output from DDEParser.parse()
            case_reference: Case file reference number
            total_pages: Total document page count

        Returns:
            Self for method chaining
        """
        # Track the result with metadata
        self._section_a_results.append({
            "dde_result": dde_result,
            "case_reference": case_reference,
            "total_pages": total_pages,
        })

        # Also populate builder via existing method
        self.from_dde_result(dde_result, case_reference, total_pages)

        return self

    def get_last_two_ddes(self) -> List[Dict[str, Any]]:
        """
        Get the last 2 DDE results (most recent).

        Per ERE processing rules, only the last 2 DDEs in the file
        should be used for building the final report.

        Returns:
            List of last 2 DDE result dictionaries (or fewer if less exist)
        """
        if len(self._section_a_results) <= 2:
            return self._section_a_results.copy()
        return self._section_a_results[-2:]

    def add_section_e(
        self,
        e_result: Dict[str, Any],
    ) -> "ChartVisionBuilder":
        """
        Add Section E (Disability Report) result.

        Tracks E-section results and extracts diagnoses as impairments.

        Args:
            e_result: Extracted data from E-section document

        Returns:
            Self for method chaining
        """
        # Track the result
        self._section_e_results.append(e_result)

        # Extract diagnoses as impairments
        for diagnosis in e_result.get("diagnoses", []):
            if isinstance(diagnosis, str):
                self.add_impairment(condition=diagnosis)
            elif isinstance(diagnosis, dict):
                self.add_impairment(
                    condition=diagnosis.get("name", "Unknown"),
                    source=diagnosis.get("source", ""),
                )

        return self

    def add_section_f(
        self,
        f_result: Dict[str, Any],
    ) -> "ChartVisionBuilder":
        """
        Add Section F (Medical Records) result.

        Tracks F-section results and extracts chronology entries.

        Args:
            f_result: Extracted data from F-section medical records

        Returns:
            Self for method chaining
        """
        # Track the result
        self._section_f_results.append(f_result)

        # Extract chronology entries
        for entry in f_result.get("chronology_entries", []):
            if "error" in entry:
                continue

            entry_date = parse_date(entry.get("date"))
            if not entry_date:
                continue

            self.add_chronology_entry(
                date=entry_date,
                provider=entry.get("provider", "Unknown"),
                facility=entry.get("facility", "Unknown"),
                occurrence=entry.get("occurrence", ""),
                source=entry.get("exhibit_citation", "") or entry.get("exhibit_reference", ""),
                citation=entry.get("citation"),
            )

        return self

    def add_impairment(
        self,
        condition: str,
        source: Optional[str] = None,
    ) -> "ChartVisionBuilder":
        """Add alleged impairment (Section 3)."""
        self._impairments.append(
            AllegedImpairment(
                condition_name=condition,
                source=source or "",
            )
        )
        return self

    def add_chronology_entry(
        self,
        date: date,
        provider: str,
        facility: str,
        occurrence: str,
        source: str,
        page_number: Optional[int] = None,
        citation: Optional[Any] = None,
    ) -> "ChartVisionBuilder":
        """Add chronology entry (Section 12).

        Args:
            date: Date of service
            provider: Provider name/specialty
            facility: Facility name
            occurrence: Treatment/occurrence description
            source: Exhibit ID (e.g., "10F")
            page_number: Optional page number within exhibit
            citation: Optional Citation object or dict with page info
        """
        self._chronology.append(
            ChronologyEntry(
                date=to_datetime(date),
                provider_specialty=provider,
                facility=facility,
                occurrence_treatment=occurrence,
                source=source,
                page_number=page_number,
                citation=citation,
            )
        )
        return self

    def from_haiku_results(
        self, haiku_results: List[Dict[str, Any]]
    ) -> "ChartVisionBuilder":
        """
        Populate builder from Haiku extraction results.

        Extracts claimant data from E-section results,
        chronology from F-section results.
        """
        for result in haiku_results:
            exhibit_id = result.get("exhibit_id", "")

            # Extract claimant from E-section
            if "E" in exhibit_id and self._claimant is None:
                self._extract_claimant_from_e_section(result)

            # Extract diagnoses as impairments
            for diagnosis in result.get("diagnoses", []):
                if isinstance(diagnosis, str):
                    self.add_impairment(condition=diagnosis)
                elif isinstance(diagnosis, dict):
                    self.add_impairment(
                        condition=diagnosis.get("name", "Unknown"),
                        source=diagnosis.get("source", ""),
                    )

        return self

    def _extract_claimant_from_e_section(self, result: Dict[str, Any]) -> None:
        """Extract claimant identification from E-section result."""
        name = result.get("claimant_name", "Unknown")
        dob = parse_date(result.get("date_of_birth"))

        if dob is None:
            dob = date(1970, 1, 1)  # Placeholder

        self._claimant = ClaimantData(
            full_name=name,
            date_of_birth=to_datetime(dob),
            case_file_reference=result.get("case_reference", "Unknown"),
            total_document_pages=result.get("total_pages", 0),
        )

    def from_dde_result(
        self,
        dde_result: Dict[str, Any],
        case_reference: str,
        total_pages: int,
    ) -> "ChartVisionBuilder":
        """
        Populate builder from DDE parser results.

        Args:
            dde_result: Output from DDEParser.parse()
            case_reference: Case file reference number
            total_pages: Total document page count

        Returns:
            Self for method chaining
        """
        fields = dde_result.get("fields", {})
        determination = dde_result.get("determinationHistory", {})
        mdi = dde_result.get("medicallyDeterminableImpairments", {})

        # DDE parser returns nested structure: fields.case_metadata contains claimant info
        case_metadata = fields.get("case_metadata", {})

        # Parse claimant data - check case_metadata first, then fall back to top-level fields
        claimant_name = case_metadata.get("claimant_name") or fields.get("claimant_name", "Unknown")
        dob_str = case_metadata.get("date_of_birth") or fields.get("date_of_birth")
        dob = parse_date(dob_str) if dob_str else date(1900, 1, 1)
        ssn_last_four = case_metadata.get("ssn_last_four") or fields.get("ssn_last_four")

        self.set_claimant(
            full_name=claimant_name,
            date_of_birth=dob,
            case_file_reference=case_reference,
            total_document_pages=total_pages,
            ssn_last_four=ssn_last_four,
        )

        # Parse administrative data - check case_metadata first, then top-level fields
        claim_type = case_metadata.get("claim_type") or fields.get("claim_type", "Unknown")
        onset_str = case_metadata.get("alleged_onset_date") or fields.get("alleged_onset_date")
        filing_str = case_metadata.get("protective_filing_date") or fields.get("protective_filing_date")
        dli_str = case_metadata.get("date_last_insured") or fields.get("date_last_insured")

        onset_date = parse_date(onset_str) if onset_str else date.today()
        filing_date = parse_date(filing_str) if filing_str else date.today()
        dli_date = parse_date(dli_str) if dli_str else None

        # Parse determination dates
        initial_denial = None
        recon_denial = None
        if determination.get("initial", {}).get("determinationDate"):
            initial_denial = parse_date(determination["initial"]["determinationDate"])
        if determination.get("reconsideration", {}).get("determinationDate"):
            recon_denial = parse_date(determination["reconsideration"]["determinationDate"])

        self.set_administrative(
            claim_type=claim_type,
            protective_filing_date=filing_date,
            alleged_onset_date=onset_date,
            date_last_insured=dli_date,
        )

        # Set denial dates directly on the object
        if initial_denial:
            self._administrative.initial_denial_date = to_datetime(initial_denial)
        if recon_denial:
            self._administrative.reconsideration_denial_date = to_datetime(recon_denial)

        # Parse impairments from MDI
        established = mdi.get("established", [])
        for imp in established:
            condition = imp.get("condition", "")
            if condition:
                self.add_impairment(condition=condition, source=imp.get("source", ""))

        return self

    def from_llm_chronology_entries(
        self,
        entries: List[Dict[str, Any]],
    ) -> "ChartVisionBuilder":
        """
        Populate chronology from LLM extraction results.

        Args:
            entries: List of extracted chronology entries from UnifiedChronologyEngine

        Returns:
            Self for method chaining
        """
        for entry in entries:
            # Skip error entries
            if "error" in entry:
                continue

            # Parse date
            date_str = entry.get("date")
            entry_date = parse_date(date_str) if date_str else None
            if not entry_date:
                continue  # Skip entries without valid dates

            # Build occurrence string from occurrence_treatment dict
            occurrence = self._format_occurrence_treatment(entry)

            # Build source from exhibit_reference + page_range
            source = format_source(entry)

            self.add_chronology_entry(
                date=entry_date,
                provider=entry.get("provider", "Unknown"),
                facility=entry.get("facility", "Unknown"),
                occurrence=occurrence,
                source=source,
                citation=entry.get("citation"),
            )

        return self

    def _format_occurrence_treatment(self, entry: Dict[str, Any]) -> str:
        """Format occurrence_treatment dict into readable string with bold labels and <br> separators.

        Uses data-driven OccurrenceFormatter for all visit types.
        """
        # Handle both formats: nested dict or simple string
        occ = entry.get("occurrence_treatment")
        if occ is None:
            return entry.get("occurrence", "")

        if isinstance(occ, str):
            return occ

        if not isinstance(occ, dict):
            return str(occ)

        # Check if occurrence_treatment is empty - provide fallback with raw_text_preview
        if self._is_empty_occurrence_dict(occ):
            # Try to use raw_text_preview if available (from chunk merge fallback)
            raw_preview = entry.get("raw_text_preview", "")
            if raw_preview:
                # Truncate and clean up for display
                preview = raw_preview[:200].replace("\n", " ").strip()
                return f"**[Review Required]** Content extraction incomplete.<br>**Raw snippet:** {preview}..."
            return "**[Review Required]** Content could not be extracted."

        # Determine visit_type (explicit or inferred)
        visit_type = entry.get("visit_type", "")
        if not visit_type:
            visit_type = self._infer_visit_type(occ)

        # Delegate to data-driven formatter
        result = self._formatter.format(visit_type, occ)
        return result if result else "—"

    def _infer_visit_type(self, occ: Dict[str, Any]) -> str:
        """Infer visit type from occurrence fields when not explicitly set."""
        if occ.get("test_name") or occ.get("test"):
            return "lab_result"
        if occ.get("imaging_type") or occ.get("procedure_type"):
            return "imaging_report"
        if occ.get("therapy_type"):
            return "therapy_eval"
        if occ.get("opinion_type") or occ.get("functional_limitations"):
            return "medical_source_statement"
        return "office_visit"

    def _is_empty_occurrence_dict(self, occ: Dict[str, Any]) -> bool:
        """Check if occurrence_treatment dict has no meaningful content."""
        if not occ:
            return True

        # Check if all values are empty/None (excluding metadata keys)
        skip_keys = {"visit_type", "applies_to"}
        for key, value in occ.items():
            if key in skip_keys:
                continue
            if value:
                if isinstance(value, str) and value.strip():
                    return False
                if isinstance(value, list) and len(value) > 0:
                    return False
                if isinstance(value, dict) and any(v for v in value.values() if v):
                    return False
        return True

    def build(self) -> ChartVisionReportData:
        """Build the final ChartVision report."""
        # Ensure required sections have defaults
        if self._claimant is None:
            self._claimant = ClaimantData(
                full_name="Unknown",
                date_of_birth=datetime(1970, 1, 1),
                case_file_reference="Unknown",
                total_document_pages=0,
            )

        if self._administrative is None:
            self._administrative = AdministrativeData(
                claim_type="Unknown",
                protective_filing_date=datetime.now(),
                alleged_onset_date=datetime.now(),
            )

        # Process chronology: group labs, deduplicate, sort
        processed = process_chronology(self._chronology)

        return ChartVisionReportData(
            claimant=self._claimant,
            administrative=self._administrative,
            alleged_impairments=self._impairments,
            chronology_entries=processed,
            generated_at=datetime.now().isoformat(),
        )
