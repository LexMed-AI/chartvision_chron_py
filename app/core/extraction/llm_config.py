"""
Centralized LLM configuration for the ChronologyEngine.

All token limits, model settings, and extraction parameters
are defined here for consistency across extractors.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractionConfig:
    """Configuration for a single extraction type."""
    max_tokens: int
    temperature: float = 0.05
    model_preference: str = "haiku"


@dataclass
class LLMSettings:
    """
    Centralized LLM settings for ChronologyEngine extractors.

    Usage:
        from app.core.extraction.llm_config import LLM_SETTINGS

        max_tokens = LLM_SETTINGS.text_extraction.max_tokens
    """
    # Text extraction from native text exhibits
    text_extraction: ExtractionConfig = field(
        default_factory=lambda: ExtractionConfig(
            max_tokens=65000,  # Haiku 4.5 supports up to 65536
            temperature=0.05,
            model_preference="haiku",
        )
    )

    # Vision extraction from scanned pages
    vision_extraction: ExtractionConfig = field(
        default_factory=lambda: ExtractionConfig(
            max_tokens=65000,
            temperature=0.05,
            model_preference="haiku",
        )
    )

    # Recovery/retry extraction for sparse entries
    recovery_extraction: ExtractionConfig = field(
        default_factory=lambda: ExtractionConfig(
            max_tokens=8000,  # Smaller for targeted recovery
            temperature=0.05,
            model_preference="haiku",
        )
    )

    # Model IDs for Bedrock
    haiku_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    sonnet_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    # Retry configuration
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0

    # Chunking thresholds (for future implementation)
    max_input_chars: int = 100000  # Consider chunking above this
    chunk_overlap_chars: int = 500


# Global singleton instance
LLM_SETTINGS = LLMSettings()
