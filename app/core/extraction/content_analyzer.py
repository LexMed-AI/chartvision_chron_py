"""
Content analysis for chronology entries.

Domain logic for detecting sparse/incomplete medical record extractions.
This identifies entries where the LLM extracted headers (date, provider, visit_type)
but the actual medical content is missing - typically because it was in a scanned image.
"""


def is_content_sparse(entry: dict) -> bool:
    """
    Check if a chronology entry has visit_type but empty/sparse details.

    This identifies the "Content Density Trap" where LLM extracts headers
    (date, provider, visit_type) but the actual medical content is missing
    because it was in a scanned image layer.

    Args:
        entry: Chronology entry dict with visit_type and occurrence_treatment

    Returns:
        True if entry has visit_type but empty/meaningless occurrence details
    """
    if not entry:
        return True

    visit_type = entry.get("visit_type")
    if not visit_type:
        return True  # No visit type = definitely sparse

    occ = entry.get("occurrence_treatment", {})
    if not occ:
        return True

    if not isinstance(occ, dict):
        # String occurrence - check if meaningful
        return len(str(occ).strip()) < 20

    # Check if all detail fields are empty/None
    # These are the key content fields per visit type (aligned with YAML template field names)
    # NOTE: LLM sometimes returns office_visit fields for other visit types, so we also check those
    content_fields = _get_content_fields()

    # Get relevant fields for this visit type - with fallback to common content fields
    fields_to_check = content_fields.get(
        visit_type,
        ["chief_complaint", "findings", "assessment", "assessment_diagnoses", "plan_of_care"]
    )

    for field in fields_to_check:
        value = occ.get(field)
        if value:
            if isinstance(value, str) and len(value.strip()) > 10:
                return False  # Has meaningful content
            if isinstance(value, list) and len(value) > 0:
                return False  # Has list content
            if isinstance(value, dict) and any(v for v in value.values() if v):
                return False  # Has nested content

    return True  # All content fields are empty


def _get_content_fields() -> dict:
    """Get content field mappings per visit type."""
    return {
        "office_visit": [
            "chief_complaint", "history_present_illness",
            "assessment_diagnoses", "plan_of_care"
        ],
        # imaging_report: check both proper schema AND office_visit fields that LLM may return
        "imaging_report": [
            "findings", "impression", "indication", "imaging_type",
            "body_part", "assessment_diagnoses", "plan_of_care"
        ],
        "lab_result": [
            "results_summary", "panel_name", "result_value",
            "test_name", "results", "interpretation"
        ],
        # therapy_eval: check both proper schema AND office_visit fields
        "therapy_eval": [
            "subjective_complaints", "objective_measurements", "assessment",
            "plan", "therapy_type", "assessment_diagnoses", "plan_of_care"
        ],
        "surgical_report": [
            "procedure_name", "operative_findings",
            "preoperative_diagnosis", "postoperative_diagnosis", "findings"
        ],
        "consultative_exam": [
            "history_of_complaint", "physical_findings", "functional_opinion"
        ],
        "psych_visit": [
            "interval_history", "mental_status_exam", "treatment_plan"
        ],
        "diagnostic_study": [
            "technical_findings", "interpretation", "findings"
        ],
        "procedural_visit": [
            "procedure_details", "outcome", "procedure_name"
        ],
        "emergency_visit": [
            "chief_complaint", "clinical_course", "disposition"
        ],
        "inpatient_admission": [
            "reason_for_admission", "hospital_course", "discharge_summary"
        ],
        "medical_source_statement": [
            "functional_limitations", "opinion_basis", "diagnoses_assessed"
        ],
    }
