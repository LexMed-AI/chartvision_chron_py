"""
TemplateLoader - Single source of truth for visit-type schemas.

Loads templates from config/templates/ which contain:
- Field definitions (type, required, label, description)
- LLM prompts (user_prompt, system_prompt)
- Few-shot examples
- Output labels for formatting

Replaces scattered schema definitions in:
- prompts/_base/occurrence_schemas.yaml
- prompts/extraction/text_extraction.yaml
- prompts/extraction/vision_extraction.yaml
- core/builders/formatter_config.yaml
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class TemplateLoader:
    """Load visit-type templates from config/templates/."""

    _instance: Optional["TemplateLoader"] = None

    def __init__(self, templates_dir: Optional[Path] = None):
        """Initialize loader.

        Args:
            templates_dir: Path to templates directory.
                          Defaults to app/config/templates/
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parents[2] / "config" / "templates"
        self._templates_dir = templates_dir
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._base: Optional[Dict[str, Any]] = None

    @classmethod
    def get_instance(cls) -> "TemplateLoader":
        """Get singleton instance for shared access."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """Load a YAML file from templates directory."""
        path = self._templates_dir / filename
        if not path.exists():
            logger.warning(f"Template not found: {path}")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_base(self) -> Dict[str, Any]:
        """Load base.yaml with shared config."""
        if self._base is None:
            self._base = self._load_yaml("base.yaml")
        return self._base

    def get_system_prompt(self) -> str:
        """Get shared system prompt from base.yaml."""
        return self.get_base().get("system_prompt", "")

    def get_core_fields(self) -> Dict[str, Any]:
        """Get core fields (date, provider, facility, etc.) from base.yaml."""
        return self.get_base().get("core_fields", {})

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration from base.yaml."""
        return self.get_base().get("llm_config", {})

    def get_template(self, visit_type: str) -> Dict[str, Any]:
        """Load template for a visit type.

        Args:
            visit_type: Visit type name (e.g., 'office_visit', 'imaging_report')

        Returns:
            Template dict with fields, user_prompt, examples, output_labels
        """
        if visit_type not in self._cache:
            self._cache[visit_type] = self._load_yaml(f"{visit_type}.yaml")
        return self._cache[visit_type]

    def get_user_prompt(self, visit_type: str) -> str:
        """Get LLM user prompt for a visit type."""
        return self.get_template(visit_type).get("user_prompt", "")

    def get_fields(self, visit_type: str) -> Dict[str, Any]:
        """Get field definitions for extraction.

        Returns dict like:
            {
                'chief_complaint': {
                    'type': 'text',
                    'required': True,
                    'label': 'CC',
                    'description': "Patient's primary reason for visit"
                },
                ...
            }
        """
        return self.get_template(visit_type).get("fields", {})

    def get_output_labels(self, visit_type: str) -> List[str]:
        """Get output labels for formatting (e.g., ['CC', 'HPI', 'Exam', 'Dx', 'Plan'])."""
        return self.get_template(visit_type).get("output_labels", [])

    def get_examples(self, visit_type: str) -> List[Dict[str, Any]]:
        """Get few-shot examples for LLM prompting."""
        return self.get_template(visit_type).get("examples", [])

    def get_output_example(self, visit_type: str) -> str:
        """Get formatted output example string."""
        return self.get_template(visit_type).get("output_example", "")

    def list_visit_types(self) -> List[str]:
        """List all available visit type templates."""
        visit_types = []
        for path in self._templates_dir.glob("*.yaml"):
            name = path.stem
            # Skip non-visit-type files
            if name in ("base", "exhibit_type_mapping", "dde_assessment"):
                continue
            visit_types.append(name)
        return sorted(visit_types)

    def get_field_label(self, visit_type: str, field_name: str) -> str:
        """Get display label for a specific field."""
        fields = self.get_fields(visit_type)
        field = fields.get(field_name, {})
        return field.get("label", field_name)

    def get_field_for_output(self, visit_type: str, field_name: str) -> Dict[str, Any]:
        """Get field config with output formatting info.

        Returns dict with:
            - label: display label
            - type: field type (text, array, etc.)
            - max_len: truncation length (if specified)
            - combine_with: field to append (if specified)
        """
        fields = self.get_fields(visit_type)
        field = fields.get(field_name, {})
        return {
            "label": field.get("label", field_name),
            "type": field.get("type", "text"),
            "max_len": field.get("max_len"),
            "combine_with": field.get("combine_with"),
        }

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()
        self._base = None

    def detect_visit_types(self, text: str) -> List[str]:
        """Detect likely visit types from text content using keyword heuristics.

        Args:
            text: Medical record text to analyze

        Returns:
            List of likely visit types (always includes 'office_visit' as fallback)
        """
        text_lower = text.lower()
        detected = set()

        # Keyword patterns for each visit type
        patterns = {
            "imaging_report": [
                "radiology", "radiologist", "x-ray", "ct scan", "mri",
                "ultrasound", "impression:", "findings:", "technique:"
            ],
            "lab_result": [
                "laboratory", "lab result", "cbc", "cmp", "bmp", "lipid panel",
                "reference range", "abnormal", "urinalysis", "hgb", "wbc"
            ],
            "surgical_report": [
                "operative report", "operative note", "pre-op", "post-op",
                "preoperative diagnosis", "postoperative diagnosis", "surgeon:",
                "anesthesia", "procedure performed"
            ],
            "emergency_visit": [
                "emergency department", "emergency room", "ed visit", "er visit",
                "triage", "chief complaint", "disposition:", "esi level"
            ],
            "therapy_eval": [
                "physical therapy", "occupational therapy", "speech therapy",
                "pt eval", "ot eval", "rom:", "range of motion", "strength:"
            ],
            "consultative_exam": [
                "consultative examination", "ce report", "disability determination",
                "dds", "functional capacity", "referred by ssa"
            ],
            "psych_visit": [
                "psychiatr", "psycholog", "mental status exam", "mse:",
                "mood:", "affect:", "thought process", "lcsw", "lpc"
            ],
            "inpatient_admission": [
                "admission date", "discharge date", "hospital course",
                "discharge summary", "admitted to", "length of stay"
            ],
            "diagnostic_study": [
                "emg", "nerve conduction", "ekg", "ecg", "eeg",
                "sleep study", "pulmonary function", "stress test"
            ],
            "medical_source_statement": [
                "medical source statement", "rfc", "functional capacity",
                "work limitations", "sedentary", "light work", "medium work"
            ],
        }

        for visit_type, keywords in patterns.items():
            if any(kw in text_lower for kw in keywords):
                detected.add(visit_type)

        # Always include office_visit as fallback (most common type)
        detected.add("office_visit")

        return list(detected)

    def get_schema_for_types(self, visit_types: List[str]) -> str:
        """Build schema documentation from YAML templates for specific visit types.

        Args:
            visit_types: List of visit types to include

        Returns:
            Formatted schema string for LLM prompt
        """
        lines = ["VISIT TYPE SCHEMAS - USE THESE EXACT FIELD NAMES", "=" * 50]

        for vt in visit_types:
            template = self.get_template(vt)
            if not template:
                continue

            description = template.get("description", vt.replace("_", " "))
            fields = template.get("fields", {})

            # Build schema from template fields
            field_lines = []
            for field_name, config in fields.items():
                required = "(required)" if config.get("required") else ""
                desc = config.get("description", "")
                field_type = config.get("type", "text")

                # Compact description
                if field_type == "array":
                    field_lines.append(f"  - {field_name}: array - {desc} {required}".strip())
                else:
                    field_lines.append(f"  - {field_name}: {desc} {required}".strip())

            if field_lines:
                lines.append(f"**{vt}** ({description}):")
                lines.extend(field_lines)
                lines.append("")

        lines.append("Extract ALL relevant fields. Empty/N/A fine if not documented.")
        return "\n".join(lines)

    def build_user_prompt(self, text: str, exhibit_id: str) -> str:
        """Build optimized user prompt with conditional schema loading.

        Args:
            text: Medical record text
            exhibit_id: Exhibit identifier

        Returns:
            Complete user prompt with only relevant schemas
        """
        # Detect likely visit types
        detected = self.detect_visit_types(text)

        # Build schema section
        schema_section = self.get_schema_for_types(detected)

        # Build prompt
        return f"""Parse the following F-Section medical records and extract all encounters.

**MEDICAL RECORDS:**
{text}

**EXHIBIT ID:** {exhibit_id}

**EXTRACTION REQUIREMENTS:**
1. Identify each medical encounter's visit_type
2. Extract the specific fields listed below for that visit type
3. Include exhibit reference with page from nearest [Page X] marker
4. Sort by date (newest first)

**OUTPUT FORMAT:**
Return a JSON array. Each entry must have:
- date: "MM/DD/YYYY" format
- exhibit_reference: "{exhibit_id}@page"
- visit_type: one of the types below
- provider: name with credentials
- facility: facility name
- occurrence_treatment: object with fields for that visit type

{schema_section}"""


# Convenience function for simple access
def get_template_loader() -> TemplateLoader:
    """Get the singleton TemplateLoader instance."""
    return TemplateLoader.get_instance()
