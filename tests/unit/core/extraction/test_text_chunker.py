"""Tests for TextChunker - text splitting for large exhibits."""
import pytest
from app.core.extraction.text_chunker import (
    TextChunker,
    TextChunk,
    merge_chunk_results,
    _create_entry_signature,
)


class TestTextChunker:
    """Tests for TextChunker class."""

    def test_small_text_no_chunking(self):
        """Text under threshold returns single chunk."""
        chunker = TextChunker(max_chars=1000)
        text = "Short text that doesn't need chunking."

        assert not chunker.needs_chunking(text)
        chunks = chunker.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1
        assert chunks[0].is_continuation is False

    def test_empty_text(self):
        """Empty text returns empty list."""
        chunker = TextChunker(max_chars=1000)
        chunks = chunker.chunk_text("")
        assert chunks == []

    def test_text_at_threshold(self):
        """Text at exactly threshold stays as single chunk."""
        chunker = TextChunker(max_chars=100)
        text = "a" * 100

        assert not chunker.needs_chunking(text)
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1

    def test_text_over_threshold_splits(self):
        """Text over threshold gets split into multiple chunks."""
        chunker = TextChunker(max_chars=100, overlap_chars=10, min_chunk_chars=50)
        text = "a" * 250

        assert chunker.needs_chunking(text)
        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 2
        # First chunk should not be continuation
        assert chunks[0].is_continuation is False
        # Subsequent chunks are continuations
        for chunk in chunks[1:]:
            assert chunk.is_continuation is True

    def test_chunk_metadata_correct(self):
        """Chunk metadata (index, total, char positions) is correct."""
        chunker = TextChunker(max_chars=100, overlap_chars=10, min_chunk_chars=50)
        text = "a" * 200

        chunks = chunker.chunk_text(text)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == len(chunks)
            assert chunk.char_count == len(chunk.text)
            assert chunk.start_char >= 0
            assert chunk.end_char <= len(text)

    def test_paragraph_boundary_splitting(self):
        """Splits at paragraph boundaries when available."""
        chunker = TextChunker(max_chars=100, overlap_chars=10, min_chunk_chars=20)

        # Create text with paragraph boundary near chunk boundary
        text = "First paragraph with content.\n\nSecond paragraph starts here and continues with more text that goes beyond the limit."

        chunks = chunker.chunk_text(text)

        # Should split at the paragraph boundary
        assert len(chunks) >= 1
        # First chunk should end at or after the paragraph boundary
        if len(chunks) > 1:
            assert chunks[0].text.strip().endswith("content.") or "\n\n" in text[chunks[0].end_char - 5:chunks[0].end_char + 5]

    def test_sentence_boundary_fallback(self):
        """Falls back to sentence boundaries when no paragraphs."""
        chunker = TextChunker(max_chars=80, overlap_chars=10, min_chunk_chars=20)

        # Long text with sentences but no paragraph breaks
        text = "First sentence here. Second sentence here. Third sentence goes beyond limit and continues."

        chunks = chunker.chunk_text(text)

        # Should split at sentence boundary
        assert len(chunks) >= 1
        if len(chunks) > 1:
            # First chunk should end at a sentence boundary
            first_text = chunks[0].text.strip()
            assert first_text.endswith(".") or first_text.endswith("!") or first_text.endswith("?")

    def test_overlap_between_chunks(self):
        """Chunks have overlap for context preservation."""
        chunker = TextChunker(max_chars=100, overlap_chars=20, min_chunk_chars=30)
        text = "a" * 200

        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 2
        # Check that chunks cover the full text with overlap
        # End of chunk n should be near start of chunk n+1
        for i in range(len(chunks) - 1):
            # The overlap means the end of one chunk should be close to or past the start of the next
            gap = chunks[i + 1].start_char - chunks[i].end_char
            assert gap <= 0 or gap < chunker.overlap_chars, f"Gap too large: {gap}"

    def test_needs_chunking_threshold(self):
        """needs_chunking correctly identifies texts over threshold."""
        chunker = TextChunker(max_chars=1000)

        assert not chunker.needs_chunking("a" * 999)
        assert not chunker.needs_chunking("a" * 1000)
        assert chunker.needs_chunking("a" * 1001)


class TestMergeChunkResults:
    """Tests for merge_chunk_results function."""

    def test_single_chunk_passthrough(self):
        """Single chunk results pass through unchanged."""
        entries = [
            {"date": "2024-01-01", "visit_type": "office_visit", "provider": "Dr. Smith"}
        ]
        chunks = [TextChunk(text="test", chunk_index=0, total_chunks=1, start_char=0, end_char=4)]

        merged = merge_chunk_results([entries], chunks)
        assert merged == entries

    def test_empty_results(self):
        """Empty results return empty list."""
        merged = merge_chunk_results([], [])
        assert merged == []

    def test_deduplication_by_signature(self):
        """Duplicate entries across chunks are deduplicated."""
        entry1 = {"date": "2024-01-01", "visit_type": "office_visit", "provider": "Dr. Smith"}
        entry2 = {"date": "2024-01-01", "visit_type": "office_visit", "provider": "Dr. Smith"}  # duplicate
        entry3 = {"date": "2024-01-02", "visit_type": "lab_result", "provider": "Dr. Jones"}

        chunk_results = [[entry1], [entry2, entry3]]
        chunks = [
            TextChunk(text="a", chunk_index=0, total_chunks=2, start_char=0, end_char=1),
            TextChunk(text="b", chunk_index=1, total_chunks=2, start_char=1, end_char=2, is_continuation=True),
        ]

        merged = merge_chunk_results(chunk_results, chunks)

        assert len(merged) == 2  # entry1 and entry3, not entry2
        dates = [e["date"] for e in merged]
        assert "2024-01-01" in dates
        assert "2024-01-02" in dates

    def test_continuation_chunks_marked(self):
        """Entries from continuation chunks get _from_chunk marker."""
        entry1 = {"date": "2024-01-01", "visit_type": "office_visit", "provider": "Dr. Smith"}
        entry2 = {"date": "2024-01-02", "visit_type": "lab_result", "provider": "Dr. Jones"}

        chunk_results = [[entry1], [entry2]]
        chunks = [
            TextChunk(text="a", chunk_index=0, total_chunks=2, start_char=0, end_char=1, is_continuation=False),
            TextChunk(text="b", chunk_index=1, total_chunks=2, start_char=1, end_char=2, is_continuation=True),
        ]

        merged = merge_chunk_results(chunk_results, chunks)

        # First chunk entry should not have marker
        first_entry = next(e for e in merged if e["date"] == "2024-01-01")
        assert "_from_chunk" not in first_entry

        # Second chunk entry should have marker
        second_entry = next(e for e in merged if e["date"] == "2024-01-02")
        assert second_entry.get("_from_chunk") == 1


class TestEntrySignature:
    """Tests for _create_entry_signature helper."""

    def test_signature_format(self):
        """Signature uses date|visit_type|provider format."""
        entry = {"date": "2024-01-01", "visit_type": "office_visit", "provider": "Dr. John Smith"}
        sig = _create_entry_signature(entry)

        assert "2024-01-01" in sig
        assert "office_visit" in sig
        assert "|" in sig

    def test_signature_normalizes_provider(self):
        """Provider is lowercased and truncated."""
        entry1 = {"date": "2024-01-01", "visit_type": "office_visit", "provider": "Dr. John Smith"}
        entry2 = {"date": "2024-01-01", "visit_type": "office_visit", "provider": "dr. john smith"}

        # Both should have same signature (case insensitive)
        sig1 = _create_entry_signature(entry1)
        sig2 = _create_entry_signature(entry2)
        assert sig1 == sig2

    def test_signature_handles_missing_fields(self):
        """Signature handles missing optional fields."""
        entry = {"date": "2024-01-01"}
        sig = _create_entry_signature(entry)

        assert "2024-01-01" in sig
        assert sig.count("|") == 2  # Still has separators

    def test_signature_handles_none_provider(self):
        """Signature handles None provider."""
        entry = {"date": "2024-01-01", "visit_type": "office_visit", "provider": None}
        sig = _create_entry_signature(entry)

        # Should not raise
        assert "2024-01-01" in sig
