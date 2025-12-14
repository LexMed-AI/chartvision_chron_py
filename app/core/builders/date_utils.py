"""
Date parsing and conversion utilities for ChartVision builders.

Provides consistent date handling across all builder components.
"""
import logging
from datetime import date, datetime
from typing import Optional, Union

logger = logging.getLogger(__name__)


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string to date object.

    Supports multiple formats commonly found in medical records:
    - YYYY-MM-DD (ISO format)
    - MM/DD/YYYY (US format)
    - MM-DD-YYYY (US format with dashes)

    Args:
        date_str: Date string to parse, or None

    Returns:
        Parsed date object, or None if parsing fails
    """
    if not date_str:
        return None

    # Already a date/datetime object
    if isinstance(date_str, date):
        return date_str if not isinstance(date_str, datetime) else date_str.date()
    if isinstance(date_str, datetime):
        return date_str.date()

    # Try ISO format first (most common in our data)
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        pass

    # Try US format with slashes
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").date()
    except ValueError:
        pass

    # Try US format with dashes
    try:
        return datetime.strptime(date_str, "%m-%d-%Y").date()
    except ValueError:
        pass

    logger.warning(f"Could not parse date: {date_str}")
    return None


def to_datetime(d: Optional[Union[date, datetime]]) -> Optional[datetime]:
    """Convert date to datetime.

    Args:
        d: Date or datetime object, or None

    Returns:
        Datetime object (at midnight), or None if input is None
    """
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    return datetime.combine(d, datetime.min.time())


def safe_date_or_default(
    date_str: Optional[str],
    default: Optional[date] = None,
) -> Optional[date]:
    """Parse date with fallback to default value.

    Args:
        date_str: Date string to parse
        default: Default value if parsing fails (None if not specified)

    Returns:
        Parsed date or default value
    """
    parsed = parse_date(date_str)
    return parsed if parsed is not None else default
