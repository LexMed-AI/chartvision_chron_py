"""Tests for ChunkMergeRetryHandler module."""
import pytest
from app.core.extraction.chunk_retry_handler import ChunkMergeRetryHandler


class TestChunkMergeRetryHandler:
    """Tests for ChunkMergeRetryHandler class."""

    @pytest.mark.asyncio
    async def test_no_retry_when_all_entries_complete(self):
        """Test that no retry happens when all entries have content."""
        async def mock_extract(text, exhibit_id):
            raise AssertionError("Should not be called")

        handler = ChunkMergeRetryHandler(mock_extract)
        entries = [
            {
                "date": "2024-01-01",
                "visit_type": "office_visit",
                "occurrence_treatment": {"chief_complaint": "Severe back pain with radiation"},
            },
        ]

        result = await handler.retry_with_merged_chunks(
            entries, "text", "adjacent", "1F"
        )

        assert len(result) == 1
        assert result[0]["occurrence_treatment"]["chief_complaint"] == "Severe back pain with radiation"

    @pytest.mark.asyncio
    async def test_retry_fills_sparse_entries(self):
        """Test that sparse entries get filled via chunk merge retry."""
        async def mock_extract(text, exhibit_id):
            # Verify merged text is passed
            assert "--- CONTINUATION ---" in text
            return [
                {
                    "date": "2024-01-01",
                    "visit_type": "office_visit",
                    "occurrence_treatment": {"chief_complaint": "Severe back pain with leg radiation"},
                }
            ]

        handler = ChunkMergeRetryHandler(mock_extract)
        entries = [
            {
                "date": "2024-01-01",
                "visit_type": "office_visit",
                "occurrence_treatment": {},  # Sparse
            },
        ]

        result = await handler.retry_with_merged_chunks(
            entries, "original text", "adjacent text", "1F"
        )

        assert len(result) == 1
        assert "back pain" in result[0]["occurrence_treatment"]["chief_complaint"]

    @pytest.mark.asyncio
    async def test_no_retry_without_adjacent_text(self):
        """Test that no retry happens without adjacent text."""
        async def mock_extract(text, exhibit_id):
            raise AssertionError("Should not be called")

        handler = ChunkMergeRetryHandler(mock_extract)
        entries = [
            {
                "date": "2024-01-01",
                "visit_type": "office_visit",
                "occurrence_treatment": {},  # Sparse but no adjacent text
            },
        ]

        result = await handler.retry_with_merged_chunks(
            entries, "text", None, "1F"  # No adjacent text
        )

        assert len(result) == 1
        assert result[0]["occurrence_treatment"] == {}

    @pytest.mark.asyncio
    async def test_adds_new_entries_from_merged_context(self):
        """Test that new entries discovered in merged context are added."""
        async def mock_extract(text, exhibit_id):
            return [
                {
                    "date": "2024-01-02",  # Different date - new entry
                    "visit_type": "imaging_report",
                    "occurrence_treatment": {"findings": "MRI shows disc herniation at L4-L5 level"},
                }
            ]

        handler = ChunkMergeRetryHandler(mock_extract)
        entries = [
            {
                "date": "2024-01-01",
                "visit_type": "office_visit",
                "occurrence_treatment": {},  # Sparse
            },
        ]

        result = await handler.retry_with_merged_chunks(
            entries, "text", "adjacent", "1F"
        )

        # Original entry + new entry from merged context
        assert len(result) == 2
        dates = {e["date"] for e in result}
        assert "2024-01-01" in dates
        assert "2024-01-02" in dates

    @pytest.mark.asyncio
    async def test_adds_raw_text_preview_to_unfilled_sparse(self):
        """Test that unfilled sparse entries get raw_text_preview."""
        async def mock_extract(text, exhibit_id):
            # Return empty - can't fill the sparse entry
            return []

        handler = ChunkMergeRetryHandler(mock_extract)
        entries = [
            {
                "date": "2024-01-01",
                "visit_type": "office_visit",
                "occurrence_treatment": {},
            },
        ]

        result = await handler.retry_with_merged_chunks(
            entries, "text", "adjacent", "1F", raw_text_preview="First 500 chars..."
        )

        assert len(result) == 1
        assert result[0]["raw_text_preview"] == "First 500 chars..."

    @pytest.mark.asyncio
    async def test_handles_extraction_error_gracefully(self):
        """Test that extraction errors don't crash the handler."""
        async def mock_extract(text, exhibit_id):
            raise RuntimeError("API error")

        handler = ChunkMergeRetryHandler(mock_extract)
        entries = [
            {
                "date": "2024-01-01",
                "visit_type": "office_visit",
                "occurrence_treatment": {},
            },
        ]

        result = await handler.retry_with_merged_chunks(
            entries, "text", "adjacent", "1F"
        )

        # Should return original sparse entry without crashing
        assert len(result) == 1
        assert result[0]["occurrence_treatment"] == {}

    def test_is_empty_occurrence_checks(self):
        """Test empty occurrence detection."""
        handler = ChunkMergeRetryHandler(lambda x, y: [])

        # Empty dict
        assert handler._is_empty_occurrence({}) is True

        # None values only
        assert handler._is_empty_occurrence({"chief_complaint": None}) is True

        # Empty string only
        assert handler._is_empty_occurrence({"chief_complaint": ""}) is True

        # Empty list only
        assert handler._is_empty_occurrence({"assessment_diagnoses": []}) is True

        # Metadata fields only don't count
        assert handler._is_empty_occurrence({"visit_type": "office_visit"}) is True

        # Has actual content
        assert handler._is_empty_occurrence({"chief_complaint": "Back pain"}) is False

        # Has list content
        assert handler._is_empty_occurrence({"assessment_diagnoses": ["Lumbar strain"]}) is False

    def test_reset_clears_retry_flag(self):
        """Test that reset clears the retry attempted flag."""
        handler = ChunkMergeRetryHandler(lambda x, y: [])
        handler._retry_attempted = True
        handler.reset()
        assert handler._retry_attempted is False
