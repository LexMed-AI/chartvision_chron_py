"""
ChunkMergeRetryHandler - Retry logic for sparse entries using merged text chunks.

Extracted from UnifiedChronologyEngine to enable modular reuse.
Handles:
- Detection of entries with empty occurrence_treatment
- Retry extraction with merged adjacent text chunks
- Matching retry results to original sparse entries
"""
import logging
from typing import Any, Callable, Dict, List, Optional, Awaitable

logger = logging.getLogger(__name__)


class ChunkMergeRetryHandler:
    """
    Handles retry for sparse entries using merged adjacent text chunks.

    When initial text extraction produces entries with empty occurrence_treatment,
    this handler retries with the current text merged with adjacent text to provide
    more context for the LLM to extract complete information.

    Usage:
        handler = ChunkMergeRetryHandler(text_extract_fn)
        enriched = await handler.retry_with_merged_chunks(
            entries, text, adjacent_text, exhibit_id
        )
    """

    def __init__(
        self,
        text_extract_fn: Callable[[str, str], Awaitable[List[Dict[str, Any]]]]
    ):
        """
        Initialize chunk merge retry handler.

        Args:
            text_extract_fn: Async function that extracts entries from text.
                            Signature: (text, exhibit_id) -> entries
        """
        self._text_extract = text_extract_fn
        self._retry_attempted = False

    def _is_empty_occurrence(self, occ: Dict[str, Any]) -> bool:
        """Check if occurrence_treatment dict has no meaningful content."""
        if not occ:
            return True
        if not isinstance(occ, dict):
            return not bool(str(occ).strip())

        # Check if all values are empty/None (excluding metadata fields)
        for key, value in occ.items():
            if key in ("visit_type", "applies_to"):
                continue
            if value:
                if isinstance(value, str) and value.strip():
                    return False
                if isinstance(value, list) and len(value) > 0:
                    return False
                if isinstance(value, dict) and any(v for v in value.values() if v):
                    return False
        return True

    def _find_sparse_entries(
        self,
        entries: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Separate entries into sparse (needs retry) and complete.

        Returns:
            Tuple of (sparse_entries, complete_entries)
        """
        sparse = []
        complete = []

        for entry in entries:
            occ = entry.get("occurrence_treatment", {})
            if self._is_empty_occurrence(occ):
                sparse.append(entry)
            else:
                complete.append(entry)

        return sparse, complete

    async def retry_with_merged_chunks(
        self,
        entries: List[Dict[str, Any]],
        text: str,
        adjacent_text: Optional[str],
        exhibit_id: str,
        raw_text_preview: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Retry extraction for sparse entries using merged text chunks.

        Process:
        1. Identify entries with empty occurrence_treatment
        2. If adjacent text available, merge and retry extraction
        3. Match retry results to sparse entries by date/visit_type
        4. Return combined complete entries

        Args:
            entries: Initial extraction results
            text: Original text chunk
            adjacent_text: Adjacent text chunk to merge for retry
            exhibit_id: Exhibit identifier
            raw_text_preview: Raw text to attach to unrecoverable sparse entries

        Returns:
            Enriched entries list with sparse entries filled where possible
        """
        needs_retry, complete_entries = self._find_sparse_entries(entries)

        if not needs_retry:
            return entries

        # Try chunk merge retry if adjacent text available
        if adjacent_text and not self._retry_attempted:
            self._retry_attempted = True
            logger.info(
                f"Retrying {len(needs_retry)} empty entries with merged chunk for {exhibit_id}"
            )

            # Merge current text with adjacent text for retry
            merged_text = f"{text}\n\n--- CONTINUATION ---\n\n{adjacent_text}"

            try:
                retry_entries = await self._text_extract(merged_text, exhibit_id)

                # Match retry results to empty entries by date/visit_type
                for retry_entry in retry_entries:
                    retry_occ = retry_entry.get("occurrence_treatment", {})
                    if not self._is_empty_occurrence(retry_occ):
                        # Find matching empty entry
                        matched = False
                        for i, empty_entry in enumerate(needs_retry):
                            if (empty_entry.get("date") == retry_entry.get("date") and
                                empty_entry.get("visit_type") == retry_entry.get("visit_type")):
                                # Use the retry entry with content
                                complete_entries.append(retry_entry)
                                needs_retry.pop(i)
                                matched = True
                                logger.info(
                                    f"Filled sparse entry via chunk merge: "
                                    f"{retry_entry.get('date')} {retry_entry.get('visit_type')}"
                                )
                                break

                        if not matched:
                            # New entry from merged context
                            complete_entries.append(retry_entry)
                            logger.info(
                                f"Added new entry from chunk merge: "
                                f"{retry_entry.get('date')} {retry_entry.get('visit_type')}"
                            )

            except Exception as e:
                logger.warning(f"Chunk merge retry failed for {exhibit_id}: {e}")
            finally:
                self._retry_attempted = False

        # Add raw_text_preview to entries with empty content for fallback display
        for entry in needs_retry:
            if raw_text_preview:
                entry["raw_text_preview"] = raw_text_preview
            complete_entries.append(entry)

        return complete_entries

    def reset(self):
        """Reset retry state for new exhibit processing."""
        self._retry_attempted = False
