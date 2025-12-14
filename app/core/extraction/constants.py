"""Shared constants for medical chronology extraction.

This module provides a single source of truth for visit types, classification
rules, and occurrence schemas used across all extractors (text, vision, DDE).

All definitions are loaded from YAML files in prompts/_base/ directory.
"""

from pathlib import Path
from typing import Dict, List, Any
import yaml

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

_BASE_PATH = Path(__file__).parent / "prompts" / "_base"
_VISIT_TYPES_PATH = _BASE_PATH / "visit_types.yaml"
_OCCURRENCE_SCHEMAS_PATH = _BASE_PATH / "occurrence_schemas.yaml"


# =============================================================================
# YAML LOADING UTILITIES
# =============================================================================

def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file and return its contents as a dictionary."""
    if not path.exists():
        raise FileNotFoundError(f"Required YAML file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_visit_types() -> Dict[str, Any]:
    """Load visit types configuration."""
    return _load_yaml(_VISIT_TYPES_PATH)


def _load_occurrence_schemas() -> Dict[str, Any]:
    """Load occurrence schemas configuration."""
    return _load_yaml(_OCCURRENCE_SCHEMAS_PATH)


# =============================================================================
# LAZY LOADING CACHE
# =============================================================================

_visit_types_cache: Dict[str, Any] = {}
_occurrence_schemas_cache: Dict[str, Any] = {}


def _get_visit_types() -> Dict[str, Any]:
    """Get visit types config with lazy loading."""
    global _visit_types_cache
    if not _visit_types_cache:
        _visit_types_cache = _load_visit_types()
    return _visit_types_cache


def _get_occurrence_schemas() -> Dict[str, Any]:
    """Get occurrence schemas config with lazy loading."""
    global _occurrence_schemas_cache
    if not _occurrence_schemas_cache:
        _occurrence_schemas_cache = _load_occurrence_schemas()
    return _occurrence_schemas_cache


# =============================================================================
# PUBLIC CONSTANTS - Loaded from YAML
# =============================================================================

def get_valid_visit_types() -> List[str]:
    """Get the list of valid visit types.

    Returns:
        List of valid visit type strings.
    """
    return _get_visit_types()["valid_visit_types"]


def get_classification_rules() -> str:
    """Get the visit type classification rules for LLM prompts.

    Returns:
        String containing classification rules to embed in prompts.
    """
    return _get_visit_types()["classification_rules"]


def get_base_system_prompt() -> str:
    """Get the base system prompt for extraction.

    Returns:
        String containing the base system prompt.
    """
    return _get_visit_types()["base_system_prompt"]


def get_vision_additions() -> str:
    """Get vision-specific prompt additions.

    Returns:
        String containing vision-specific instructions.
    """
    return _get_visit_types()["vision_additions"]


def get_occurrence_schemas() -> Dict[str, Any]:
    """Get all occurrence treatment schemas.

    Returns:
        Dictionary mapping visit types to their field schemas.
    """
    return _get_occurrence_schemas()["schemas"]


def get_output_labels() -> Dict[str, List[str]]:
    """Get output labels for each visit type.

    Returns:
        Dictionary mapping visit types to their output label lists.
    """
    return _get_occurrence_schemas()["output_labels"]


def get_schema_for_visit_type(visit_type: str) -> Dict[str, Any]:
    """Get the occurrence schema for a specific visit type.

    Args:
        visit_type: The visit type to get the schema for.

    Returns:
        Dictionary containing the field definitions for that visit type.

    Raises:
        KeyError: If the visit type is not found.
    """
    schemas = get_occurrence_schemas()
    if visit_type not in schemas:
        raise KeyError(f"Unknown visit type: {visit_type}")
    return schemas[visit_type]


# =============================================================================
# CONVENIENCE CONSTANTS - For backward compatibility
# =============================================================================

# These are loaded at import time for simple access patterns
# Use get_* functions for lazy loading if startup time is critical

VALID_VISIT_TYPES: List[str] = [
    "office_visit",
    "imaging_report",
    "therapy_eval",
    "lab_result",
    "surgical_report",
    "emergency_visit",
    "inpatient_admission",
    "consultative_exam",
    "psych_visit",
    "diagnostic_study",
    "procedural_visit",
    "medical_source_statement",
]


def reload_constants() -> None:
    """Force reload of all constants from YAML files.

    Useful for testing or when YAML files are modified at runtime.
    """
    global _visit_types_cache, _occurrence_schemas_cache
    _visit_types_cache = {}
    _occurrence_schemas_cache = {}
