"""Tests for RecoveryHandler module."""
import pytest
from app.core.extraction.recovery_handler import (
    is_sparse_entry,
    find_sparse_entries,
    merge_entry_with_vision,
    deduplicate_entries,
    RecoveryHandler,
)


class TestIsSparseEntry:
    """Tests for is_sparse_entry function."""

    def test_empty_occurrence_is_sparse(self):
        entry = {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}}
        assert is_sparse_entry(entry) is True

    def test_none_occurrence_is_sparse(self):
        entry = {"date": "2024-01-01", "visit_type": "office_visit"}
        assert is_sparse_entry(entry) is True

    def test_occurrence_with_content_not_sparse(self):
        entry = {
            "date": "2024-01-01",
            "visit_type": "office_visit",
            "occurrence_treatment": {
                "chief_complaint": "Back pain",
                "assessment_diagnoses": ["Lumbar strain"],
            }
        }
        assert is_sparse_entry(entry) is False

    def test_occurrence_with_only_empty_values_is_sparse(self):
        entry = {
            "date": "2024-01-01",
            "visit_type": "office_visit",
            "occurrence_treatment": {
                "chief_complaint": "",
                "assessment_diagnoses": [],
            }
        }
        assert is_sparse_entry(entry) is True

    def test_occurrence_with_visit_type_only_is_sparse(self):
        """Metadata fields like visit_type don't count as content."""
        entry = {
            "date": "2024-01-01",
            "visit_type": "office_visit",
            "occurrence_treatment": {
                "visit_type": "office_visit",
            }
        }
        assert is_sparse_entry(entry) is True


class TestFindSparseEntries:
    """Tests for find_sparse_entries function."""

    def test_finds_sparse_entries(self):
        # Note: preprocessing requires content > 10 chars to be considered non-sparse
        entries = [
            {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}},
            {"date": "2024-01-02", "visit_type": "office_visit", "occurrence_treatment": {"chief_complaint": "Severe back pain radiating to left leg"}},
            {"date": "2024-01-03", "visit_type": "office_visit", "occurrence_treatment": {}},
        ]
        sparse = find_sparse_entries(entries)
        assert len(sparse) == 2
        assert sparse[0]["date"] == "2024-01-01"
        assert sparse[1]["date"] == "2024-01-03"

    def test_no_sparse_entries(self):
        entries = [
            {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {"chief_complaint": "Severe back pain radiating to left leg"}},
        ]
        sparse = find_sparse_entries(entries)
        assert len(sparse) == 0


class TestMergeEntryWithVision:
    """Tests for merge_entry_with_vision function."""

    def test_merges_vision_content(self):
        sparse = {"date": "2024-01-01", "visit_type": "office_visit", "provider": "Dr. Smith", "occurrence_treatment": {}}
        vision = {
            "date": "2024-01-01",
            "visit_type": "office_visit",
            "occurrence_treatment": {"chief_complaint": "Back pain", "plan_of_care": "Physical therapy"}
        }
        merged = merge_entry_with_vision(sparse, vision)

        assert merged["provider"] == "Dr. Smith"  # Preserved from sparse
        assert merged["occurrence_treatment"]["chief_complaint"] == "Back pain"
        assert merged.get("_enriched_via_vision") is True

    def test_keeps_sparse_if_vision_also_sparse(self):
        sparse = {"date": "2024-01-01", "visit_type": "office_visit", "provider": "Dr. Smith", "occurrence_treatment": {}}
        vision = {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}}
        merged = merge_entry_with_vision(sparse, vision)

        assert merged["occurrence_treatment"] == {}
        assert "_enriched_via_vision" not in merged


class TestDeduplicateEntries:
    """Tests for deduplicate_entries function."""

    def test_removes_duplicates_keeping_rich(self):
        entries = [
            {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}},
            {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {"chief_complaint": "Severe back pain radiating down left leg"}},
        ]
        deduped = deduplicate_entries(entries)
        assert len(deduped) == 1
        assert "back pain" in deduped[0]["occurrence_treatment"]["chief_complaint"]

    def test_keeps_unique_entries(self):
        entries = [
            {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}},
            {"date": "2024-01-02", "visit_type": "imaging_report", "occurrence_treatment": {}},
        ]
        deduped = deduplicate_entries(entries)
        assert len(deduped) == 2


class TestRecoveryHandler:
    """Tests for RecoveryHandler class."""

    @pytest.mark.asyncio
    async def test_recover_sparse_entries(self):
        """Test that sparse entries get enriched via vision."""
        async def mock_vision_extract(images, exhibit_id, page_nums):
            return [
                {
                    "date": "2024-01-01",
                    "visit_type": "office_visit",
                    "occurrence_treatment": {"chief_complaint": "Severe back pain with radiation to left leg"},
                }
            ]

        handler = RecoveryHandler(mock_vision_extract)
        entries = [
            {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}},
        ]

        result = await handler.recover_sparse_entries(
            entries, [b"fake_image"], "1F", [1]
        )

        assert len(result) == 1
        assert "back pain" in result[0]["occurrence_treatment"]["chief_complaint"]

    @pytest.mark.asyncio
    async def test_adds_new_entries_from_vision(self):
        """Test that new entries discovered by vision are added."""
        async def mock_vision_extract(images, exhibit_id, page_nums):
            return [
                {
                    "date": "2024-01-02",  # Different date - new entry
                    "visit_type": "imaging_report",
                    "occurrence_treatment": {"findings": "MRI shows disc herniation at L4-L5 with nerve impingement"},
                }
            ]

        handler = RecoveryHandler(mock_vision_extract)
        entries = [
            {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}},
        ]

        result = await handler.recover_sparse_entries(
            entries, [b"fake_image"], "1F", [1]
        )

        assert len(result) == 2  # Original + new from vision

    @pytest.mark.asyncio
    async def test_no_recovery_without_images(self):
        """Test that no recovery happens without images."""
        async def mock_vision_extract(images, exhibit_id, page_nums):
            raise AssertionError("Should not be called")

        handler = RecoveryHandler(mock_vision_extract)
        entries = [
            {"date": "2024-01-01", "visit_type": "office_visit", "occurrence_treatment": {}},
        ]

        result = await handler.recover_sparse_entries(
            entries, [], "1F", [1]  # Empty images
        )

        assert len(result) == 1
        assert result[0]["occurrence_treatment"] == {}
