"""Tests for Citation integration with Entry models."""

from datetime import datetime

import pytest

from app.core.models.entry import MedicalEvent, ChronologyEvent
from app.core.models.citation import Citation


class TestMedicalEventCitation:
    """Test MedicalEvent with Citation field."""

    def test_medical_event_with_citation(self):
        """MedicalEvent accepts Citation object."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
        )

        event = MedicalEvent(
            event_type="office_visit",
            date=datetime(2019, 3, 15),
            provider="Dr. Smith",
            description="Patient examined",
            citation=citation,
        )

        assert event.citation is not None
        assert event.citation.exhibit_id == "25F"
        assert event.citation.format() == "25F@33 (p.1847)"

    def test_medical_event_without_citation(self):
        """MedicalEvent works without citation."""
        event = MedicalEvent(
            event_type="office_visit",
            date=datetime(2019, 3, 15),
            provider="Dr. Smith",
            description="Patient examined",
        )

        assert event.citation is None

    def test_medical_event_citation_with_range(self):
        """MedicalEvent accepts Citation with page range."""
        citation = Citation(
            exhibit_id="10F",
            relative_page=5,
            absolute_page=500,
            end_relative_page=8,
            end_absolute_page=503,
        )

        event = MedicalEvent(
            event_type="hospitalization",
            date=datetime(2020, 6, 1),
            provider="Regional Hospital",
            description="Inpatient stay",
            citation=citation,
        )

        assert event.citation is not None
        assert event.citation.format() == "10F@5-8 (pp.500-503)"


class TestChronologyEventCitation:
    """Test ChronologyEvent with Citation field."""

    def test_chronology_event_with_citation(self):
        """ChronologyEvent accepts Citation object."""
        citation = Citation(
            exhibit_id="3F",
            relative_page=12,
            absolute_page=245,
        )

        event = ChronologyEvent(
            event_id="evt-001",
            event_type="medical",
            date=datetime(2021, 8, 20),
            title="Follow-up Visit",
            description="Post-surgery follow-up",
            source_exhibit="3F",
            source_pages=[12],
            citation=citation,
        )

        assert event.citation is not None
        assert event.citation.exhibit_id == "3F"
        assert event.citation.absolute_page == 245

    def test_chronology_event_without_citation(self):
        """ChronologyEvent works without citation."""
        event = ChronologyEvent(
            event_id="evt-002",
            event_type="procedural",
            date=datetime(2021, 9, 5),
            title="Lab Results",
            description="Blood work",
        )

        assert event.citation is None

    def test_chronology_event_citation_with_bates(self):
        """ChronologyEvent with Bates-style citation."""
        citation = Citation(
            absolute_page=150,
            bates_number="ABC000150",
            source_type="bates",
        )

        event = ChronologyEvent(
            event_id="evt-003",
            event_type="medical",
            date=datetime(2022, 1, 10),
            title="Medical Record",
            description="Primary care notes",
            citation=citation,
        )

        assert event.citation is not None
        assert event.citation.format() == "ABC000150"
