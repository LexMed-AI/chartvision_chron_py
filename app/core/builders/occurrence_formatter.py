"""
OccurrenceFormatter - Data-driven formatting for medical visit occurrences.

Replaces 15 hardcoded _format_* methods in chartvision_builder.py with
a single configurable formatter driven by YAML config.

Uses shared schema from formatter_config.yaml via schema_loader.
"""
import logging
from typing import Any, Dict, Optional

from app.core.builders.schema_loader import (
    load_formatter_config,
    format_field_value,
    render_occurrence,
)

logger = logging.getLogger(__name__)


class OccurrenceFormatter:
    """Format occurrence_treatment using YAML config."""

    def __init__(self, separator: str = "<br>"):
        """Initialize formatter with config.

        Args:
            separator: Line separator for output. Default "<br>" for HTML.
        """
        config = load_formatter_config()
        self._config = config.get("formatters", {})
        self._separator = separator

    def format(self, visit_type: str, occurrence: Optional[Dict[str, Any]]) -> str:
        """Format occurrence_treatment for display.

        Args:
            visit_type: Type of visit (e.g., "office_visit", "imaging_report")
            occurrence: Dict of occurrence data fields

        Returns:
            Formatted string with bold labels and separator between lines
        """
        if not occurrence:
            return ""

        formatter = self._config.get(visit_type)
        if not formatter:
            return self._format_generic(occurrence)

        # Handle special visit types with complex nested structures
        if formatter.get("special_handler"):
            if visit_type == "consultative_exam":
                return self._format_consultative_exam(occurrence, formatter)
            elif visit_type == "psych_visit":
                return self._format_psych_visit(occurrence, formatter)

        parts = []
        rendered_fields = set()
        for section in formatter.get("sections", []):
            field = section["field"]
            value = occurrence.get(field)

            # Use shared format_field_value for consistent handling
            formatted = format_field_value(value, section, occurrence)
            if not formatted:
                continue

            rendered_fields.add(field)
            # Also mark combine_with field as rendered
            if section.get("combine_with"):
                rendered_fields.add(section["combine_with"])

            parts.append(f"**{section['label']}:** {formatted}")

        # Append any remaining fields not in config
        parts.extend(self._format_remaining(occurrence, rendered_fields))

        return self._separator.join(parts) if parts else self._format_generic(occurrence)

    def _format_consultative_exam(self, occ: Dict, formatter: Dict) -> str:
        """Handle consultative_exam with CE type header and nested findings."""
        parts = []
        rendered_fields = set()

        # Header with CE type
        ce_type = occ.get("ce_type", "General")
        specialty = occ.get("examiner_specialty", "")
        header = f"**{ce_type} CE**"
        if specialty:
            header += f" ({specialty})"
        parts.append(header)
        rendered_fields.update(["ce_type", "examiner_specialty"])

        # History
        if occ.get("history_of_complaint"):
            history = occ["history_of_complaint"]
            if len(history) > 300:
                history = history[:300] + "..."
            parts.append(f"**History:** {history}")
            rendered_fields.add("history_of_complaint")

        # Physical Findings (nested dict)
        phys = occ.get("physical_findings", {})
        if phys and isinstance(phys, dict):
            p_parts = []
            if phys.get("gait_ambulation"):
                p_parts.append(f"Gait: {phys['gait_ambulation']}")
            if phys.get("range_of_motion"):
                p_parts.append(f"ROM: {phys['range_of_motion']}")
            if phys.get("strength_neuro"):
                p_parts.append(f"Neuro/Strength: {phys['strength_neuro']}")
            if phys.get("assistive_devices"):
                p_parts.append(f"Devices: {phys['assistive_devices']}")
            if phys.get("general_appearance"):
                p_parts.append(f"Appearance: {phys['general_appearance']}")
            if p_parts:
                parts.append(f"**Physical Exam:** {'; '.join(p_parts)}")
            rendered_fields.add("physical_findings")

        # Mental Findings (nested dict)
        mental = occ.get("mental_findings", {})
        if mental and isinstance(mental, dict):
            m_parts = []
            if mental.get("mood_affect"):
                m_parts.append(f"Mood/Affect: {mental['mood_affect']}")
            if mental.get("memory_concentration"):
                m_parts.append(f"Memory: {mental['memory_concentration']}")
            if mental.get("thought_process"):
                m_parts.append(f"Thought: {mental['thought_process']}")
            if mental.get("insight_judgment"):
                m_parts.append(f"Insight: {mental['insight_judgment']}")
            if mental.get("appearance_behavior"):
                m_parts.append(f"Appearance: {mental['appearance_behavior']}")
            if m_parts:
                parts.append(f"**MSE:** {'; '.join(m_parts)}")
            rendered_fields.add("mental_findings")

        # Diagnostic impression
        if occ.get("diagnostic_impression"):
            dx = occ["diagnostic_impression"]
            dx_str = "; ".join(dx) if isinstance(dx, list) else str(dx)
            parts.append(f"**Impression:** {dx_str}")
            rendered_fields.add("diagnostic_impression")

        # Functional Opinion
        if occ.get("functional_opinion"):
            opinion = occ["functional_opinion"]
            if len(opinion) > 400:
                opinion = opinion[:400] + "..."
            parts.append(f"**Functional Opinion:** {opinion}")
            rendered_fields.add("functional_opinion")

        # Prognosis
        if occ.get("prognosis"):
            parts.append(f"**Prognosis:** {occ['prognosis']}")
            rendered_fields.add("prognosis")

        # Append remaining fields
        parts.extend(self._format_remaining(occ, rendered_fields))

        return self._separator.join(parts) if parts else "—"

    def _format_psych_visit(self, occ: Dict, formatter: Dict) -> str:
        """Handle psych_visit with structured MSE nested dict."""
        parts = []
        rendered_fields = set()

        # Interval history
        if occ.get("interval_history"):
            history = occ["interval_history"]
            if len(history) > 300:
                history = history[:300] + "..."
            parts.append(f"**History:** {history}")
            rendered_fields.add("interval_history")

        # Mental Status Exam (handle dict or string)
        mse = occ.get("mental_status_exam")
        if mse:
            if isinstance(mse, dict):
                mse_parts = []
                if mse.get("mood_affect"):
                    mse_parts.append(f"Mood/Affect: {mse['mood_affect']}")
                if mse.get("appearance_behavior"):
                    mse_parts.append(f"Appearance: {mse['appearance_behavior']}")
                if mse.get("speech_thought"):
                    mse_parts.append(f"Speech/Thought: {mse['speech_thought']}")
                if mse.get("perception_cognition"):
                    mse_parts.append(f"Cognition: {mse['perception_cognition']}")
                if mse.get("insight_judgment"):
                    mse_parts.append(f"Insight: {mse['insight_judgment']}")
                if mse_parts:
                    parts.append(f"**MSE:** {'; '.join(mse_parts)}")
            else:
                # Fallback if LLM returns string
                parts.append(f"**MSE:** {mse}")
            rendered_fields.add("mental_status_exam")

        # Risk assessment
        if occ.get("risk_assessment"):
            parts.append(f"**Risk:** {occ['risk_assessment']}")
            rendered_fields.add("risk_assessment")

        # Treatment response
        if occ.get("treatment_response"):
            response = occ["treatment_response"]
            if len(response) > 200:
                response = response[:200] + "..."
            parts.append(f"**Response:** {response}")
            rendered_fields.add("treatment_response")

        # Plan
        if occ.get("plan"):
            plan = occ["plan"]
            if len(plan) > 150:
                plan = plan[:150] + "..."
            parts.append(f"**Plan:** {plan}")
            rendered_fields.add("plan")

        # Append remaining fields
        parts.extend(self._format_remaining(occ, rendered_fields))

        return self._separator.join(parts) if parts else "—"

    def _format_remaining(self, occ: Dict, rendered_fields: set) -> list:
        """Format any fields not explicitly handled."""
        parts = []
        skip_keys = {"visit_type", "applies_to"} | rendered_fields

        for key, value in occ.items():
            if key in skip_keys or not value:
                continue
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                value = "; ".join(str(v) for v in value[:5])
            if isinstance(value, dict):
                # Flatten nested dict
                value = "; ".join(f"{k}: {v}" for k, v in value.items() if v)
            if isinstance(value, str) and len(value) > 200:
                value = value[:200] + "..."
            parts.append(f"**{label}:** {value}")
        return parts

    def _format_generic(self, occurrence: Dict) -> str:
        """Fallback for unknown visit types.

        Args:
            occurrence: Dict of occurrence data

        Returns:
            Formatted string with all non-internal fields
        """
        if not occurrence:
            return ""

        parts = []
        for key, value in occurrence.items():
            # Skip internal fields
            if key in ("visit_type", "applies_to") or not value:
                continue
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value if v)
            if isinstance(value, dict):
                # Flatten nested dict
                value = "; ".join(f"{k}: {v}" for k, v in value.items() if v)
            # Truncate long values
            if isinstance(value, str) and len(value) > 300:
                value = value[:300] + "..."
            parts.append(f"**{label}:** {value}")
        return self._separator.join(parts)
