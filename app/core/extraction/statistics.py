"""
Chronology Statistics.

Calculates quality metrics and statistics for extracted medical events.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime (internal helper)."""
    if not date_str:
        return None
    try:
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y']:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    except Exception:
        return None


def calculate_confidence(
    data_completeness: float,
    providers: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]]
) -> float:
    """
    Calculate overall confidence score.

    Args:
        data_completeness: Ratio of processed to total exhibits
        providers: List of provider records
        timeline: List of timeline events

    Returns:
        Confidence score between 0.0 and 1.0
    """
    factors = []

    # Data completeness factor
    factors.append(data_completeness)

    # Provider reliability factor
    provider_count = len(set(p.get('name', '') for p in providers))
    factors.append(min(1.0, provider_count / 5.0))

    # Timeline consistency factor
    if timeline:
        dated_events = [e for e in timeline if _parse_date(e.get('date', ''))]
        factors.append(len(dated_events) / len(timeline))

    return sum(factors) / len(factors) if factors else 0.0


def calculate_quality_metrics(
    data_completeness: float,
    confidence_score: float,
    timeline: List[Dict[str, Any]],
    providers: List[Dict[str, Any]],
    diagnoses: List[Dict[str, Any]],
    treatments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate comprehensive quality metrics.

    Returns:
        Dict with quality metrics
    """
    return {
        'data_completeness': data_completeness,
        'confidence_score': confidence_score,
        'timeline_coverage': len(timeline),
        'provider_diversity': len(set(p.get('name', '') for p in providers)),
        'diagnosis_count': len(diagnoses),
        'treatment_documentation': len(treatments)
    }


def calculate_statistics(events: List) -> Dict[str, Any]:
    """
    Calculate statistics for events.

    Handles both MedicalEvent objects and dicts.

    Args:
        events: List of events (dicts or MedicalEvent objects)

    Returns:
        Statistics dict with total_events and date_range
    """
    if not events:
        return {'total_events': 0, 'date_range': 'No events'}

    dates = []
    for e in events:
        if hasattr(e, 'date'):
            date_val = e.date
        elif isinstance(e, dict):
            date_val = e.get('date')
        else:
            continue

        if date_val:
            if isinstance(date_val, str):
                parsed = _parse_date(date_val)
                if parsed:
                    dates.append(parsed)
            else:
                dates.append(date_val)

    if dates:
        date_range = f"{min(dates)} to {max(dates)}"
    else:
        date_range = "No dated events"

    return {
        'total_events': len(events),
        'date_range': date_range
    }
