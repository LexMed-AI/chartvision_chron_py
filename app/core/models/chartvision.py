"""
ChartVision Data Models

Single source of truth for all ChartVision report dataclasses.
All ChartVision components should import models from here.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.core.models.citation import Citation


@dataclass
class ClaimantData:
    """Section 1: Claimant Identification data."""
    full_name: str
    date_of_birth: datetime
    case_file_reference: str
    total_document_pages: int
    ssn: Optional[str] = None
    bnc_code: Optional[str] = None


@dataclass
class AdministrativeData:
    """Section 2: Administrative Data & Critical Dates."""
    claim_type: str  # DIB, SSI, Concurrent
    protective_filing_date: Optional[datetime] = None
    alleged_onset_date: Optional[datetime] = None
    date_last_insured: Optional[datetime] = None
    initial_denial_date: Optional[datetime] = None
    reconsideration_denial_date: Optional[datetime] = None
    alj_hearing_date: Optional[datetime] = None


@dataclass
class AllegedImpairment:
    """Section 3: Single alleged impairment."""
    condition_name: str
    source: str  # Ex. #E@page


@dataclass
class MedicallyDeterminableImpairment:
    """Section 4: MDI with medical evidence."""
    diagnosis: str
    icd_code: Optional[str] = None
    severity: Optional[str] = None  # Severe, Non-Severe
    first_documented: Optional[datetime] = None
    source: str = ""


@dataclass
class MedicalSourceOpinion:
    """Section 5: Medical Source Opinion."""
    date: datetime
    medical_source: str
    relationship: str  # DDS, Treating, CE, Non-exam, VA, LTD, Workers Comp
    opinion_type: str  # RFC, MSS, CE Report, VA Rating, etc.
    source: str


@dataclass
class SurgicalProcedure:
    """Section 6: Surgical procedure."""
    date: datetime
    procedure: str
    facility_type: str  # Hospital, Outpatient, ASC
    source: str


@dataclass
class DiagnosticTest:
    """Section 7: Diagnostic test."""
    date: datetime
    test_name: str
    category: Optional[str] = None
    results_summary: str = ""
    source: str = ""


@dataclass
class Medication:
    """Section 8: Medication."""
    medication: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    indication: Optional[str] = None
    source: str = ""


@dataclass
class OccupationalHistory:
    """Section 9: Job history entry."""
    position_title: str
    employment_period: str  # MM/YYYY - MM/YYYY
    exertional_level: Optional[str] = None
    source: str = ""


@dataclass
class FunctionalLimitation:
    """Section 10: Functional limitation from claimant."""
    activity_domain: str
    reported_limitation: str
    specific_examples: Optional[str] = None
    source: str = ""


@dataclass
class ChronologyEntry:
    """Section 12: Single chronology entry."""
    date: datetime
    provider_specialty: str
    facility: str
    occurrence_treatment: str
    source: str  # Exhibit ID (e.g., "10F") - kept for backwards compatibility
    page_number: Optional[int] = None
    citation: Optional[Union[Citation, Dict[str, Any]]] = None  # Full citation with page info

    @property
    def formatted_source(self) -> str:
        """Get formatted source citation for display.

        Returns page-specific citation if available, otherwise exhibit ID.
        """
        if self.citation:
            if isinstance(self.citation, Citation):
                return self.citation.format()
            elif isinstance(self.citation, dict) and "formatted" in self.citation:
                return self.citation["formatted"]
            elif isinstance(self.citation, dict) and "absolute_page" in self.citation:
                # Build formatted citation from dict
                exhibit_id = self.citation.get("exhibit_id", self.source)
                abs_page = self.citation.get("absolute_page")
                rel_page = self.citation.get("relative_page")
                if rel_page:
                    return f"{exhibit_id}@{rel_page} (p.{abs_page})"
                elif abs_page:
                    return f"{exhibit_id} (p.{abs_page})"
        return self.source


@dataclass
class ChartVisionReportData:
    """Complete data for ChartVision report generation."""
    claimant: ClaimantData
    administrative: AdministrativeData
    alleged_impairments: List[AllegedImpairment] = field(default_factory=list)
    mdis: List[MedicallyDeterminableImpairment] = field(default_factory=list)
    medical_source_opinions: List[MedicalSourceOpinion] = field(default_factory=list)
    surgical_history: List[SurgicalProcedure] = field(default_factory=list)
    diagnostic_tests: List[DiagnosticTest] = field(default_factory=list)
    medications: List[Medication] = field(default_factory=list)
    occupational_history: List[OccupationalHistory] = field(default_factory=list)
    functional_limitations: List[FunctionalLimitation] = field(default_factory=list)
    missing_evidence: List[Dict[str, Any]] = field(default_factory=list)
    chronology_entries: List[ChronologyEntry] = field(default_factory=list)

    # Metadata
    schema_version: str = "2.0.0"
    generated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report data to dictionary."""
        return asdict(self)

    def to_markdown(self) -> str:
        """Generate 12-section Markdown report."""
        from app.core.builders.report_generator import ChartVisionReportGenerator
        generator = ChartVisionReportGenerator()
        return generator.generate_full_report(self)
