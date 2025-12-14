# Reference Documentation

These YAML files are **not loaded by the application**. They serve as reference documentation for the schema designs and extraction patterns.

## Files

- `chartvision_chronology_template.yaml` - Original ChartVision report structure template
- `f_medical_parsing_template.yaml` - F-section medical parsing schema reference
- `dde_section_a.yaml` - DDE Section A extraction schema reference
- `chronology_filtering.yaml` - Chronology filtering rules reference

## Active Schemas

The application loads schemas from:
- `config/templates/*.yaml` - Visit type templates (single source of truth)
- `prompts/_base/visit_types.yaml` - Visit type classification rules
- `prompts/parsing/dde_parsing.yaml` - DDE extraction prompts
