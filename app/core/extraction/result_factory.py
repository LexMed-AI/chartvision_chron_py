"""
Result Factory.

Creates standardized result objects for chronology extraction.
"""

from typing import Any, Dict


def create_error_result(
    error_message: str,
    processing_time: float,
    processing_mode: Any,
    analysis_level: Any
) -> Dict[str, Any]:
    """
    Create error result dict.

    Args:
        error_message: The error message
        processing_time: Time spent processing
        processing_mode: ProcessingMode enum value
        analysis_level: AnalysisLevel enum value

    Returns:
        Error result dict (to be converted to UnifiedChronologyResult)
    """
    from app.core.models.entry import MedicalTimeline

    return {
        'success': False,
        'processing_time': processing_time,
        'processing_mode': processing_mode,
        'analysis_level': analysis_level,
        'timeline': MedicalTimeline(events=[]),
        'events': [],
        'providers': [],
        'diagnoses': [],
        'treatment_gaps': [],
        'error_message': error_message
    }
