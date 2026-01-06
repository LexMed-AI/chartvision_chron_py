"""
VisionExtractor - Extract medical data from scanned page images.

Extracted from UnifiedChronologyEngine._extract_with_vision.
Loads prompts from config/templates/base.yaml (single source of truth).
Includes exponential backoff retry for API throttling.
"""
import logging
from typing import Any, Dict, List, Optional

from .constants import VALID_VISIT_TYPES
from .response_parser import ResponseParser
from .retry_utils import retry_with_backoff, RetryConfig
from .llm_config import LLM_SETTINGS
from .template_loader import get_template_loader
from app.core.models.citation import Citation

logger = logging.getLogger(__name__)


class VisionExtractor:
    """Extract medical entries from scanned page images with detailed prompts."""

    def __init__(
        self,
        llm_manager,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        self._llm = llm_manager
        self._parser = ResponseParser()
        self._retry_config = RetryConfig.for_bedrock()

        # Load prompts from templates/base.yaml (single source of truth)
        loader = get_template_loader()
        base = loader.get_base()
        llm_config = base.get("llm_config", {})

        # Use centralized config, with optional overrides
        config = LLM_SETTINGS.vision_extraction
        self._max_tokens = max_tokens or config.max_tokens
        self._temperature = temperature or config.temperature
        self._batch_size = llm_config.get("batch_size", 10)
        self._system_prompt = base.get(
            "system_prompt",
            "Extract medical chronology from images. Return JSON array."
        )
        # Vision uses a slightly modified prompt for images
        self._user_prompt_template = base.get("user_prompt", "").replace(
            "**MEDICAL RECORDS:**\n  {medical_content}",
            "**IMAGES:** {page_count} scanned page images"
        )

    async def extract(
        self,
        images: List[bytes],
        exhibit_id: str,
        page_nums: List[int],
        exhibit_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Extract medical entries from page images.

        Args:
            images: List of PNG image bytes
            exhibit_id: Exhibit identifier (e.g., "1F")
            page_nums: Corresponding page numbers for citation
            exhibit_context: Optional context with exhibit_start, exhibit_end, total_pages

        Returns:
            List of medical entry dictionaries
        """
        if not images:
            return []

        all_entries = []
        for i in range(0, len(images), self._batch_size):
            batch_imgs = images[i:i + self._batch_size]
            batch_pages = page_nums[i:i + self._batch_size] if page_nums else []
            try:
                entries = await self._extract_batch(batch_imgs, exhibit_id, batch_pages)
                # Attach citations to entries
                if batch_pages and exhibit_context:
                    for entry in entries:
                        citation = self._build_citation(batch_pages, exhibit_id, exhibit_context)
                        entry["citation"] = citation
                all_entries.extend(entries)
            except Exception as e:
                logger.error(f"Vision batch failed for {exhibit_id}: {e}")
        return all_entries

    async def _extract_batch(
        self, images: List[bytes], exhibit_id: str, page_nums: List[int]
    ) -> List[Dict]:
        """Process a batch of images through vision LLM with retry."""
        prompt = self._build_prompt(len(images), exhibit_id, page_nums)

        # Use retry wrapper for throttling resilience
        response = await retry_with_backoff(
            self._llm.generate_with_vision,
            prompt=prompt,
            images=images,
            model="haiku",
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=self._system_prompt,
            max_retries=self._retry_config.max_retries,
            base_delay=self._retry_config.base_delay,
            max_delay=self._retry_config.max_delay,
        )

        entries = self._parser.parse(response)
        return self._validate(entries, exhibit_id)

    def _build_prompt(self, page_count: int, exhibit_id: str, page_nums: List[int]) -> str:
        """Build user prompt from template."""
        if self._user_prompt_template:
            return self._user_prompt_template.replace(
                "{page_count}", str(page_count)
            ).replace(
                "{exhibit_id}", exhibit_id
            ).replace(
                "{page_nums}", str(page_nums)
            )
        # Fallback minimal prompt
        return f"""Extract medical entries from these {page_count} page images.
EXHIBIT ID: {exhibit_id}
PAGE NUMBERS: {page_nums}
Return JSON array only."""

    def _validate(self, entries: List[Dict], exhibit_id: str) -> List[Dict]:
        """Validate and normalize entries."""
        validated = []
        for entry in entries:
            if not entry.get("date"):
                continue
            entry.setdefault("exhibit_reference", exhibit_id)
            if entry.get("visit_type") not in VALID_VISIT_TYPES:
                entry["visit_type"] = "office_visit"
            entry.setdefault("provider", "Not Specified")
            entry.setdefault("facility", "Not Specified")
            entry.setdefault("occurrence_treatment", {})
            validated.append(entry)
        return validated

    def _build_citation(
        self,
        page_nums: List[int],
        exhibit_id: str,
        exhibit_context: Dict[str, Any],
    ) -> Citation:
        """Build citation from batch page numbers.

        Args:
            page_nums: Page numbers in the batch
            exhibit_id: Exhibit identifier (e.g., "25F")
            exhibit_context: Context with exhibit_start, total_pages

        Returns:
            Citation with deterministic page attribution
        """
        exhibit_start = exhibit_context.get("exhibit_start", page_nums[0])
        total_pages = exhibit_context.get("total_pages")

        primary_page = page_nums[0]
        relative_page = primary_page - exhibit_start + 1

        citation = Citation(
            exhibit_id=exhibit_id,
            relative_page=relative_page,
            absolute_page=primary_page,
            total_pages=total_pages,
            is_estimated=False,  # Vision pages are deterministic
            confidence=0.95,
            source_type="ere",
        )

        # Add range if multi-page batch
        if len(page_nums) > 1:
            end_page = page_nums[-1]
            citation.end_relative_page = end_page - exhibit_start + 1
            citation.end_absolute_page = end_page

        return citation
