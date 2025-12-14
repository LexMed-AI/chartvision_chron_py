"""
Shared schema loader for occurrence formatting.

Loads schemas from config/templates/ (single source of truth) and provides
utilities for both markdown (occurrence_formatter.py) and HTML (html_renderer.py).

Note: Previously loaded from formatter_config.yaml which is now deprecated.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Cached config (built from templates)
_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _get_template_loader():
    """Lazy import to avoid circular dependencies."""
    from app.core.extraction.template_loader import get_template_loader
    return get_template_loader()


def load_formatter_config() -> Dict[str, Any]:
    """Load formatter configuration from templates.

    Builds formatter config from config/templates/*.yaml files,
    converting from template format to formatter format.

    Returns:
        Dict with 'formatters' key containing visit type schemas
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    loader = _get_template_loader()
    formatters = {}

    for visit_type in loader.list_visit_types():
        template = loader.get_template(visit_type)
        fields = template.get("fields", {})
        output_labels = template.get("output_labels", [])

        # Check for special handlers (consultative_exam, psych_visit)
        if visit_type in ("consultative_exam", "psych_visit", "mental_health"):
            formatters[visit_type] = {"special_handler": True}
            continue

        # Build sections list from fields, ordered by output_labels
        sections = []
        field_order = _get_field_order(fields, output_labels)

        for field_name in field_order:
            field_config = fields.get(field_name, {})
            section = {
                "field": field_name,
                "label": field_config.get("label", field_name.replace("_", " ").title()),
            }
            # Copy optional formatting attributes
            if field_config.get("type") == "array":
                section["type"] = "list"
            if field_config.get("max_len"):
                section["max_len"] = field_config["max_len"]
            if field_config.get("combine_with"):
                section["combine_with"] = field_config["combine_with"]

            sections.append(section)

        formatters[visit_type] = {"sections": sections}

    _CONFIG_CACHE = {"formatters": formatters}
    return _CONFIG_CACHE


def _get_field_order(fields: Dict, output_labels: List[str]) -> List[str]:
    """Determine field order based on output_labels and field definitions.

    Args:
        fields: Dict of field definitions
        output_labels: Ordered list of output labels (e.g., ["CC", "HPI", "Dx"])

    Returns:
        Ordered list of field names
    """
    if not output_labels:
        return list(fields.keys())

    # Map labels to field names
    label_to_field = {}
    for field_name, config in fields.items():
        label = config.get("label", "")
        if label:
            label_to_field[label] = field_name

    # Build ordered list
    ordered = []
    for label in output_labels:
        if label in label_to_field:
            ordered.append(label_to_field[label])

    # Add any fields not in output_labels
    for field_name in fields:
        if field_name not in ordered:
            ordered.append(field_name)

    return ordered


def get_visit_type_schema(visit_type: str) -> Optional[Dict[str, Any]]:
    """Get schema for a specific visit type.

    Args:
        visit_type: Visit type key (e.g., "office_visit", "imaging_report")

    Returns:
        Schema dict with 'sections' list, or None if not found
    """
    config = load_formatter_config()
    return config.get("formatters", {}).get(visit_type)


def format_field_value(
    value: Any,
    field_config: Dict[str, Any],
    occurrence: Dict[str, Any],
) -> Optional[str]:
    """Format a single field value according to config.

    Args:
        value: Raw field value
        field_config: Field configuration from schema
        occurrence: Full occurrence dict (for combine_with)

    Returns:
        Formatted string value, or None if empty
    """
    if not value:
        return None

    # Handle list type
    if field_config.get("type") == "list" and isinstance(value, list):
        value = "; ".join(str(v) for v in value if v)
    elif isinstance(value, list):
        value = "; ".join(str(v) for v in value if v)
    elif isinstance(value, dict):
        # Flatten nested dict
        value = "; ".join(f"{k}: {v}" for k, v in value.items() if v)
    else:
        value = str(value)

    if not value:
        return None

    # Handle combine_with
    combine_field = field_config.get("combine_with")
    if combine_field:
        combine_value = occurrence.get(combine_field)
        if combine_value:
            value = f"{value} {combine_value}"

    # Handle max_len truncation
    max_len = field_config.get("max_len")
    if max_len and len(value) > max_len:
        value = value[:max_len] + "..."

    return value


def render_occurrence(
    visit_type: str,
    occurrence: Dict[str, Any],
    output_format: str = "markdown",
    separator: str = "<br>",
) -> str:
    """Render occurrence using shared schema.

    Args:
        visit_type: Visit type key
        occurrence: Occurrence treatment dict
        output_format: "markdown" or "html"
        separator: Line separator (default "<br>")

    Returns:
        Formatted string
    """
    if not occurrence:
        return "N/A" if output_format == "html" else ""

    schema = get_visit_type_schema(visit_type)
    if not schema or schema.get("special_handler"):
        # Fall back to generic rendering
        return _render_generic(occurrence, output_format, separator)

    parts = []
    rendered_fields = set()

    for section in schema.get("sections", []):
        field = section["field"]
        value = occurrence.get(field)

        formatted = format_field_value(value, section, occurrence)
        if not formatted:
            continue

        rendered_fields.add(field)
        # Also mark combine_with field as rendered
        if section.get("combine_with"):
            rendered_fields.add(section["combine_with"])

        label = section["label"]
        if output_format == "html":
            parts.append(f"<strong>{label}:</strong> {_escape_html(formatted)}")
        else:
            parts.append(f"**{label}:** {formatted}")

    # Render any remaining fields not in schema
    remaining = _render_remaining(occurrence, rendered_fields, output_format)
    parts.extend(remaining)

    if not parts:
        return "N/A" if output_format == "html" else ""

    return separator.join(parts)


def _render_generic(
    occurrence: Dict[str, Any],
    output_format: str,
    separator: str,
) -> str:
    """Generic rendering for unknown visit types."""
    parts = []
    skip_keys = {"visit_type", "applies_to"}

    for key, value in occurrence.items():
        if key in skip_keys or not value:
            continue

        label = key.replace("_", " ").title()

        if isinstance(value, list):
            value = "; ".join(str(v) for v in value[:5] if v)
        elif isinstance(value, dict):
            value = "; ".join(f"{k}: {v}" for k, v in value.items() if v)

        value = str(value)
        if len(value) > 300:
            value = value[:300] + "..."

        if output_format == "html":
            parts.append(f"<strong>{label}:</strong> {_escape_html(value)}")
        else:
            parts.append(f"**{label}:** {value}")

    return separator.join(parts) if parts else ("N/A" if output_format == "html" else "")


def _render_remaining(
    occurrence: Dict[str, Any],
    rendered_fields: set,
    output_format: str,
) -> List[str]:
    """Render fields not covered by schema."""
    parts = []
    skip_keys = {"visit_type", "applies_to"} | rendered_fields

    for key, value in occurrence.items():
        if key in skip_keys or not value:
            continue

        label = key.replace("_", " ").title()

        if isinstance(value, list):
            value = "; ".join(str(v) for v in value[:5] if v)
        elif isinstance(value, dict):
            value = "; ".join(f"{k}: {v}" for k, v in value.items() if v)

        value = str(value)
        if len(value) > 200:
            value = value[:200] + "..."

        if output_format == "html":
            parts.append(f"<strong>{label}:</strong> {_escape_html(value)}")
        else:
            parts.append(f"**{label}:** {value}")

    return parts


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    import html
    return html.escape(text).replace("|", "/")


def clear_config_cache() -> None:
    """Clear the config cache (for testing)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
