# Schema Consolidation Design

**Date:** 2025-01-13
**Status:** Approved
**Problem:** Visit type schemas duplicated across 6 files, unclear source of truth

## Summary

Consolidate all visit-type schemas to use `config/templates/` as the single source of truth. Delete 1,010 lines of redundant schema definitions and move 3,118 lines of unused reference docs.

## Current State (Problem)

Visit type field definitions duplicated in:
1. `prompts/_base/occurrence_schemas.yaml` (382 lines)
2. `prompts/extraction/text_extraction.yaml` (242 lines)
3. `prompts/extraction/vision_extraction.yaml` (220 lines)
4. `core/builders/formatter_config.yaml` (166 lines)
5. `prompts/schemas/f_medical_parsing_template.yaml` (909 lines - unused)
6. `config/templates/*.yaml` (5,840 lines - **unused but complete**)

**Pain points:**
- Changes require updating multiple files
- Unclear which schema is authoritative
- 5,840 lines of well-structured templates sitting unused

## Solution

Use existing `config/templates/` as the single source of truth. These templates already contain:
- Field definitions with type, required, label, description
- LLM prompts (`user_prompt`)
- Few-shot examples (`examples`)
- Output labels (`output_labels`)
- Shared base config (`base.yaml`)

## New Directory Structure

```
app/config/
├── templates/                        # SOURCE OF TRUTH
│   ├── base.yaml                     # System prompt, core fields, LLM config
│   ├── office_visit.yaml             # Per-type: fields, prompt, examples
│   ├── imaging_report.yaml
│   ├── lab_result.yaml
│   ├── surgical_report.yaml
│   ├── consultative_exam.yaml
│   ├── mental_health.yaml
│   ├── therapy_eval.yaml
│   ├── hospital_admission.yaml
│   ├── medical_source_statement.yaml
│   ├── medication_list.yaml
│   ├── function_report.yaml
│   ├── disability_report.yaml
│   ├── dde_assessment.yaml
│   └── exhibit_type_mapping.yaml
│
└── prompts/
    ├── _base/
    │   └── visit_types.yaml          # KEEP - classification rules
    ├── parsing/
    │   └── dde_parsing.yaml          # KEEP - DDE extraction
    └── reference/                    # NEW - documentation only
        ├── README.md
        ├── f_medical_parsing_template.yaml
        ├── chartvision_chronology_template.yaml
        ├── dde_section_a.yaml
        └── chronology_filtering.yaml
```

## Python Code Changes

### New: TemplateLoader

```python
# app/core/extraction/template_loader.py

class TemplateLoader:
    """Load visit-type templates from config/templates/."""

    def __init__(self):
        self._templates_dir = Path(__file__).parents[2] / "config" / "templates"
        self._base = self._load_yaml("base.yaml")
        self._cache = {}

    def get_system_prompt(self) -> str:
        """Get shared system prompt from base.yaml."""
        return self._base["system_prompt"]

    def get_template(self, visit_type: str) -> dict:
        """Load template for a visit type (e.g., 'office_visit')."""
        if visit_type not in self._cache:
            self._cache[visit_type] = self._load_yaml(f"{visit_type}.yaml")
        return self._cache[visit_type]

    def get_user_prompt(self, visit_type: str) -> str:
        """Get LLM user prompt for a visit type."""
        return self.get_template(visit_type)["user_prompt"]

    def get_fields(self, visit_type: str) -> dict:
        """Get field definitions for extraction."""
        return self.get_template(visit_type)["fields"]

    def get_output_labels(self, visit_type: str) -> list:
        """Get output labels for formatting."""
        return self.get_template(visit_type)["output_labels"]
```

### Files to Modify

| File | Change |
|------|--------|
| `text_extractor.py` | Use `TemplateLoader` instead of `text_extraction.yaml` |
| `vision_extractor.py` | Use `TemplateLoader` instead of `vision_extraction.yaml` |
| `occurrence_formatter.py` | Use `TemplateLoader.get_output_labels()` |
| `schema_loader.py` | Delegate to `TemplateLoader` or delete |

## File Changes

### DELETE (1,010 lines - redundant)

| File | Lines |
|------|-------|
| `prompts/_base/occurrence_schemas.yaml` | 382 |
| `prompts/extraction/text_extraction.yaml` | 242 |
| `prompts/extraction/vision_extraction.yaml` | 220 |
| `core/builders/formatter_config.yaml` | 166 |

### MOVE to reference/ (3,118 lines - documentation)

| File | Lines |
|------|-------|
| `prompts/schemas/f_medical_parsing_template.yaml` | 909 |
| `prompts/schemas/chartvision_chronology_template.yaml` | 832 |
| `prompts/extraction/dde_section_a.yaml` | 1,120 |
| `prompts/parsing/chronology_filtering.yaml` | 257 |

### KEEP (actively used)

| File | Reason |
|------|--------|
| `templates/*.yaml` (16 files) | Source of truth |
| `prompts/_base/visit_types.yaml` | Classification rules |
| `prompts/parsing/dde_parsing.yaml` | DDE extraction |

## Benefits

1. **Single source of truth** - All visit type definitions in `templates/`
2. **No redundancy** - Delete 1,010 lines of duplicated schemas
3. **Cleaner structure** - Unused docs moved to `reference/`
4. **Better LLM prompts** - Templates include few-shot examples
5. **Simpler code** - One loader instead of multiple

## Implementation Order

1. Create `TemplateLoader` class
2. Update `text_extractor.py` to use `TemplateLoader`
3. Update `vision_extractor.py` to use `TemplateLoader`
4. Update `occurrence_formatter.py` to use `TemplateLoader`
5. Run tests to verify
6. Delete redundant files
7. Move reference docs
8. Final test run
