"""
TextChunker - Split large text into processable chunks for LLM extraction.

Handles exhibits that exceed Bedrock request timeout limits (~50K chars).
Uses paragraph-aware splitting to maintain context at chunk boundaries.
"""
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """A chunk of text with metadata for processing."""
    text: str
    chunk_index: int
    total_chunks: int
    start_char: int
    end_char: int
    is_continuation: bool = False

    @property
    def char_count(self) -> int:
        return len(self.text)


class TextChunker:
    """
    Split large text into processable chunks for LLM extraction.

    Strategy:
    1. If text is under threshold, return as single chunk
    2. Split at paragraph boundaries (double newline) when possible
    3. Fall back to sentence boundaries if paragraphs are too large
    4. Use overlap to maintain context at boundaries

    Usage:
        chunker = TextChunker(max_chars=40000, overlap_chars=500)
        chunks = chunker.chunk_text(large_text)
        for chunk in chunks:
            result = await extractor.extract(chunk.text, exhibit_id)
    """

    def __init__(
        self,
        max_chars: int = 40000,
        overlap_chars: int = 500,
        min_chunk_chars: int = 1000,
    ):
        """
        Initialize text chunker.

        Args:
            max_chars: Maximum characters per chunk (default 40K for Bedrock safety)
            overlap_chars: Characters to overlap between chunks for context
            min_chunk_chars: Minimum chunk size to avoid tiny fragments
        """
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self.min_chunk_chars = min_chunk_chars

    def needs_chunking(self, text: str) -> bool:
        """Check if text exceeds chunking threshold."""
        return len(text) > self.max_chars

    def chunk_text(self, text: str) -> List[TextChunk]:
        """
        Split text into chunks with overlap.

        Args:
            text: Full text to chunk

        Returns:
            List of TextChunk objects
        """
        if not text:
            return []

        if not self.needs_chunking(text):
            return [TextChunk(
                text=text,
                chunk_index=0,
                total_chunks=1,
                start_char=0,
                end_char=len(text),
                is_continuation=False,
            )]

        logger.info(f"Chunking {len(text):,} chars into ~{len(text) // self.max_chars + 1} chunks")

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            # Calculate end position
            end = min(start + self.max_chars, len(text))

            # If not at the end, find a good break point
            if end < len(text):
                end = self._find_break_point(text, start, end)

            chunk_text = text[start:end]

            chunks.append(TextChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                total_chunks=0,  # Will be set after all chunks created
                start_char=start,
                end_char=end,
                is_continuation=chunk_index > 0,
            ))

            # Move start with overlap (but not past the end we just used)
            start = max(end - self.overlap_chars, start + self.min_chunk_chars)
            if start >= len(text):
                break
            chunk_index += 1

        # Update total_chunks count
        total = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total

        logger.info(f"Created {total} chunks: {[c.char_count for c in chunks]}")
        return chunks

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """
        Find a good break point near the end position.

        Priority:
        1. Paragraph boundary (double newline)
        2. Section header (newline followed by caps)
        3. Sentence boundary (period + space)
        4. Any newline
        5. Word boundary (space)
        6. Fall back to hard cut
        """
        search_start = max(start, end - 2000)  # Look back up to 2000 chars
        search_text = text[search_start:end]

        # Try paragraph boundary (double newline)
        para_matches = list(re.finditer(r'\n\n+', search_text))
        if para_matches:
            last_para = para_matches[-1]
            return search_start + last_para.end()

        # Try section header (newline + uppercase)
        header_matches = list(re.finditer(r'\n[A-Z][A-Z\s]{2,}:', search_text))
        if header_matches:
            last_header = header_matches[-1]
            return search_start + last_header.start() + 1  # After the newline

        # Try sentence boundary
        sentence_matches = list(re.finditer(r'[.!?]\s+', search_text))
        if sentence_matches:
            last_sentence = sentence_matches[-1]
            return search_start + last_sentence.end()

        # Try any newline
        newline_matches = list(re.finditer(r'\n', search_text))
        if newline_matches:
            last_newline = newline_matches[-1]
            return search_start + last_newline.end()

        # Try word boundary
        space_matches = list(re.finditer(r'\s', search_text))
        if space_matches:
            last_space = space_matches[-1]
            return search_start + last_space.end()

        # Hard cut (shouldn't normally happen)
        return end


def merge_chunk_results(
    chunk_results: List[List[dict]],
    chunks: List[TextChunk],
) -> List[dict]:
    """
    Merge extraction results from multiple chunks.

    Handles deduplication of entries that appear in overlap regions.
    Uses date + visit_type + provider as signature for matching.

    Args:
        chunk_results: List of extraction results per chunk
        chunks: Original TextChunk objects (for metadata)

    Returns:
        Merged, deduplicated list of entries
    """
    if not chunk_results:
        return []

    if len(chunk_results) == 1:
        return chunk_results[0]

    seen_signatures = set()
    merged = []

    for i, (entries, chunk) in enumerate(zip(chunk_results, chunks)):
        for entry in entries:
            sig = _create_entry_signature(entry)

            if sig not in seen_signatures:
                seen_signatures.add(sig)
                # Mark entries from continuation chunks
                if chunk.is_continuation:
                    entry["_from_chunk"] = chunk.chunk_index
                merged.append(entry)
            else:
                logger.debug(f"Deduplicated entry at chunk boundary: {sig}")

    logger.info(f"Merged {sum(len(r) for r in chunk_results)} entries to {len(merged)} (deduped {sum(len(r) for r in chunk_results) - len(merged)})")
    return merged


def _create_entry_signature(entry: dict) -> str:
    """Create a signature for entry matching/deduplication."""
    date = entry.get("date", "")
    visit_type = entry.get("visit_type", "")
    provider = (entry.get("provider", "") or "").lower().replace(" ", "")[:20]
    return f"{date}|{visit_type}|{provider}"
