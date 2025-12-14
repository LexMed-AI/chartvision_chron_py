"""
DDE Result Normalizer.

Transforms DDE parser output to consistent API structures.
Handles both vision (nested) and text (flat) extraction formats.
"""
from typing import Any, Dict, List


def normalize_dde_result(
    fields: Dict[str, Any],
    extraction_mode: str,
    confidence: float,
) -> Dict[str, Any]:
    """
    Normalize DDE extraction result to consistent API structure.

    Vision extraction returns nested structure (case_metadata, physical_rfc_assessment, etc.)
    Text extraction returns flat fields. This normalizes both to a consistent structure.

    Args:
        fields: Raw fields from DDE parser
        extraction_mode: "text" or "vision"
        confidence: Extraction confidence score (0.0-1.0)

    Returns:
        Normalized dictionary with consistent field names
    """
    result = {
        "extraction_mode": extraction_mode,
        "confidence": confidence,
    }

    case_metadata = fields.get("case_metadata", {})
    if case_metadata:
        # Vision extraction - extract from nested structure
        _extract_case_metadata(result, case_metadata)
        _extract_rfc_assessment(result, fields)
        _extract_mental_rfc(result, fields)
        _extract_impairments(result, fields)
        _extract_determination(result, fields)
        _extract_findings(result, fields)

        # Evidence and consultative exam
        result["evidence_received"] = fields.get("evidence_received", [])
        result["consultative_examination"] = fields.get("consultative_examination")

        # Keep original nested structure for detailed views
        result["raw_fields"] = fields
    else:
        # Flat structure (text extraction) - pass through
        result.update(fields)

    return result


def _extract_case_metadata(result: Dict[str, Any], case_metadata: Dict[str, Any]) -> None:
    """Extract case metadata fields from nested structure."""
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


def _extract_rfc_assessment(result: Dict[str, Any], fields: Dict[str, Any]) -> None:
    """Extract Physical RFC assessment from nested structure."""
    rfc = fields.get("physical_rfc_assessment", {})
    if not rfc:
        return

    result["assessment_type"] = rfc.get("rfc_assessment_type", "Physical RFC")
    result["medical_consultant"] = rfc.get("medical_consultant")
    result["exertional_limitations"] = rfc.get("exertional_limitations")
    result["postural_limitations"] = rfc.get("postural_limitations")
    result["manipulative_limitations"] = rfc.get("manipulative_limitations")
    result["visual_limitations"] = rfc.get("visual_limitations")
    result["communicative_limitations"] = rfc.get("communicative_limitations")
    result["environmental_limitations"] = rfc.get("environmental_limitations")

    # Derive exertional capacity from lifting limitations
    result["exertional_capacity"] = _derive_exertional_capacity(rfc)


def _derive_exertional_capacity(rfc: Dict[str, Any]) -> str:
    """Derive exertional capacity level from RFC limitations."""
    exertional = rfc.get("exertional_limitations", {})
    if not exertional:
        return "Unknown"

    occ_lift = exertional.get("lift_carry_occasional", {})
    if isinstance(occ_lift, dict):
        amount = occ_lift.get("amount", "")
    else:
        amount = str(occ_lift)

    amount_str = str(amount)
    if "50" in amount_str:
        return "Medium"
    if "20" in amount_str:
        return "Light"
    if "10" in amount_str:
        return "Sedentary"
    return "Unknown"


def _extract_mental_rfc(result: Dict[str, Any], fields: Dict[str, Any]) -> None:
    """Extract Mental RFC assessment from nested structure."""
    mental_rfc = fields.get("mental_rfc_assessment", {})
    if not mental_rfc:
        return

    result["paragraph_b_criteria"] = mental_rfc.get("paragraph_b_criteria")
    result["section_1_activities"] = mental_rfc.get("section_1_activities")


def _extract_impairments(result: Dict[str, Any], fields: Dict[str, Any]) -> None:
    """Extract and normalize impairments from various structures."""
    impairments_data = fields.get("medical_impairments", fields.get("impairments", []))
    diagnoses = _parse_impairments(impairments_data)

    if diagnoses:
        result["primary_diagnoses"] = diagnoses


def _parse_impairments(impairments_data: Any) -> List[Dict[str, str]]:
    """Parse impairments from list or dict structure."""
    diagnoses = []

    if isinstance(impairments_data, list):
        for imp in impairments_data:
            diagnoses.append({
                "description": imp.get("impairment", imp.get("description", "")),
                "code": imp.get("code", ""),
                "severity": imp.get("severity", imp.get("priority", "")),
            })
    elif isinstance(impairments_data, dict):
        for key in ["primary_diagnosis", "secondary_diagnosis"]:
            if imp := impairments_data.get(key):
                diagnoses.append({
                    "description": imp.get("description", imp.get("impairment", "")),
                    "code": imp.get("code", ""),
                    "severity": imp.get("severity", imp.get("priority", "")),
                })

    return diagnoses


def _extract_determination(result: Dict[str, Any], fields: Dict[str, Any]) -> None:
    """Extract determination decision from nested structure."""
    determination = fields.get("determination_decision", {})
    if not determination:
        return

    # Try multiple possible field names
    decision = (
        determination.get("decision")
        or determination.get("disability_status")
        or determination.get("level")
    )
    result["determination_decision"] = decision
    result["determination_basis"] = determination.get("basis")


def _extract_findings(result: Dict[str, Any], fields: Dict[str, Any]) -> None:
    """Extract findings of fact (clinical summary) from nested structure."""
    findings = fields.get("findings_of_fact", {})
    if not findings:
        return

    result["clinical_summary"] = findings.get("clinical_summary")
    result["adl_limitations"] = findings.get("adl_limitations")
