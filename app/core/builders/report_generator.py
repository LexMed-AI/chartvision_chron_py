"""
ChartVision Medical Chronology Report Generator

Generates 12-section medical chronology reports matching SandefurChron.pdf format.
Uses chartvision_chronology_template.yaml for field definitions.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.models.chartvision import (
    ClaimantData,
    AdministrativeData,
    AllegedImpairment,
    MedicallyDeterminableImpairment,
    MedicalSourceOpinion,
    SurgicalProcedure,
    DiagnosticTest,
    Medication,
    OccupationalHistory,
    FunctionalLimitation,
    ChronologyEntry,
    ChartVisionReportData,
)

logger = logging.getLogger(__name__)

# Re-export models for backwards compatibility
__all__ = [
    "ChartVisionReportGenerator",
    "ChartVisionReportData",
    "ClaimantData",
    "AdministrativeData",
    "AllegedImpairment",
    "MedicallyDeterminableImpairment",
    "MedicalSourceOpinion",
    "SurgicalProcedure",
    "DiagnosticTest",
    "Medication",
    "OccupationalHistory",
    "FunctionalLimitation",
    "ChronologyEntry",
]


class ChartVisionReportGenerator:
    """
    Generates ChartVision-format medical chronology reports.

    Produces 12-section markdown matching SandefurChron.pdf structure:
    1. Claimant Identification
    2. Administrative Data & Critical Dates
    3. Alleged Impairments Inventory
    4. Medically Determinable Impairments
    5. Medical Source Opinions
    6. Surgical History Inventory
    7. Diagnostic Testing Summary
    8. Current Medication Profile
    9. Occupational History Profile
    10. Functional Capacity Indicators
    11. Missing Medical Evidence
    12. Comprehensive Medical Evidence Table
    """

    def __init__(self):
        self.date_format = "%m/%d/%Y"

    def _format_date(self, dt: Optional[datetime]) -> str:
        """Format datetime to MM/DD/YYYY"""
        if dt is None:
            return ""
        return dt.strftime(self.date_format)

    def _mask_ssn(self, ssn: Optional[str]) -> str:
        """Mask SSN to show only last 4 digits"""
        if not ssn:
            return ""
        # Remove any dashes/spaces
        clean_ssn = ssn.replace("-", "").replace(" ", "")
        if len(clean_ssn) >= 4:
            return f"XXX-XX-{clean_ssn[-4:]}"
        return ""

    def generate_section_1_claimant_identification(
        self, claimant: ClaimantData
    ) -> str:
        """Generate Section 1: Claimant Identification"""
        masked_ssn = self._mask_ssn(claimant.ssn) if claimant.ssn else "N/A"
        bnc = claimant.bnc_code if claimant.bnc_code else "N/A"

        return f"""## SECTION 1: CLAIMANT IDENTIFICATION

| **Field** | **Value** | **Field** | **Value** |
|-----------|-----------|-----------|-----------|
| **Full Name** | {claimant.full_name} | **SSN** | {masked_ssn} |
| **Date of Birth** | {self._format_date(claimant.date_of_birth)} | **BNC Code** | {bnc} |
| **Case File Reference** | {claimant.case_file_reference} | **Total Document Pages** | {claimant.total_document_pages} |

---

"""

    def generate_section_2_administrative_data(
        self, admin: AdministrativeData
    ) -> str:
        """Generate Section 2: Administrative Data & Critical Dates"""
        pfd = self._format_date(admin.protective_filing_date) or "N/A"
        aod = self._format_date(admin.alleged_onset_date) or "N/A"
        dli = self._format_date(admin.date_last_insured) or "N/A"
        initial = self._format_date(admin.initial_denial_date) or "N/A"
        recon = self._format_date(admin.reconsideration_denial_date) or "N/A"
        alj = self._format_date(admin.alj_hearing_date) or "N/A"

        return f"""## SECTION 2: ADMINISTRATIVE DATA & CRITICAL DATES

| **Case Information** | **Value** | **Denial Dates** | **Date** |
|----------------------|-----------|------------------|----------|
| **Claim Type** | {admin.claim_type} | **Initial Denial** | {initial} |
| **Protective Filing Date (PFD)** | {pfd} | **Reconsideration Denial** | {recon} |
| **Alleged Onset Date (AOD)** | {aod} | **ALJ Hearing Date** | {alj} |
| **Date Last Insured (DLI)** | {dli} | | |

---

"""

    def generate_section_3_alleged_impairments(
        self, impairments: List[AllegedImpairment]
    ) -> str:
        """Generate Section 3: Alleged Impairments Inventory"""
        rows = []
        for imp in impairments:
            rows.append(f"| {imp.condition_name} | {imp.source} |")

        table_rows = "\n".join(rows) if rows else "| No alleged impairments documented | N/A |"

        return f"""## SECTION 3: ALLEGED IMPAIRMENTS INVENTORY

**Note: Extract claimant's own words from forms - do not interpret**

| **Alleged Condition** | **Source** |
|-----------------------|------------|
{table_rows}

---

"""

    def generate_section_4_mdi(
        self, mdis: List[MedicallyDeterminableImpairment]
    ) -> str:
        """Generate Section 4: Medically Determinable Impairments"""
        rows = []
        for mdi in mdis:
            date_str = self._format_date(mdi.first_documented) or "N/A"
            icd = mdi.icd_code or "N/A"
            severity = mdi.severity or "N/A"
            rows.append(f"| {mdi.diagnosis} | {icd} | {severity} | {date_str} | {mdi.source} |")

        table_rows = "\n".join(rows) if rows else "| No MDIs documented | N/A | N/A | N/A | N/A |"

        return f"""## SECTION 4: MEDICALLY DETERMINABLE IMPAIRMENTS

| **Confirmed Diagnosis** | **ICD Code** | **Severity** | **First Documented** | **Source** |
|-------------------------|--------------|--------------|----------------------|------------|
{table_rows}

---

"""

    def generate_section_5_medical_source_opinions(
        self, opinions: List[MedicalSourceOpinion]
    ) -> str:
        """Generate Section 5: Medical Source Opinions"""
        rows = []
        for op in opinions:
            date_str = self._format_date(op.date)
            rows.append(f"| {date_str} | {op.medical_source} | {op.relationship} | {op.opinion_type} | {op.source} |")

        table_rows = "\n".join(rows) if rows else "| N/A | No medical source opinions documented | N/A | N/A | N/A |"

        return f"""## SECTION 5: MEDICAL SOURCE OPINIONS

| **Date** | **Medical Source** | **Relationship** | **Opinion Type** | **Source** |
|----------|--------------------|--------------------|------------------|------------|
{table_rows}

---

"""

    def generate_section_6_surgical_history(
        self, procedures: List[SurgicalProcedure]
    ) -> str:
        """Generate Section 6: Surgical History Inventory"""
        rows = []
        for proc in procedures:
            date_str = self._format_date(proc.date)
            rows.append(f"| {date_str} | {proc.procedure} | {proc.facility_type} | {proc.source} |")

        table_rows = "\n".join(rows) if rows else "| N/A | No surgical history documented | N/A | N/A |"

        return f"""## SECTION 6: SURGICAL HISTORY INVENTORY

| **Date** | **Procedure** | **Facility Type** | **Source** |
|----------|---------------|-------------------|------------|
{table_rows}

---

"""

    def generate_section_7_diagnostic_testing(
        self, tests: List[DiagnosticTest]
    ) -> str:
        """Generate Section 7: Diagnostic Testing Summary"""
        rows = []
        for test in tests:
            date_str = self._format_date(test.date)
            category = test.category or "N/A"
            rows.append(f"| {date_str} | {test.test_name} | {category} | {test.results_summary} | {test.source} |")

        table_rows = "\n".join(rows) if rows else "| N/A | No diagnostic tests documented | N/A | N/A | N/A |"

        return f"""## SECTION 7: DIAGNOSTIC TESTING SUMMARY

| **Date** | **Test** | **Category** | **Results (Succinct)** | **Source** |
|----------|----------|--------------|------------------------|------------|
{table_rows}

---

"""

    def generate_section_8_medication_profile(
        self, medications: List[Medication]
    ) -> str:
        """Generate Section 8: Current Medication Profile"""
        rows = []
        for med in medications:
            dosage = med.dosage or "N/A"
            frequency = med.frequency or "N/A"
            indication = med.indication or "N/A"
            rows.append(f"| {med.medication} | {dosage} | {frequency} | {indication} | {med.source} |")

        table_rows = "\n".join(rows) if rows else "| No medications documented | N/A | N/A | N/A | N/A |"

        return f"""## SECTION 8: CURRENT MEDICATION PROFILE

| **Medication** | **Dosage** | **Frequency** | **Indication** | **Source** |
|----------------|------------|---------------|----------------|------------|
{table_rows}

---

"""

    def generate_section_9_occupational_history(
        self, jobs: List[OccupationalHistory]
    ) -> str:
        """Generate Section 9: Occupational History Profile"""
        rows = []
        for job in jobs:
            exertional = job.exertional_level or "N/A"
            rows.append(f"| {job.position_title} | {job.employment_period} | {exertional} | {job.source} |")

        table_rows = "\n".join(rows) if rows else "| No occupational history documented | N/A | N/A | N/A |"

        return f"""## SECTION 9: OCCUPATIONAL HISTORY PROFILE

| **Position Title** | **Employment Period** | **Exertional Level** | **Source** |
|--------------------|----------------------|----------------------|------------|
{table_rows}

---

"""

    def generate_section_10_functional_capacity(
        self, limitations: List[FunctionalLimitation]
    ) -> str:
        """Generate Section 10: Functional Capacity Indicators"""
        rows = []
        for lim in limitations:
            examples = lim.specific_examples or "N/A"
            rows.append(f"| {lim.activity_domain} | {lim.reported_limitation} | {examples} | {lim.source} |")

        table_rows = "\n".join(rows) if rows else "| No functional limitations documented | N/A | N/A | N/A |"

        return f"""## SECTION 10: FUNCTIONAL CAPACITY INDICATORS

**Note: Claimant statements only - extract from Section E forms**

| **Activity Domain** | **Reported Limitation** | **Specific Examples** | **Source** |
|---------------------|-------------------------|----------------------|------------|
{table_rows}

---

"""

    def generate_section_11_missing_evidence(
        self, gaps: List[Dict[str, Any]]
    ) -> str:
        """Generate Section 11: Missing Medical Evidence"""
        if not gaps:
            content = "No significant gaps in medical evidence identified."
        else:
            items = []
            for gap in gaps:
                desc = gap.get("gap_description", "Unknown gap")
                period = gap.get("time_period", "")
                if period:
                    items.append(f"- {desc} ({period})")
                else:
                    items.append(f"- {desc}")
            content = "\n".join(items)

        return f"""## SECTION 11: MISSING MEDICAL EVIDENCE

{content}

---

"""

    def generate_section_12_comprehensive_chronology(
        self, entries: List[ChronologyEntry]
    ) -> str:
        """Generate Section 12: Comprehensive Patient History Medical Evidence Table"""
        # Sort entries chronologically
        sorted_entries = sorted(entries, key=lambda e: e.date)

        rows = []
        for entry in sorted_entries:
            # Use MM/DD/YYYY format for DOS (Date of Service) for user readability
            date_str = entry.date.strftime("%m/%d/%Y") if entry.date else ""
            # Escape pipe characters in content (but not <br> tags)
            occurrence = entry.occurrence_treatment.replace("|", "\\|") if entry.occurrence_treatment else "—"
            rows.append(
                f"| {date_str} | {entry.provider_specialty} | {entry.facility} | {occurrence} | {entry.source} |"
            )

        table_rows = "\n".join(rows) if rows else "| N/A | No medical events documented | N/A | N/A | N/A |"

        return f"""## SECTION 12: COMPREHENSIVE PATIENT HISTORY MEDICAL EVIDENCE TABLE

| **DOS** | **Provider** | **Facility** | **Occurrence/Treatment** | **Source** |
|---------|--------------|--------------|--------------------------|------------|
{table_rows}

---

"""

    def generate_diagnoses_summary(self, entries: List[ChronologyEntry]) -> str:
        """Generate Diagnoses Summary from chronology entries."""
        # Extract unique diagnoses from occurrence_treatment
        diagnoses = set()
        for entry in entries:
            occ = entry.occurrence_treatment
            # Parse diagnoses from formatted text (look for **Dx:** pattern)
            if "**Dx:**" in occ:
                # Extract text after **Dx:** until next **
                start = occ.find("**Dx:**") + 7
                end = occ.find("**", start)
                if end == -1:
                    end = occ.find("<br>", start)
                if end == -1:
                    end = len(occ)
                dx_text = occ[start:end].strip()
                # Split by semicolons or commas
                for dx in dx_text.replace(";", ",").split(","):
                    dx = dx.strip()
                    if dx and len(dx) > 3:
                        diagnoses.add(dx)

        if not diagnoses:
            return ""

        # Sort and number diagnoses
        sorted_dx = sorted(diagnoses)
        rows = [f"{i+1}. **{dx}**" for i, dx in enumerate(sorted_dx)]

        return f"""## Diagnoses Summary

{chr(10).join(rows)}

---

"""

    def generate_providers_summary(self, entries: List[ChronologyEntry]) -> str:
        """Generate Healthcare Providers summary from chronology entries."""
        # Extract unique provider/facility pairs
        providers = {}
        for entry in entries:
            provider = entry.provider_specialty
            facility = entry.facility
            if provider and provider != "Unknown" and provider != "Not Specified":
                key = provider
                if key not in providers:
                    providers[key] = facility

        if not providers:
            return ""

        rows = []
        for provider, facility in sorted(providers.items()):
            rows.append(f"| {provider} | {facility} |")

        return f"""## Healthcare Providers

| Provider | Facility |
|----------|----------|
{chr(10).join(rows)}

---

"""

    def generate_full_report(self, data: ChartVisionReportData) -> str:
        """Generate complete ChartVision report with all sections"""
        generated_date = datetime.now().strftime("%m/%d/%Y %H:%M")

        # Calculate summary statistics
        num_events = len(data.chronology_entries)
        providers = set(e.provider_specialty for e in data.chronology_entries if e.provider_specialty != "Unknown")
        num_providers = len(providers)

        header = f"""# CHART VISION MEDICAL CHRONOLOGY

**Claimant:** {data.claimant.full_name}
**Case File:** {data.claimant.case_file_reference}
**Generated:** {generated_date}

---

**Summary:** {num_events} Events | {num_providers} Providers

---

"""

        sections = [
            self.generate_section_1_claimant_identification(data.claimant),
            self.generate_section_2_administrative_data(data.administrative),
            self.generate_section_3_alleged_impairments(data.alleged_impairments),
            self.generate_section_4_mdi(data.mdis),
            self.generate_section_5_medical_source_opinions(data.medical_source_opinions),
            self.generate_section_6_surgical_history(data.surgical_history),
            self.generate_section_7_diagnostic_testing(data.diagnostic_tests),
            self.generate_section_8_medication_profile(data.medications),
            self.generate_section_9_occupational_history(data.occupational_history),
            self.generate_section_10_functional_capacity(data.functional_limitations),
            self.generate_section_11_missing_evidence(data.missing_evidence),
            self.generate_section_12_comprehensive_chronology(data.chronology_entries),
            self.generate_diagnoses_summary(data.chronology_entries),
            self.generate_providers_summary(data.chronology_entries),
        ]

        footer = """
---

**CONFIDENTIALITY NOTICE:** This document contains protected health information.

*Generative AI may have been used to assist in data extraction.*
"""

        return header + "".join(sections) + footer
