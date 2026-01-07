"""
HTML Report Generator - Server-side HTML generation matching ChartVision UI.

Generates HTML that matches the UI's legal document styling for PDF export.
This ensures the downloaded PDF looks identical to the browser display.

Uses shared occurrence schema from core/builders/schema_loader.py.
"""
import html as html_lib
import logging
from typing import Any, Dict, List, Optional

from app.core.builders.schema_loader import render_occurrence
from app.adapters.export import styles

logger = logging.getLogger(__name__)


def escape(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return html_lib.escape(str(text))


def format_source_citation(entry: Dict[str, Any]) -> str:
    """Format source citation from entry, using citation object if available.

    Matches the format used by ChronologyEntry.formatted_source for consistency
    between markdown and PDF outputs.

    Args:
        entry: Chronology entry dict with optional 'citation' key

    Returns:
        Formatted source citation string (e.g., "10F@3 (p.245)")
    """
    citation = entry.get("citation")

    if citation:
        # Handle Citation dataclass (has format() method)
        if hasattr(citation, "format"):
            return citation.format()

        # Handle dict (backwards compatibility or serialized data)
        exhibit_id = citation.get("exhibit_id", entry.get("exhibit_reference", ""))
        abs_page = citation.get("absolute_page")
        rel_page = citation.get("relative_page")
        end_rel_page = citation.get("end_relative_page")
        end_abs_page = citation.get("end_absolute_page")

        if exhibit_id and rel_page:
            if end_rel_page and end_rel_page != rel_page:
                # Multi-page range
                return f"{exhibit_id}@{rel_page}-{end_rel_page} (pp.{abs_page}-{end_abs_page})"
            elif abs_page:
                return f"{exhibit_id}@{rel_page} (p.{abs_page})"
            else:
                return f"{exhibit_id}@{rel_page}"
        elif exhibit_id and abs_page:
            return f"{exhibit_id} (p.{abs_page})"
        elif abs_page:
            return f"p.{abs_page}"

    # Fallback to exhibit_reference
    if entry.get("exhibit_reference"):
        source = f"Ex. {entry['exhibit_reference']}"
        if entry.get("page_range"):
            source += f" pp.{entry['page_range']}"
        return source

    return "N/A"


def build_occurrence_summary(occ: Dict[str, Any], visit_type: Optional[str]) -> str:
    """
    Build occurrence/treatment summary for table cell based on visit type.

    Uses shared schema from formatter_config.yaml for consistent formatting
    across markdown and HTML outputs.
    """
    if not occ or len(occ) == 0:
        return "N/A"

    # Use shared schema-driven rendering
    return render_occurrence(
        visit_type=visit_type or "office_visit",
        occurrence=occ,
        output_format="html",
        separator="<br>",
    )


def render_dde_section(dde: Dict[str, Any]) -> str:
    """Render DDE extraction section as HTML."""
    lines = []
    lines.append('<div class="dde-section">')
    lines.append('<h2>CLAIMANT INFORMATION</h2>')

    # Required DDE fields
    lines.append(f'<p><strong>Claimant:</strong> {escape(dde.get("claimant_name", "N/A"))}</p>')
    lines.append(f'<p><strong>Date of Birth:</strong> {escape(dde.get("date_of_birth", "N/A"))}</p>')
    lines.append(f'<p><strong>Claim Type:</strong> {escape(dde.get("claim_type", "N/A"))}</p>')
    lines.append(f'<p><strong>Protective Filing Date (PFD):</strong> {escape(dde.get("protective_filing_date", "N/A"))}</p>')
    lines.append(f'<p><strong>Alleged Onset Date:</strong> {escape(dde.get("alleged_onset_date", "N/A"))}</p>')

    age_cat = dde.get("age_category") or dde.get("vocationalFactors", {}).get("age", {}).get("category", "N/A")
    lines.append(f'<p><strong>Age Category:</strong> {escape(age_cat)}</p>')

    if dde.get("date_last_insured"):
        lines.append(f'<p><strong>Date Last Insured (DLI):</strong> {escape(dde["date_last_insured"])}</p>')

    lines.append('<hr>')

    # Determination
    if dde.get("determination_decision"):
        det = dde["determination_decision"].upper()
        if dde.get("determination_level"):
            det += f" ({escape(dde['determination_level'])})"
        lines.append(f'<p><strong>Determination:</strong> {det}</p>')

    # Exertional Capacity
    if dde.get("exertional_capacity"):
        lines.append(f'<p><strong>RFC Exertional Level:</strong> {escape(dde["exertional_capacity"])}</p>')

    # Medical Consultant
    if dde.get("medical_consultant"):
        lines.append(f'<p><strong>Medical Consultant:</strong> {escape(dde["medical_consultant"])}</p>')

    # RFC Limitations - Exertional
    if dde.get("exertional_limitations"):
        ex = dde["exertional_limitations"]
        lines.append('<p><strong>Exertional Limitations:</strong></p>')
        lines.append('<ul>')
        if ex.get("lift_carry_occasional"):
            val = ex["lift_carry_occasional"]
            if isinstance(val, dict):
                val = val.get("amount", val)
            lines.append(f'<li>Occasional Lift/Carry: {escape(str(val))}</li>')
        if ex.get("lift_carry_frequent"):
            val = ex["lift_carry_frequent"]
            if isinstance(val, dict):
                val = val.get("amount", val)
            lines.append(f'<li>Frequent Lift/Carry: {escape(str(val))}</li>')
        if ex.get("stand_walk_hours"):
            lines.append(f'<li>Stand/Walk: {escape(ex["stand_walk_hours"])}</li>')
        if ex.get("sit_hours"):
            lines.append(f'<li>Sit: {escape(ex["sit_hours"])}</li>')
        if ex.get("push_pull"):
            lines.append(f'<li>Push/Pull: {escape(ex["push_pull"])}</li>')
        lines.append('</ul>')

    # Postural Limitations
    if dde.get("postural_limitations"):
        postural = dde["postural_limitations"]
        has_limits = any(v and v != "Unlimited" for v in postural.values())
        if has_limits:
            lines.append('<p><strong>Postural Limitations:</strong></p>')
            lines.append('<ul>')
            for key, label in [
                ("climbing_ramps_stairs", "Climbing Ramps/Stairs"),
                ("climbing_ladders_ropes_scaffolds", "Climbing Ladders/Ropes/Scaffolds"),
                ("balancing", "Balancing"),
                ("stooping", "Stooping"),
                ("kneeling", "Kneeling"),
                ("crouching", "Crouching"),
                ("crawling", "Crawling"),
            ]:
                if postural.get(key):
                    lines.append(f'<li>{label}: {escape(postural[key])}</li>')
            lines.append('</ul>')

    # Manipulative Limitations
    if dde.get("manipulative_limitations"):
        manip = dde["manipulative_limitations"]
        has_limits = any(v and v != "Unlimited" for v in manip.values())
        if has_limits:
            lines.append('<p><strong>Manipulative Limitations:</strong></p>')
            lines.append('<ul>')
            for key, label in [
                ("reaching_all_directions", "Reaching (All Directions)"),
                ("reaching_overhead_left", "Reaching Overhead (Left)"),
                ("reaching_overhead_right", "Reaching Overhead (Right)"),
                ("handling", "Handling"),
                ("fingering", "Fingering"),
                ("feeling", "Feeling"),
                ("reaching_any_direction", "Reaching"),
            ]:
                if manip.get(key):
                    lines.append(f'<li>{label}: {escape(manip[key])}</li>')
            lines.append('</ul>')

    # Primary Diagnoses
    if dde.get("primary_diagnoses") and len(dde["primary_diagnoses"]) > 0:
        lines.append('<p><strong>Primary Diagnoses (MDIs):</strong></p>')
        lines.append('<ul>')
        for dx in dde["primary_diagnoses"]:
            desc = dx.get("description", "Unknown")
            code = f" ({dx['code']})" if dx.get("code") else ""
            severity = f" - {dx['severity']}" if dx.get("severity") else ""
            lines.append(f'<li>{escape(desc)}{escape(code)}{escape(severity)}</li>')
        lines.append('</ul>')

    # Clinical Summary
    if dde.get("clinical_summary"):
        lines.append(f'<p><strong>Clinical Summary:</strong><br>{escape(dde["clinical_summary"])}</p>')

    lines.append('</div>')
    return "\n".join(lines)


def render_chronology_table(entries: List[Dict[str, Any]]) -> str:
    """Render medical chronology entries as HTML table."""
    lines = []
    lines.append('<h2>MEDICAL EVENT TIMELINE</h2>')
    lines.append(f'<p><strong>Total Entries:</strong> {len(entries)}</p>')

    lines.append('<table class="chronology-table">')
    lines.append('<thead><tr>')
    lines.append('<th>Date</th>')
    lines.append('<th>Provider</th>')
    lines.append('<th>Facility</th>')
    lines.append('<th>Type</th>')
    lines.append('<th>Occurrence/Treatment</th>')
    lines.append('<th>Source</th>')
    lines.append('</tr></thead>')
    lines.append('<tbody>')

    for entry in entries:
        date = escape(entry.get("date", "N/A"))
        provider = escape(entry.get("provider", "Unknown"))
        facility = escape(entry.get("facility", "N/A"))
        visit_type = (entry.get("visit_type") or "N/A").replace("_", " ")

        source = format_source_citation(entry)

        occ = entry.get("occurrence_treatment", {})
        occ_summary = build_occurrence_summary(occ, entry.get("visit_type"))

        lines.append('<tr>')
        lines.append(f'<td>{date}</td>')
        lines.append(f'<td>{provider}</td>')
        lines.append(f'<td>{facility}</td>')
        lines.append(f'<td>{visit_type}</td>')
        lines.append(f'<td>{occ_summary}</td>')
        lines.append(f'<td>{escape(source)}</td>')
        lines.append('</tr>')

    lines.append('</tbody>')
    lines.append('</table>')

    return "\n".join(lines)


def get_pdf_css() -> str:
    """Get CSS styling for PDF reports matching ChartVision UI.

    Delegates to styles.py for centralized CSS management.
    """
    return styles.get_chartvision_css() + styles.get_chronology_table_css()


def render_chronology_html(
    results: Dict[str, Any],
    title: str = "ChartVision Medical Chronology"
) -> str:
    """
    Render complete chronology report as HTML matching ChartVision UI.

    Args:
        results: Job results containing dde_extraction and entries
        title: Document title

    Returns:
        Complete HTML document ready for Gotenberg PDF conversion
    """
    body_parts = []
    body_parts.append(f'<h1>{escape(title)}</h1>')

    # DDE Section (if extracted)
    if results.get("dde_extracted") and results.get("dde_extraction"):
        body_parts.append(render_dde_section(results["dde_extraction"]))

    # Medical Chronology Table
    entries = results.get("entries", [])
    if entries:
        body_parts.append(render_chronology_table(entries))
    else:
        # Fallback summary
        body_parts.append('<h2>RESULTS</h2>')
        body_parts.append(f'<p><strong>Segments Processed:</strong> {results.get("segments", 0)}</p>')
        body_parts.append(f'<p><strong>Chronology Entries:</strong> {results.get("chronology_entries", 0)}</p>')

        sections_found = results.get("sections_found", [])
        if sections_found and "F" not in sections_found and "A" not in sections_found:
            body_parts.append(
                '<p><em>Note: This document does not contain Section A (DDE) or '
                'Section F (Medical Records). ChartVision extracts chronologies '
                'from these sections.</em></p>'
            )

    body_html = "\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{escape(title)}</title>
    <style>
{get_pdf_css()}
    </style>
</head>
<body>
{body_html}
</body>
</html>"""
