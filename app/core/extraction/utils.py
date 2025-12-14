"""
Chronology Utilities - Re-exports for backward compatibility.

This module re-exports functions from focused modules:
- exhibit_normalizer: Exhibit format normalization
- statistics: Quality metrics calculation
- pdf_exhibit_extractor: PDF bookmark extraction
- result_factory: Error result creation

Version: 4.0.0 - Modularized into focused components
"""

# Re-export from exhibit_normalizer
from app.core.extraction.exhibit_normalizer import (
    normalize_exhibits,
    is_f_section_exhibit,
)

# Re-export from statistics
from app.core.extraction.statistics import (
    calculate_confidence,
    calculate_quality_metrics,
    calculate_statistics,
)

# Re-export from pdf_exhibit_extractor
from app.core.extraction.pdf_exhibit_extractor import (
    extract_f_exhibits_from_pdf,
    load_bookmark_metadata,
)

# Re-export from result_factory
from app.core.extraction.result_factory import (
    create_error_result,
)

__all__ = [
    # Exhibit normalization
    "normalize_exhibits",
    "is_f_section_exhibit",
    # Statistics
    "calculate_confidence",
    "calculate_quality_metrics",
    "calculate_statistics",
    # PDF extraction
    "extract_f_exhibits_from_pdf",
    "load_bookmark_metadata",
    # Result factory
    "create_error_result",
]
