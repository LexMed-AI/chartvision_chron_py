"""Tests for ParallelExtractor module."""
import asyncio
import pytest
from app.core.extraction.parallel_extractor import (
    ParallelExtractor,
    ParallelExtractionResult,
    ExhibitExtractionResult,
)


class TestParallelExtractor:
    """Tests for ParallelExtractor class."""

    @pytest.mark.asyncio
    async def test_extracts_text_from_single_exhibit(self):
        """Test basic text extraction from one exhibit."""
        async def mock_text_extract(text, exhibit_id):
            return [
                {"date": "2024-01-01", "visit_type": "office_visit", "exhibit_reference": exhibit_id}
            ]

        extractor = ParallelExtractor(
            text_extract_fn=mock_text_extract,
            max_concurrent=5,
        )

        exhibits = [
            {"exhibit_id": "1F", "text": "Patient visit notes", "images": []},
        ]

        result = await extractor.extract_exhibits(exhibits)

        assert result.total_exhibits == 1
        assert result.successful_exhibits == 1
        assert len(result.all_entries) == 1
        assert result.all_entries[0]["exhibit_reference"] == "1F"

    @pytest.mark.asyncio
    async def test_extracts_from_multiple_exhibits_in_parallel(self):
        """Test parallel extraction from multiple exhibits."""
        call_order = []

        async def mock_text_extract(text, exhibit_id):
            call_order.append(exhibit_id)
            await asyncio.sleep(0.01)  # Small delay to test parallelism
            return [
                {"date": "2024-01-01", "visit_type": "office_visit", "exhibit_reference": exhibit_id}
            ]

        extractor = ParallelExtractor(
            text_extract_fn=mock_text_extract,
            max_concurrent=5,
        )

        exhibits = [
            {"exhibit_id": "1F", "text": "Text 1", "images": []},
            {"exhibit_id": "2F", "text": "Text 2", "images": []},
            {"exhibit_id": "3F", "text": "Text 3", "images": []},
        ]

        result = await extractor.extract_exhibits(exhibits)

        assert result.total_exhibits == 3
        assert result.successful_exhibits == 3
        assert len(result.all_entries) == 3

    @pytest.mark.asyncio
    async def test_runs_text_and_vision_in_parallel_within_exhibit(self):
        """Test that text and vision extraction run concurrently for same exhibit."""
        extraction_order = []

        async def mock_text_extract(text, exhibit_id):
            extraction_order.append(f"text_{exhibit_id}")
            await asyncio.sleep(0.02)
            return [{"date": "2024-01-01", "visit_type": "office_visit", "exhibit_reference": exhibit_id}]

        async def mock_vision_extract(images, exhibit_id, page_nums):
            extraction_order.append(f"vision_{exhibit_id}")
            await asyncio.sleep(0.02)
            return [{"date": "2024-01-02", "visit_type": "imaging_report", "exhibit_reference": exhibit_id}]

        extractor = ParallelExtractor(
            text_extract_fn=mock_text_extract,
            vision_extract_fn=mock_vision_extract,
            max_concurrent=5,
        )

        exhibits = [
            {"exhibit_id": "1F", "text": "Text content", "images": [b"fake_image"]},
        ]

        result = await extractor.extract_exhibits(exhibits)

        assert result.total_exhibits == 1
        assert result.successful_exhibits == 1
        # Should have both text and vision entries
        assert len(result.all_entries) == 2

        # Verify both extraction types were used
        exhibit_result = result.exhibit_results[0]
        assert exhibit_result.text_entries == 1
        assert exhibit_result.vision_entries == 1
        assert exhibit_result.used_vision is True

    @pytest.mark.asyncio
    async def test_respects_max_concurrent_limit(self):
        """Test that max_concurrent is respected."""
        concurrent_count = 0
        max_concurrent_observed = 0

        async def mock_text_extract(text, exhibit_id):
            nonlocal concurrent_count, max_concurrent_observed
            concurrent_count += 1
            max_concurrent_observed = max(max_concurrent_observed, concurrent_count)
            await asyncio.sleep(0.05)  # Longer delay to observe concurrency
            concurrent_count -= 1
            return [{"date": "2024-01-01", "visit_type": "office_visit", "exhibit_reference": exhibit_id}]

        # Set max_concurrent to 2
        extractor = ParallelExtractor(
            text_extract_fn=mock_text_extract,
            max_concurrent=2,
        )

        exhibits = [
            {"exhibit_id": f"{i}F", "text": f"Text {i}", "images": []}
            for i in range(5)
        ]

        await extractor.extract_exhibits(exhibits)

        # Should never exceed max_concurrent
        assert max_concurrent_observed <= 2

    @pytest.mark.asyncio
    async def test_handles_extraction_errors_gracefully(self):
        """Test that extraction errors don't crash the whole batch.

        Note: The parallel extractor catches errors within individual extraction tasks
        (text/vision) but continues processing. The error is logged but the exhibit
        result shows 0 entries, not a hard failure. This is by design - partial
        extraction is better than total failure.
        """
        async def mock_text_extract(text, exhibit_id):
            if exhibit_id == "2F":
                raise RuntimeError("API error")
            return [{"date": "2024-01-01", "visit_type": "office_visit", "exhibit_reference": exhibit_id}]

        extractor = ParallelExtractor(
            text_extract_fn=mock_text_extract,
            max_concurrent=5,
        )

        exhibits = [
            {"exhibit_id": "1F", "text": "Text 1", "images": []},
            {"exhibit_id": "2F", "text": "Text 2", "images": []},  # Will fail internally
            {"exhibit_id": "3F", "text": "Text 3", "images": []},
        ]

        result = await extractor.extract_exhibits(exhibits)

        assert result.total_exhibits == 3
        # All exhibits "succeeded" at the exhibit level (no exception propagated)
        # but 2F has 0 entries due to internal extraction failure
        assert len(result.all_entries) == 2

        # Check that 2F has no entries (extraction failed internally)
        exhibit_2f = next(r for r in result.exhibit_results if r.exhibit_id == "2F")
        assert len(exhibit_2f.entries) == 0
        assert exhibit_2f.text_entries == 0

    @pytest.mark.asyncio
    async def test_applies_recovery_handler(self):
        """Test that recovery handler is called for sparse entries."""
        async def mock_text_extract(text, exhibit_id):
            return [{"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}}]

        async def mock_recovery(entries, images, exhibit_id, page_nums):
            # Simulate enriching sparse entries
            for entry in entries:
                entry["occurrence_treatment"] = {"chief_complaint": "Recovered content"}
            return entries

        extractor = ParallelExtractor(
            text_extract_fn=mock_text_extract,
            max_concurrent=5,
            recovery_fn=mock_recovery,
        )

        exhibits = [
            {"exhibit_id": "1F", "text": "Text", "images": [b"image"]},
        ]

        result = await extractor.extract_exhibits(exhibits)

        assert len(result.all_entries) == 1
        assert result.all_entries[0]["occurrence_treatment"]["chief_complaint"] == "Recovered content"

    @pytest.mark.asyncio
    async def test_empty_exhibits_returns_empty_result(self):
        """Test that empty exhibits list returns empty result."""
        async def mock_text_extract(text, exhibit_id):
            raise AssertionError("Should not be called")

        extractor = ParallelExtractor(
            text_extract_fn=mock_text_extract,
            max_concurrent=5,
        )

        result = await extractor.extract_exhibits([])

        assert result.total_exhibits == 0
        assert result.successful_exhibits == 0
        assert len(result.all_entries) == 0

    @pytest.mark.asyncio
    async def test_extract_single_convenience_method(self):
        """Test the extract_single convenience method."""
        async def mock_text_extract(text, exhibit_id):
            return [{"date": "2024-01-01", "visit_type": "office_visit", "exhibit_reference": exhibit_id}]

        extractor = ParallelExtractor(
            text_extract_fn=mock_text_extract,
            max_concurrent=5,
        )

        entries = await extractor.extract_single(
            text="Patient visit notes",
            exhibit_id="1F",
        )

        assert len(entries) == 1
        assert entries[0]["exhibit_reference"] == "1F"

    @pytest.mark.asyncio
    async def test_derives_page_nums_from_page_range(self):
        """Test that page numbers are derived from page_range if scanned_page_nums not provided."""
        received_page_nums = None

        async def mock_vision_extract(images, exhibit_id, page_nums):
            nonlocal received_page_nums
            received_page_nums = page_nums
            return []

        extractor = ParallelExtractor(
            text_extract_fn=lambda t, e: [],
            vision_extract_fn=mock_vision_extract,
            max_concurrent=5,
        )

        exhibits = [
            {"exhibit_id": "1F", "text": "", "images": [b"img"], "page_range": (10, 15)},
        ]

        await extractor.extract_exhibits(exhibits)

        assert received_page_nums == [10, 11, 12, 13, 14, 15]
