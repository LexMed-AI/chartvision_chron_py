"""
Source citation formatting for ChartVision chronology entries.

Handles exhibit reference formatting and source citation combination.
"""
import re
from typing import Any, Dict, List


def format_source(entry: Dict[str, Any]) -> str:
    """Format exhibit reference into source citation.

    Uses compact format: 1F@1-3 or 47F@2

    Args:
        entry: Chronology entry dict with exhibit_reference and/or page_range

    Returns:
        Formatted source citation string
    """
    # Try new format: exhibit_reference + page_range
    exhibit_ref = entry.get("exhibit_reference")
    if exhibit_ref:
        page_range = entry.get("page_range", "")
        if page_range:
            return f"{exhibit_ref}@{page_range}"
        return exhibit_ref

    # Fallback to old format - convert verbose to compact
    old_citation = entry.get("exhibit_citation", "")
    if old_citation:
        return _convert_verbose_citation(old_citation)

    return old_citation


def _convert_verbose_citation(citation: str) -> str:
    """Convert verbose citation format to compact format.

    Converts: "Ex. 1F, pp. 52-55 pp.52 of 55" → "1F@52-55"

    Args:
        citation: Verbose citation string

    Returns:
        Compact citation string
    """
    # Remove "Ex. " prefix
    result = citation.replace("Ex. ", "")

    # Replace ", pp. " with "@"
    result = result.replace(", pp. ", "@")

    # Remove " pp.X of Y" pagination hints (e.g., " pp.52 of 55")
    result = re.sub(r'\s+pp\.\d+\s+of\s+\d+', '', result)

    # Remove standalone " of X" suffixes
    result = re.sub(r'\s+of\s+\d+$', '', result)

    return result.strip()


def combine_sources(sources: List[str]) -> str:
    """Combine multiple source citations into a single string.

    Attempts to merge citations from the same exhibit into ranges.
    E.g., ["1F@52", "1F@53", "1F@55"] → "1F@52-55"

    Args:
        sources: List of source citation strings

    Returns:
        Combined citation string
    """
    if len(sources) == 1:
        return sources[0]

    # Try to extract exhibit ID and page numbers
    exhibit_pages: Dict[str, List[int]] = {}

    for source in sources:
        # Parse "1F@52" format
        match = re.match(r'(\d+F)@(\d+)', source)
        if match:
            exhibit = match.group(1)
            page = int(match.group(2))
            if exhibit not in exhibit_pages:
                exhibit_pages[exhibit] = []
            exhibit_pages[exhibit].append(page)

    if exhibit_pages:
        return _format_exhibit_ranges(exhibit_pages)

    # Fallback: join with commas
    return ", ".join(sorted(set(sources)))


def _format_exhibit_ranges(exhibit_pages: Dict[str, List[int]]) -> str:
    """Format exhibit pages as ranges.

    Args:
        exhibit_pages: Dict mapping exhibit IDs to page numbers

    Returns:
        Formatted string like "1F@52-55, 2F@10"
    """
    parts = []
    for exhibit, pages in sorted(exhibit_pages.items()):
        pages = sorted(set(pages))
        if len(pages) == 1:
            parts.append(f"{exhibit}@{pages[0]}")
        else:
            # Check if pages are contiguous for range format
            parts.append(f"{exhibit}@{pages[0]}-{pages[-1]}")
    return ", ".join(parts)
