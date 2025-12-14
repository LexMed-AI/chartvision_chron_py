"""
RecoveryHandler - Retry and recovery logic for medical chronology extraction.

Extracted from UnifiedChronologyEngine to enable modular reuse.
Handles:
- Sparse entry detection (entries with empty occurrence_treatment)
- Vision retry for sparse entries
- Entry merging and deduplication
"""
import logging
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)

# Use domain logic from content_analyzer
from app.core.extraction.content_analyzer import is_content_sparse as _content_is_sparse


def is_sparse_entry(entry: Dict[str, Any]) -> bool:
    """
    Check if an entry has sparse/empty occurrence_treatment content.

    Uses the visit-type-aware check from content_analyzer module.

    Args:
        entry: Medical chronology entry dict

    Returns:
        True if occurrence_treatment is empty or has only empty values
    """
    return _content_is_sparse(entry)


def find_sparse_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Find all entries with sparse/empty occurrence_treatment.

    Args:
        entries: List of medical chronology entries

    Returns:
        List of entries that need retry/enrichment
    """
    return [e for e in entries if is_sparse_entry(e)]


def merge_entry_with_vision(
    sparse_entry: Dict[str, Any],
    vision_entry: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge a sparse entry with a richer vision-extracted entry.

    Preserves the sparse entry's metadata but takes occurrence_treatment
    from the vision entry if it has more content.

    Args:
        sparse_entry: Original entry with empty occurrence_treatment
        vision_entry: Vision-extracted entry with content

    Returns:
        Merged entry with best of both
    """
    merged = sparse_entry.copy()

    vision_occ = vision_entry.get("occurrence_treatment", {})
    if not is_sparse_entry(vision_entry):
        merged["occurrence_treatment"] = vision_occ
        merged["_enriched_via_vision"] = True

    return merged


def deduplicate_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate entries based on (date, visit_type) key.

    Keeps the entry with more content in occurrence_treatment.

    Args:
        entries: List of entries potentially containing duplicates

    Returns:
        Deduplicated list preserving richest entries
    """
    seen = {}

    for entry in entries:
        key = (entry.get("date"), entry.get("visit_type"))

        if key not in seen:
            seen[key] = entry
        else:
            # Keep the entry with more content
            existing = seen[key]
            if is_sparse_entry(existing) and not is_sparse_entry(entry):
                seen[key] = entry

    return list(seen.values())


class RecoveryHandler:
    """
    Handles retry and recovery for sparse entries using vision extraction.

    Usage:
        handler = RecoveryHandler(vision_extractor.extract)
        enriched = await handler.recover_sparse_entries(
            entries, images, exhibit_id, page_nums
        )
    """

    def __init__(
        self,
        vision_extract_fn: Callable[[List[bytes], str, List[int]], Awaitable[List[Dict]]]
    ):
        """
        Initialize recovery handler.

        Args:
            vision_extract_fn: Async function that extracts entries from images.
                              Signature: (images, exhibit_id, page_nums) -> entries
        """
        self._vision_extract = vision_extract_fn

    async def recover_sparse_entries(
        self,
        entries: List[Dict[str, Any]],
        images: List[bytes],
        exhibit_id: str,
        page_nums: List[int],
    ) -> List[Dict[str, Any]]:
        """
        Attempt to enrich sparse entries using vision extraction.

        Process:
        1. Find entries with empty occurrence_treatment
        2. Run vision extraction on images
        3. Match vision results to sparse entries by date/type
        4. Replace sparse entries with richer vision entries
        5. Add any new entries discovered by vision

        Args:
            entries: Initial extraction results
            images: Page images for vision retry
            exhibit_id: Exhibit identifier
            page_nums: Page numbers for citation

        Returns:
            Enriched entries list with sparse entries filled
        """
        if not images:
            return entries

        sparse = find_sparse_entries(entries)
        if not sparse:
            return entries

        logger.info(
            f"Found {len(sparse)} sparse entries in {exhibit_id}, "
            f"retrying with vision extraction"
        )

        try:
            vision_entries = await self._vision_extract(images, exhibit_id, page_nums)
        except Exception as e:
            logger.warning(f"Vision retry failed for {exhibit_id}: {e}")
            return entries

        if not vision_entries:
            return entries

        # Build result list
        result = []
        existing_keys = set()

        for entry in entries:
            key = (entry.get("date"), entry.get("visit_type"))

            if is_sparse_entry(entry):
                # Try to find matching vision entry
                matched = self._find_matching_vision_entry(entry, vision_entries)
                if matched and not is_sparse_entry(matched):
                    merged = merge_entry_with_vision(entry, matched)
                    result.append(merged)
                    logger.info(
                        f"Filled sparse entry via vision: "
                        f"{entry.get('date')} {entry.get('visit_type')}"
                    )
                else:
                    result.append(entry)
            else:
                result.append(entry)

            existing_keys.add(key)

        # Add new entries from vision that weren't in original
        for vision_entry in vision_entries:
            key = (vision_entry.get("date"), vision_entry.get("visit_type"))
            if key not in existing_keys and not is_sparse_entry(vision_entry):
                result.append(vision_entry)
                existing_keys.add(key)
                logger.info(
                    f"Added new entry from vision: "
                    f"{vision_entry.get('date')} {vision_entry.get('visit_type')}"
                )

        return result

    def _find_matching_vision_entry(
        self,
        sparse_entry: Dict[str, Any],
        vision_entries: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Find a vision entry that matches the sparse entry by date and type."""
        sparse_date = sparse_entry.get("date", "")
        sparse_type = sparse_entry.get("visit_type", "")

        for vision_entry in vision_entries:
            if (vision_entry.get("date") == sparse_date and
                vision_entry.get("visit_type") == sparse_type):
                return vision_entry

        return None
