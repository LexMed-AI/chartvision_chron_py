"""
Content analysis for chronology entries.

Domain logic for detecting sparse/incomplete medical record extractions.
This identifies entries where the LLM extracted headers (date, provider, visit_type)
but the actual medical content is missing - typically because it was in a scanned image.

Field names are loaded dynamically from YAML templates (single source of truth).
"""
from typing import Dict, List, Optional

# Cached content fields - loaded once from templates
_CONTENT_FIELDS_CACHE: Optional[Dict[str, List[str]]] = None

# Common fallback fields when LLM uses office_visit schema for other types
_FALLBACK_FIELDS = [
    "chief_complaint", "findings", "assessment",
    "assessment_diagnoses", "plan_of_care"
]


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

    # Get fields to check from templates (with fallback)
    content_fields = _get_content_fields()
    fields_to_check = content_fields.get(visit_type, _FALLBACK_FIELDS)

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


def _get_content_fields() -> Dict[str, List[str]]:
    """Load content field names from YAML templates.

    Dynamically reads field definitions from config/templates/*.yaml
    to ensure single source of truth. Results are cached for performance.

    Returns:
        Dict mapping visit_type to list of field names
    """
    global _CONTENT_FIELDS_CACHE

    if _CONTENT_FIELDS_CACHE is not None:
        return _CONTENT_FIELDS_CACHE

    # Lazy import to avoid circular dependencies
    from app.core.extraction.template_loader import get_template_loader

    loader = get_template_loader()
    fields = {}

    for visit_type in loader.list_visit_types():
        template_fields = loader.get_fields(visit_type)
        if template_fields:
            # Include all template fields plus common fallbacks
            field_names = list(template_fields.keys()) + _FALLBACK_FIELDS
            fields[visit_type] = list(set(field_names))  # Deduplicate

    _CONTENT_FIELDS_CACHE = fields
    return fields


def clear_content_fields_cache() -> None:
    """Clear the cached content fields (for testing)."""
    global _CONTENT_FIELDS_CACHE
    _CONTENT_FIELDS_CACHE = None
