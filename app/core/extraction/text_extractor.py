"""
TextExtractor - Extract medical data from text using LLM.

Extracted from UnifiedChronologyEngine._extract_with_template.
Loads prompts from config/templates/base.yaml (single source of truth).
Includes exponential backoff retry for API throttling.
Automatically chunks large texts to avoid Bedrock timeout.
"""
import logging
from typing import Any, Dict, List, Optional

from .constants import VALID_VISIT_TYPES
from .response_parser import ResponseParser
from .retry_utils import retry_with_backoff, RetryConfig
from .llm_config import LLM_SETTINGS
from .text_chunker import TextChunker, merge_chunk_results
from .template_loader import get_template_loader

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extract medical entries from text using LLM with detailed prompts."""

    def __init__(
        self,
        llm_manager,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        chunk_threshold: Optional[int] = None,
    ):
        self._llm = llm_manager
        self._parser = ResponseParser()
        self._retry_config = RetryConfig.for_bedrock()

        # Template loader for conditional schema loading
        self._template_loader = get_template_loader()
        base = self._template_loader.get_base()

        # Use centralized config, with optional overrides
        config = LLM_SETTINGS.text_extraction
        self._max_tokens = max_tokens or config.max_tokens
        self._temperature = temperature or config.temperature
        self._system_prompt = base.get(
            "system_prompt",
            "Extract medical chronology entries. Return JSON array."
        )

        # Chunker for large texts (default 40K chars to avoid Bedrock timeout)
        threshold = chunk_threshold or LLM_SETTINGS.max_input_chars
        # Use 40K as safe default to avoid timeout (12F at 53K was timing out)
        self._chunker = TextChunker(max_chars=min(threshold, 40000), overlap_chars=500)

    async def extract(self, text: str, exhibit_id: str) -> List[Dict[str, Any]]:
        """
        Extract medical entries from text with exponential backoff retry.

        Automatically chunks large texts to avoid Bedrock timeout.
        """
        if not text.strip():
            return []

        # Check if chunking is needed
        if self._chunker.needs_chunking(text):
            return await self._extract_chunked(text, exhibit_id)

        return await self._extract_single(text, exhibit_id)

    async def _extract_single(self, text: str, exhibit_id: str) -> List[Dict[str, Any]]:
        """Extract from a single text block (under chunk threshold)."""
        prompt = self._build_prompt(text, exhibit_id)

        try:
            response = await retry_with_backoff(
                self._llm.generate,
                prompt=prompt,
                model="haiku",
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=self._system_prompt,
                max_retries=self._retry_config.max_retries,
                base_delay=self._retry_config.base_delay,
                max_delay=self._retry_config.max_delay,
            )
            if not response:
                logger.warning(f"Empty response from LLM for {exhibit_id}")
                return []
            entries = self._parser.parse(response)
            return self._validate(entries, exhibit_id)
        except Exception as e:
            logger.error(f"Text extraction failed for {exhibit_id}: {e}")
            return []

    async def _extract_chunked(self, text: str, exhibit_id: str) -> List[Dict[str, Any]]:
        """Extract from large text by chunking and merging results."""
        chunks = self._chunker.chunk_text(text)
        logger.info(f"Chunking {exhibit_id}: {len(text):,} chars -> {len(chunks)} chunks")

        chunk_results = []
        for chunk in chunks:
            chunk_exhibit_id = f"{exhibit_id}#chunk{chunk.chunk_index + 1}of{chunk.total_chunks}"
            logger.info(f"Processing {chunk_exhibit_id} ({chunk.char_count:,} chars)")

            entries = await self._extract_single(chunk.text, chunk_exhibit_id)
            # Normalize exhibit_reference back to original (remove chunk suffix)
            for entry in entries:
                entry["exhibit_reference"] = exhibit_id
            chunk_results.append(entries)

        # Merge and deduplicate results from all chunks
        merged = merge_chunk_results(chunk_results, chunks)
        return self._validate(merged, exhibit_id)

    def _build_prompt(self, text: str, exhibit_id: str) -> str:
        """Build user prompt with conditional schema loading.

        Detects likely visit types from text and includes only relevant schemas.
        """
        return self._template_loader.build_user_prompt(text, exhibit_id)

    def _validate(self, entries: List[Dict], exhibit_id: str) -> List[Dict]:
        validated = []
        for entry in entries:
            if not entry or not isinstance(entry, dict):
                continue
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
