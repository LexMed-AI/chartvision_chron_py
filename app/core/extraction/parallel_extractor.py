"""
ParallelExtractor - Parallel exhibit-level extraction orchestration.

Extracted from UnifiedChronologyEngine to enable modular reuse.
Handles:
- Concurrent text + vision extraction within a single exhibit
- Semaphore-controlled parallel processing across multiple exhibits
- Graceful error handling for failed extractions
- Format-based extraction routing (RAW_SSA, PROCESSED, COURT_TRANSCRIPT)

Format-based routing optimizations:
- PROCESSED: 100% searchable text, skip vision extraction entirely
- COURT_TRANSCRIPT: Image-only, skip text extraction
- RAW_SSA: ~94% searchable, use text + vision fallback for scanned pages
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Awaitable

from app.core.extraction.format_detector import (
    RAW_SSA, PROCESSED, COURT_TRANSCRIPT, UNKNOWN
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractionTask:
    """Represents a single extraction task."""
    exhibit_id: str
    task_type: str  # "text" or "vision"
    coroutine: Awaitable[List[Dict[str, Any]]]


@dataclass
class ExhibitExtractionResult:
    """Result from extracting a single exhibit."""
    exhibit_id: str
    entries: List[Dict[str, Any]] = field(default_factory=list)
    text_entries: int = 0
    vision_entries: int = 0
    error: Optional[str] = None
    used_vision: bool = False


@dataclass
class ParallelExtractionResult:
    """Result from parallel extraction of multiple exhibits."""
    all_entries: List[Dict[str, Any]] = field(default_factory=list)
    exhibit_results: List[ExhibitExtractionResult] = field(default_factory=list)
    total_exhibits: int = 0
    successful_exhibits: int = 0
    failed_exhibits: int = 0


class ParallelExtractor:
    """
    Orchestrates parallel extraction across multiple exhibits.

    Supports two levels of parallelism:
    1. Within-exhibit: text + vision extraction run concurrently via asyncio.gather
    2. Across-exhibits: multiple exhibits processed with semaphore-controlled concurrency

    Usage (function-based - legacy):
        extractor = ParallelExtractor(
            text_extract_fn=text_extractor.extract,
            vision_extract_fn=vision_extractor.extract,
            max_concurrent=5,
        )
        result = await extractor.extract_exhibits(exhibits)

    Usage (object-based - preferred for citation context):
        extractor = ParallelExtractor(
            text_extractor=text_extractor,
            vision_extractor=vision_extractor,
            max_concurrent=5,
        )
        result = await extractor.extract_exhibits(exhibits)
    """

    def __init__(
        self,
        text_extract_fn: Optional[Callable[[str, str], Awaitable[List[Dict[str, Any]]]]] = None,
        vision_extract_fn: Optional[Callable[[List[bytes], str, List[int]], Awaitable[List[Dict[str, Any]]]]] = None,
        max_concurrent: int = 5,
        recovery_fn: Optional[Callable[[List[Dict], List[bytes], str, List[int]], Awaitable[List[Dict]]]] = None,
        ere_format: Optional[str] = None,
        text_extractor: Optional[Any] = None,
        vision_extractor: Optional[Any] = None,
    ):
        """
        Initialize parallel extractor.

        Args:
            text_extract_fn: Async function for text extraction (text, exhibit_id) -> entries (legacy)
            vision_extract_fn: Optional async function for vision extraction (legacy)
            max_concurrent: Maximum concurrent exhibit extractions
            recovery_fn: Optional recovery handler for sparse entries
            ere_format: ERE format type for extraction routing optimization
            text_extractor: TextExtractor object with .extract() method (preferred)
            vision_extractor: VisionExtractor object with .extract() method (preferred)
        """
        # Support both function-based (legacy) and object-based (preferred) approaches
        self._text_extract = text_extract_fn
        self._vision_extract = vision_extract_fn
        self._text_extractor = text_extractor
        self._vision_extractor = vision_extractor
        self._recovery_fn = recovery_fn
        self._max_concurrent = max_concurrent
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._ere_format = ere_format or UNKNOWN

    async def extract_exhibits(
        self,
        exhibits: List[Dict[str, Any]],
    ) -> ParallelExtractionResult:
        """
        Extract entries from multiple exhibits in parallel.

        Args:
            exhibits: List of exhibit dicts with keys:
                - exhibit_id: str
                - text: str (optional)
                - images: List[bytes] (optional)
                - page_range: tuple (optional)
                - scanned_page_nums: List[int] (optional)

        Returns:
            ParallelExtractionResult with combined entries and per-exhibit results
        """
        if not exhibits:
            return ParallelExtractionResult()

        # Create semaphore for concurrent control
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

        # Create extraction tasks for all exhibits
        tasks = [
            self._extract_single_exhibit(exhibit)
            for exhibit in exhibits
        ]

        # Run all exhibits with controlled concurrency
        exhibit_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        result = ParallelExtractionResult(total_exhibits=len(exhibits))

        for i, er in enumerate(exhibit_results):
            if isinstance(er, Exception):
                logger.error(f"Exhibit extraction failed: {er}")
                result.failed_exhibits += 1
                result.exhibit_results.append(ExhibitExtractionResult(
                    exhibit_id=exhibits[i].get("exhibit_id", f"unknown_{i}"),
                    error=str(er),
                ))
            else:
                result.all_entries.extend(er.entries)
                result.exhibit_results.append(er)
                if er.error:
                    result.failed_exhibits += 1
                else:
                    result.successful_exhibits += 1

        logger.info(
            f"ParallelExtractor: {result.successful_exhibits}/{result.total_exhibits} exhibits, "
            f"{len(result.all_entries)} total entries"
        )

        return result

    def _build_exhibit_context(self, exhibit: Dict[str, Any]) -> Dict[str, Any]:
        """Build exhibit context for citation tracking.

        Args:
            exhibit: Exhibit dict with exhibit_id, page_range, etc.

        Returns:
            Context dict with exhibit_id, exhibit_start, exhibit_end, total_pages
        """
        page_range = exhibit.get("page_range", (0, 0))
        exhibit_start = page_range[0] if isinstance(page_range, tuple) and len(page_range) >= 1 else 0
        exhibit_end = page_range[1] if isinstance(page_range, tuple) and len(page_range) >= 2 else 0
        total_pages = exhibit_end - exhibit_start + 1 if exhibit_start else 0

        return {
            "exhibit_id": exhibit.get("exhibit_id", ""),
            "exhibit_start": exhibit_start,
            "exhibit_end": exhibit_end,
            "total_pages": total_pages,
        }

    async def _process_exhibit(
        self,
        exhibit: Dict[str, Any],
    ) -> ExhibitExtractionResult:
        """Process a single exhibit - internal method for testing.

        This is an alias for _extract_single_exhibit, exposed for testing purposes.
        """
        # Ensure semaphore exists
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return await self._extract_single_exhibit(exhibit)

    async def _extract_single_exhibit(
        self,
        exhibit: Dict[str, Any],
    ) -> ExhibitExtractionResult:
        """
        Extract entries from a single exhibit with text+vision parallelism.

        Uses semaphore to control overall concurrency.
        Passes exhibit context to extractors for citation tracking.
        """
        async with self._semaphore:
            exhibit_id = exhibit.get("exhibit_id", "unknown")
            text = exhibit.get("text", "")
            images = exhibit.get("images", [])
            pages = exhibit.get("pages", [])
            page_range = exhibit.get("page_range", (0, 0))
            scanned_page_nums = exhibit.get("scanned_page_nums", [])

            # Derive page numbers from page_range if scanned_page_nums not provided
            if not scanned_page_nums and isinstance(page_range, tuple) and len(page_range) == 2:
                scanned_page_nums = list(range(page_range[0], page_range[1] + 1))

            # Build exhibit context for citation tracking
            exhibit_context = self._build_exhibit_context(exhibit)

            result = ExhibitExtractionResult(exhibit_id=exhibit_id)

            try:
                extraction_tasks = []

                # Format-based extraction routing
                skip_text = self._ere_format == COURT_TRANSCRIPT
                skip_vision = self._ere_format == PROCESSED

                # Prepare text extraction task (skip for COURT_TRANSCRIPT - images only)
                if text.strip() and not skip_text:
                    text_task = self._create_text_extraction_task(
                        text, exhibit_id, pages, exhibit_context
                    )
                    if text_task:
                        extraction_tasks.append(("text", text_task))
                elif skip_text:
                    logger.debug(f"Skipping text extraction for {exhibit_id} (COURT_TRANSCRIPT format)")

                # Prepare vision extraction task (skip for PROCESSED - 100% searchable)
                if images and not skip_vision:
                    vision_task = self._create_vision_extraction_task(
                        images, exhibit_id, scanned_page_nums, exhibit_context
                    )
                    if vision_task:
                        result.used_vision = True
                        extraction_tasks.append(("vision", vision_task))
                elif skip_vision and images:
                    logger.debug(f"Skipping vision extraction for {exhibit_id} (PROCESSED format)")

                if not extraction_tasks:
                    return result

                # Run text and vision extraction in parallel within this exhibit
                task_results = await asyncio.gather(
                    *[t[1] for t in extraction_tasks],
                    return_exceptions=True
                )

                # Process results
                entries = []
                for i, (task_type, _) in enumerate(extraction_tasks):
                    task_result = task_results[i]
                    if isinstance(task_result, Exception):
                        logger.warning(f"{task_type} extraction failed for {exhibit_id}: {task_result}")
                    else:
                        entries.extend(task_result)
                        if task_type == "text":
                            result.text_entries = len(task_result)
                            logger.debug(f"Extracted {len(task_result)} entries from text in {exhibit_id}")
                        else:
                            result.vision_entries = len(task_result)
                            logger.info(f"Extracted {len(task_result)} entries via vision from {exhibit_id}")

                # Apply recovery for sparse entries if handler provided
                # Skip recovery for PROCESSED format (100% searchable, no scanned pages)
                if images and self._recovery_fn and self._ere_format != PROCESSED:
                    entries = await self._recovery_fn(
                        entries, images, exhibit_id, scanned_page_nums
                    )
                elif self._ere_format == PROCESSED and images:
                    logger.debug(f"Skipping recovery for {exhibit_id} (PROCESSED format)")

                result.entries = entries
                logger.info(f"Extracted {len(entries)} total entries from {exhibit_id}")

            except Exception as e:
                result.error = str(e)
                logger.error(f"Failed to extract exhibit {exhibit_id}: {e}")

            return result

    def _create_text_extraction_task(
        self,
        text: str,
        exhibit_id: str,
        pages: List[Any],
        exhibit_context: Dict[str, Any],
    ) -> Optional[Awaitable[List[Dict[str, Any]]]]:
        """Create text extraction task using object-based or function-based extractor."""
        # Prefer object-based extractor (supports exhibit_context)
        if self._text_extractor is not None:
            return self._text_extractor.extract(
                text=text,
                exhibit_id=exhibit_id,
                pages=pages if pages else None,
                exhibit_context=exhibit_context,
            )
        # Fall back to function-based extractor (legacy)
        if self._text_extract is not None:
            return self._text_extract(text, exhibit_id)
        return None

    def _create_vision_extraction_task(
        self,
        images: List[bytes],
        exhibit_id: str,
        page_nums: List[int],
        exhibit_context: Dict[str, Any],
    ) -> Optional[Awaitable[List[Dict[str, Any]]]]:
        """Create vision extraction task using object-based or function-based extractor."""
        # Prefer object-based extractor (supports exhibit_context)
        if self._vision_extractor is not None:
            return self._vision_extractor.extract(
                images=images,
                exhibit_id=exhibit_id,
                page_nums=page_nums,
                exhibit_context=exhibit_context,
            )
        # Fall back to function-based extractor (legacy)
        if self._vision_extract is not None:
            return self._vision_extract(images, exhibit_id, page_nums)
        return None

    async def extract_single(
        self,
        text: str,
        exhibit_id: str,
        images: Optional[List[bytes]] = None,
        page_nums: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convenience method for extracting a single exhibit without parallel overhead.

        Args:
            text: Text content
            exhibit_id: Exhibit identifier
            images: Optional page images for vision extraction
            page_nums: Page numbers for citation

        Returns:
            List of extracted entries
        """
        # Ensure semaphore exists for single extraction
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)

        exhibit = {
            "exhibit_id": exhibit_id,
            "text": text,
            "images": images or [],
            "scanned_page_nums": page_nums or [],
        }
        result = await self._extract_single_exhibit(exhibit)
        return result.entries
