"""
ChronologyEngine - Slim orchestrator for medical chronology extraction.

Replaces the 1,255-line UnifiedChronologyEngine monolith.
Delegates to focused components with parallel extraction support.
Supports format-based extraction routing (RAW_SSA, PROCESSED, COURT_TRANSCRIPT).
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from app.core.extraction.citation_resolver import CitationResolver
from app.core.extraction.format_detector import (
    RAW_SSA, PROCESSED, COURT_TRANSCRIPT, UNKNOWN
)

from .text_extractor import TextExtractor
from .vision_extractor import VisionExtractor
from .recovery_handler import RecoveryHandler
from .parallel_extractor import ParallelExtractor

logger = logging.getLogger(__name__)


@dataclass
class ChronologyResult:
    """Result container for chronology extraction (matches old API)."""
    events: List[Dict[str, Any]] = field(default_factory=list)
    processing_time: float = 0.0
    exhibit_count: int = 0
    error: Optional[str] = None


class ChronologyEngine:
    """
    Slim orchestrator for medical chronology extraction.

    Delegates to:
    - TextExtractor: LLM text extraction
    - VisionExtractor: Scanned page extraction
    - CitationResolver: Accurate page→exhibit citations

    Compatible with UnifiedChronologyEngine API for drop-in replacement.
    """

    def __init__(
        self,
        llm: "LLMPort" = None,
        llm_manager=None,  # Deprecated: use llm parameter
        enable_recovery: bool = True,
        enable_parallel: bool = True,
        max_concurrent: int = 5,
        allow_lazy_init: bool = True,
        ere_format: Optional[str] = None,
    ):
        """Initialize engine with LLM port.

        Args:
            llm: LLMPort implementation (preferred)
            llm_manager: Deprecated - use llm parameter instead
            enable_recovery: Enable sparse entry recovery via vision retry
            enable_parallel: Enable parallel exhibit extraction
            max_concurrent: Maximum concurrent exhibit extractions (default 5)
            allow_lazy_init: Allow lazy LLMManager init (for backward compat)
            ere_format: ERE format type for extraction routing (RAW_SSA, PROCESSED, COURT_TRANSCRIPT)
        """
        # Prefer new llm parameter, fall back to deprecated llm_manager
        self._llm_port = llm or llm_manager
        self._allow_lazy_init = allow_lazy_init

        self._text_extractor: Optional[TextExtractor] = None
        self._vision_extractor: Optional[VisionExtractor] = None
        self._recovery_handler: Optional[RecoveryHandler] = None
        self._parallel_extractor: Optional[ParallelExtractor] = None
        self._citation_resolver: Optional[CitationResolver] = None
        self._enable_recovery = enable_recovery
        self._enable_parallel = enable_parallel
        self._max_concurrent = max_concurrent
        self._ere_format = ere_format or UNKNOWN

    @property
    def llm(self):
        """Get LLM port, with optional lazy initialization."""
        if self._llm_port is None:
            if not self._allow_lazy_init:
                raise ValueError("LLM port required when allow_lazy_init=False")
            # Lazy init using BedrockAdapter for backward compatibility
            try:
                from app.adapters.llm.bedrock import BedrockAdapter
                self._llm_port = BedrockAdapter()
                logger.info("ChronologyEngine: BedrockAdapter initialized")
            except Exception as e:
                logger.error(f"Failed to initialize BedrockAdapter: {e}")
                raise
        return self._llm_port

    @property
    def llm_manager(self):
        """Deprecated: Use llm property instead."""
        return self.llm

    @property
    def text_extractor(self) -> TextExtractor:
        """Lazy initialization of text extractor."""
        if self._text_extractor is None:
            self._text_extractor = TextExtractor(self.llm)
        return self._text_extractor

    @property
    def vision_extractor(self) -> VisionExtractor:
        """Lazy initialization of vision extractor."""
        if self._vision_extractor is None:
            self._vision_extractor = VisionExtractor(self.llm)
        return self._vision_extractor

    @property
    def recovery_handler(self) -> Optional[RecoveryHandler]:
        """Lazy initialization of recovery handler."""
        if self._recovery_handler is None and self._enable_recovery and self.vision_extractor:
            self._recovery_handler = RecoveryHandler(self.vision_extractor.extract)
        return self._recovery_handler

    @property
    def parallel_extractor(self) -> Optional[ParallelExtractor]:
        """Lazy initialization of parallel extractor."""
        if self._parallel_extractor is None and self._enable_parallel:
            recovery_fn = None
            if self._enable_recovery and self.recovery_handler:
                recovery_fn = self.recovery_handler.recover_sparse_entries

            self._parallel_extractor = ParallelExtractor(
                text_extractor=self.text_extractor,
                vision_extractor=self.vision_extractor,
                max_concurrent=self._max_concurrent,
                recovery_fn=recovery_fn,
                ere_format=self._ere_format,
            )
        return self._parallel_extractor

    def set_exhibit_ranges(self, exhibit_ranges: List[Dict]) -> None:
        """Set exhibit ranges for citation resolution."""
        self._citation_resolver = CitationResolver(exhibit_ranges)

    async def generate_chronology(
        self,
        exhibits: Union[List[Dict], List[tuple]],
        case_info: Optional[Dict[str, Any]] = None
    ) -> ChronologyResult:
        """Generate chronology from exhibits (matches UnifiedChronologyEngine API).

        Args:
            exhibits: List of exhibit dicts with keys: exhibit_id, text, images, page_range
                     OR list of (exhibit_id, text) tuples for backward compatibility
            case_info: Optional case metadata

        Returns:
            ChronologyResult with .events list
        """
        start_time = time.time()

        try:
            # Normalize exhibits to dict format
            normalized = self._normalize_exhibits(exhibits)

            # Auto-initialize citation resolver from exhibit data if not set
            if not self._citation_resolver:
                exhibit_ranges = [
                    {
                        "exhibit_id": ex.get("exhibit_id", ""),
                        "start_page": ex.get("page_range", (0, 0))[0] if isinstance(ex.get("page_range"), tuple) else 0,
                        "end_page": ex.get("page_range", (0, 0))[1] if isinstance(ex.get("page_range"), tuple) else 0,
                    }
                    for ex in normalized
                    if ex.get("page_range") and isinstance(ex.get("page_range"), tuple)
                ]
                if exhibit_ranges:
                    self._citation_resolver = CitationResolver(exhibit_ranges)

            # Use parallel extraction if enabled and available
            if self._enable_parallel and self.parallel_extractor:
                all_entries = await self._generate_parallel(normalized)
            else:
                all_entries = await self._generate_sequential(normalized)

            # Apply citation resolution to all entries
            self._apply_citations(all_entries, normalized)

            processing_time = time.time() - start_time
            logger.info(
                f"ChronologyEngine processed {len(normalized)} exhibits -> "
                f"{len(all_entries)} entries in {processing_time:.2f}s"
            )

            return ChronologyResult(
                events=all_entries,
                processing_time=processing_time,
                exhibit_count=len(normalized),
            )

        except Exception as e:
            logger.error(f"Chronology generation failed: {e}")
            return ChronologyResult(
                events=[],
                processing_time=time.time() - start_time,
                error=str(e),
            )

    async def _generate_parallel(self, exhibits: List[Dict]) -> List[Dict[str, Any]]:
        """Generate chronology using parallel exhibit extraction."""
        logger.info(f"Using parallel extraction (max_concurrent={self._max_concurrent})")
        result = await self.parallel_extractor.extract_exhibits(exhibits)
        return result.all_entries

    async def _generate_sequential(self, exhibits: List[Dict]) -> List[Dict[str, Any]]:
        """Generate chronology using sequential exhibit extraction (fallback)."""
        all_entries = []
        for ex in exhibits:
            exhibit_id = ex.get("exhibit_id", "unknown")
            text = ex.get("text", "")
            images = ex.get("images", [])
            page_range = ex.get("page_range", (0, 0))
            scanned_pages = ex.get("scanned_page_nums", [])

            # Convert page_range tuple to list of page numbers
            if isinstance(page_range, tuple) and len(page_range) == 2:
                source_pages = list(range(page_range[0], page_range[1] + 1))
            else:
                source_pages = scanned_pages or []

            entries = await self.process_exhibit(
                text=text,
                exhibit_id=exhibit_id,
                source_pages=source_pages,
                images=images,
            )
            all_entries.extend(entries)
            logger.info(f"Extracted {len(entries)} entries from {exhibit_id}")

        return all_entries

    def _apply_citations(self, entries: List[Dict], exhibits: List[Dict]) -> None:
        """Apply citation resolution to all entries."""
        if not self._citation_resolver:
            return

        # Build exhibit_id -> page_range mapping
        exhibit_pages = {}
        for ex in exhibits:
            exhibit_id = ex.get("exhibit_id", "unknown")
            page_range = ex.get("page_range", (0, 0))
            scanned_pages = ex.get("scanned_page_nums", [])
            if isinstance(page_range, tuple) and len(page_range) == 2:
                exhibit_pages[exhibit_id] = list(range(page_range[0], page_range[1] + 1))
            else:
                exhibit_pages[exhibit_id] = scanned_pages or []

        # Apply citations to entries
        for entry in entries:
            exhibit_id = entry.get("exhibit_reference", "")
            source_pages = exhibit_pages.get(exhibit_id, [])
            if source_pages:
                entry["exhibit_reference"] = self._citation_resolver.format(source_pages[0])
                if len(source_pages) > 1:
                    entry["page_range"] = f"{source_pages[0]}-{source_pages[-1]}"

    def _normalize_exhibits(self, exhibits: Union[List[Dict], List[tuple]]) -> List[Dict]:
        """Normalize various exhibit formats to standard dict format."""
        normalized = []
        for ex in exhibits:
            if isinstance(ex, tuple) and len(ex) >= 2:
                # (exhibit_id, text) tuple format
                normalized.append({
                    "exhibit_id": ex[0],
                    "text": ex[1],
                    "images": [],
                    "page_range": (0, 0),
                })
            elif isinstance(ex, dict):
                # Already dict format from extract_f_exhibits_from_pdf
                normalized.append(ex)
            else:
                logger.warning(f"Unknown exhibit format: {type(ex)}")
        return normalized

    async def process_exhibit(
        self,
        text: str,
        exhibit_id: str,
        source_pages: List[int],
        images: Optional[List[bytes]] = None,
    ) -> List[Dict[str, Any]]:
        """Process exhibit and return entries with accurate citations.

        Args:
            text: Extracted text content
            exhibit_id: Exhibit identifier (e.g., "1F")
            source_pages: Page numbers for citation
            images: Optional scanned page images for vision extraction

        Returns:
            List of medical entry dictionaries with citations
        """
        entries = []

        # Primary extraction: text or vision
        if text.strip() and self.text_extractor:
            entries.extend(await self.text_extractor.extract(text, exhibit_id))

        if images and self.vision_extractor:
            entries.extend(
                await self.vision_extractor.extract(images, exhibit_id, source_pages)
            )

        # Recovery: retry sparse entries with vision
        if images and self.recovery_handler:
            entries = await self.recovery_handler.recover_sparse_entries(
                entries, images, exhibit_id, source_pages
            )

        # Inject accurate citations (overwrite LLM guesses)
        if self._citation_resolver and source_pages:
            for entry in entries:
                entry["exhibit_reference"] = self._citation_resolver.format(source_pages[0])
                if len(source_pages) > 1:
                    entry["page_range"] = f"{source_pages[0]}-{source_pages[-1]}"

        return entries

    async def process_exhibits(self, exhibits: List[Dict]) -> List[Dict[str, Any]]:
        """Process multiple exhibits.

        Args:
            exhibits: List of dicts with keys: text, exhibit_id, pages, images

        Returns:
            Combined list of all extracted entries
        """
        all_entries = []
        for ex in exhibits:
            entries = await self.process_exhibit(
                text=ex.get("text", ""),
                exhibit_id=ex.get("exhibit_id", "unknown"),
                source_pages=ex.get("pages", []),
                images=ex.get("images"),
            )
            all_entries.extend(entries)
        return all_entries
