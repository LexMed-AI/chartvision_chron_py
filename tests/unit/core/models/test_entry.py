"""Tests for entry.py models - medical chronology data structures."""

from datetime import datetime

import pytest

from app.core.models.entry import (
    AnalysisLevel,
    ChronologyConfig,
    ChronologyEvent,
    ConsolidatedData,
    DiagnosisInfo,
    DiagnosisType,
    MedicalEvent,
    MedicalTimeline,
    ProcessingMode,
    UnifiedChronologyResult,
)


class TestMedicalEvent:
    """Test MedicalEvent dataclass."""

    def test_create_minimal_event(self):
        """Test creating event with required fields only."""
        event = MedicalEvent(
            event_type="office_visit",
            date=datetime(2023, 1, 15),
            provider="Dr. Smith",
            description="Annual checkup",
        )
        assert event.event_type == "office_visit"
        assert event.provider == "Dr. Smith"
        assert event.confidence == 1.0  # default

    def test_create_full_event(self):
        """Test creating event with all fields."""
        event = MedicalEvent(
            event_type="procedure",
            date=datetime(2023, 6, 10),
            provider="Dr. Jones",
            description="MRI of lumbar spine",
            diagnosis="Herniated disc L4-L5",
            procedure="Lumbar MRI",
            medications=["Ibuprofen", "Flexeril"],
            severity="moderate",
            location="Regional Hospital",
            confidence=0.95,
            source_page=45,
            follow_up_required=True,
            critical_finding=True,
            exhibit_reference="1F",
        )
        assert event.diagnosis == "Herniated disc L4-L5"
        assert len(event.medications) == 2
        assert event.critical_finding is True

    def test_default_values(self):
        """Test default values are set correctly."""
        event = MedicalEvent(
            event_type="test",
            date=datetime(2023, 1, 1),
            provider="Test",
            description="Test",
        )
        assert event.diagnosis is None
        assert event.medications == []
        assert event.follow_up_required is False
        assert event.metadata == {}


class TestDiagnosisType:
    """Test DiagnosisType enum."""

    def test_enum_values(self):
        """Test all enum values exist."""
        assert DiagnosisType.PRIMARY.value == "primary"
        assert DiagnosisType.SECONDARY.value == "secondary"
        assert DiagnosisType.RULED_OUT.value == "ruled_out"

    def test_enum_comparison(self):
        """Test enum comparison works."""
        assert DiagnosisType.PRIMARY == DiagnosisType.PRIMARY
        assert DiagnosisType.PRIMARY != DiagnosisType.SECONDARY


class TestProcessingMode:
    """Test ProcessingMode enum."""

    def test_enum_values(self):
        """Test all processing modes exist."""
        assert ProcessingMode.SYNC.value == "sync"
        assert ProcessingMode.ASYNC.value == "async"
        assert ProcessingMode.BATCH.value == "batch"


class TestAnalysisLevel:
    """Test AnalysisLevel enum."""

    def test_enum_values(self):
        """Test all analysis levels exist."""
        assert AnalysisLevel.BASIC.value == "basic"
        assert AnalysisLevel.STANDARD.value == "standard"
        assert AnalysisLevel.COMPREHENSIVE.value == "comprehensive"


class TestDiagnosisInfo:
    """Test DiagnosisInfo dataclass."""

    def test_create_diagnosis(self):
        """Test creating diagnosis info."""
        diagnosis = DiagnosisInfo(
            diagnosis="Type 2 Diabetes",
            icd_code="E11.9",
            diagnosis_type=DiagnosisType.PRIMARY,
            first_diagnosed=datetime(2020, 3, 15),
            provider="Dr. Smith",
        )
        assert diagnosis.diagnosis == "Type 2 Diabetes"
        assert diagnosis.icd_code == "E11.9"
        assert diagnosis.status == "active"  # default

    def test_diagnosis_with_treatments(self):
        """Test diagnosis with treatments and medications."""
        diagnosis = DiagnosisInfo(
            diagnosis="Hypertension",
            treatments=["Lifestyle modification", "Medication"],
            medications=["Lisinopril", "HCTZ"],
        )
        assert len(diagnosis.treatments) == 2
        assert "Lisinopril" in diagnosis.medications


class TestMedicalTimeline:
    """Test MedicalTimeline dataclass."""

    def test_empty_timeline(self):
        """Test creating empty timeline."""
        timeline = MedicalTimeline()
        assert timeline.events == []
        assert timeline.diagnoses == {}
        assert timeline.total_events == 0

    def test_timeline_with_events(self):
        """Test timeline with events added."""
        event = MedicalEvent(
            event_type="visit",
            date=datetime(2023, 1, 1),
            provider="Dr. Test",
            description="Test visit",
        )
        timeline = MedicalTimeline(
            events=[event],
            total_events=1,
            providers=["Dr. Test"],
        )
        assert len(timeline.events) == 1
        assert timeline.total_events == 1


class TestChronologyEvent:
    """Test ChronologyEvent dataclass."""

    def test_create_event(self):
        """Test creating chronology event."""
        event = ChronologyEvent(
            event_id="evt-001",
            event_type="medical",
            date=datetime(2023, 5, 20),
            title="Office Visit",
            description="Follow-up appointment",
            source_exhibit="2F",
            source_pages=[10, 11],
        )
        assert event.event_id == "evt-001"
        assert event.source_exhibit == "2F"
        assert 10 in event.source_pages

    def test_event_with_related(self):
        """Test event with related events."""
        event = ChronologyEvent(
            event_id="evt-002",
            event_type="procedural",
            date=datetime(2023, 6, 1),
            related_events=["evt-001", "evt-003"],
        )
        assert len(event.related_events) == 2


class TestChronologyConfig:
    """Test ChronologyConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ChronologyConfig()
        assert config.processing_mode == ProcessingMode.SYNC
        assert config.analysis_level == AnalysisLevel.STANDARD
        assert config.use_haiku is True
        assert config.max_concurrent_workers == 5

    def test_custom_config(self):
        """Test custom configuration."""
        config = ChronologyConfig(
            processing_mode=ProcessingMode.ASYNC,
            analysis_level=AnalysisLevel.COMPREHENSIVE,
            max_concurrent_workers=10,
            timeout_seconds=300,
        )
        assert config.processing_mode == ProcessingMode.ASYNC
        assert config.max_concurrent_workers == 10


class TestConsolidatedData:
    """Test ConsolidatedData dataclass."""

    def test_empty_consolidated_data(self):
        """Test creating empty consolidated data."""
        data = ConsolidatedData()
        assert data.patient_name == "Unknown Patient"
        assert data.all_diagnoses == []
        assert data.data_completeness == 0.0

    def test_consolidated_with_data(self):
        """Test consolidated data with medical info."""
        data = ConsolidatedData(
            patient_name="John Doe",
            case_id="SSA-12345",
            all_diagnoses=[{"diagnosis": "Diabetes"}],
            all_medications=["Metformin"],
            processed_exhibits=5,
            total_exhibits=10,
        )
        assert data.patient_name == "John Doe"
        assert len(data.all_diagnoses) == 1
        assert data.processed_exhibits == 5


class TestUnifiedChronologyResult:
    """Test UnifiedChronologyResult dataclass."""

    def test_successful_result(self):
        """Test creating successful result."""
        timeline = MedicalTimeline()
        result = UnifiedChronologyResult(
            success=True,
            processing_time=45.5,
            processing_mode=ProcessingMode.SYNC,
            analysis_level=AnalysisLevel.STANDARD,
            timeline=timeline,
            events=[],
            providers=[],
            diagnoses=[],
            treatment_gaps=[],
        )
        assert result.success is True
        assert result.processing_time == 45.5
        assert result.error_message is None

    def test_failed_result(self):
        """Test creating failed result."""
        timeline = MedicalTimeline()
        result = UnifiedChronologyResult(
            success=False,
            processing_time=5.0,
            processing_mode=ProcessingMode.SYNC,
            analysis_level=AnalysisLevel.BASIC,
            timeline=timeline,
            events=[],
            providers=[],
            diagnoses=[],
            treatment_gaps=[],
            error_message="PDF parsing failed",
            warnings=["Missing pages 10-15"],
        )
        assert result.success is False
        assert result.error_message == "PDF parsing failed"
        assert len(result.warnings) == 1
