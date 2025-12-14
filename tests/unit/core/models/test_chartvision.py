"""Tests for chartvision.py models - ChartVision report data structures."""

from datetime import datetime

import pytest

from app.core.models.chartvision import (
    AdministrativeData,
    AllegedImpairment,
    ChartVisionReportData,
    ChronologyEntry,
    ClaimantData,
    DiagnosticTest,
    FunctionalLimitation,
    MedicallyDeterminableImpairment,
    MedicalSourceOpinion,
    Medication,
    OccupationalHistory,
    SurgicalProcedure,
)


class TestClaimantData:
    """Test ClaimantData dataclass."""

    def test_create_claimant(self):
        """Test creating claimant with required fields."""
        claimant = ClaimantData(
            full_name="John Doe",
            date_of_birth=datetime(1970, 5, 15),
            case_file_reference="SSA-2023-12345",
            total_document_pages=500,
        )
        assert claimant.full_name == "John Doe"
        assert claimant.total_document_pages == 500
        assert claimant.ssn is None  # optional

    def test_claimant_with_optional_fields(self):
        """Test claimant with SSN and BNC code."""
        claimant = ClaimantData(
            full_name="Jane Smith",
            date_of_birth=datetime(1985, 8, 20),
            case_file_reference="SSA-2023-67890",
            total_document_pages=350,
            ssn="XXX-XX-1234",
            bnc_code="ABC123",
        )
        assert claimant.ssn == "XXX-XX-1234"
        assert claimant.bnc_code == "ABC123"


class TestAdministrativeData:
    """Test AdministrativeData dataclass."""

    def test_create_admin_data(self):
        """Test creating administrative data."""
        admin = AdministrativeData(
            claim_type="DIB",
            protective_filing_date=datetime(2022, 1, 15),
            alleged_onset_date=datetime(2021, 6, 1),
        )
        assert admin.claim_type == "DIB"
        assert admin.protective_filing_date == datetime(2022, 1, 15)

    def test_admin_all_dates(self):
        """Test administrative data with all dates."""
        admin = AdministrativeData(
            claim_type="Concurrent",
            protective_filing_date=datetime(2022, 1, 15),
            alleged_onset_date=datetime(2021, 6, 1),
            date_last_insured=datetime(2025, 12, 31),
            initial_denial_date=datetime(2022, 4, 1),
            reconsideration_denial_date=datetime(2022, 8, 15),
            alj_hearing_date=datetime(2023, 2, 10),
        )
        assert admin.claim_type == "Concurrent"
        assert admin.alj_hearing_date == datetime(2023, 2, 10)


class TestAllegedImpairment:
    """Test AllegedImpairment dataclass."""

    def test_create_impairment(self):
        """Test creating alleged impairment."""
        impairment = AllegedImpairment(
            condition_name="Chronic back pain",
            source="3E@15",
        )
        assert impairment.condition_name == "Chronic back pain"
        assert impairment.source == "3E@15"


class TestMedicallyDeterminableImpairment:
    """Test MedicallyDeterminableImpairment dataclass."""

    def test_create_mdi(self):
        """Test creating MDI."""
        mdi = MedicallyDeterminableImpairment(
            diagnosis="Degenerative disc disease",
            icd_code="M51.16",
            severity="Severe",
            first_documented=datetime(2020, 3, 10),
            source="1F@25",
        )
        assert mdi.diagnosis == "Degenerative disc disease"
        assert mdi.icd_code == "M51.16"
        assert mdi.severity == "Severe"

    def test_mdi_minimal(self):
        """Test MDI with minimal fields."""
        mdi = MedicallyDeterminableImpairment(diagnosis="Anxiety disorder")
        assert mdi.diagnosis == "Anxiety disorder"
        assert mdi.icd_code is None


class TestMedicalSourceOpinion:
    """Test MedicalSourceOpinion dataclass."""

    def test_create_opinion(self):
        """Test creating medical source opinion."""
        opinion = MedicalSourceOpinion(
            date=datetime(2023, 5, 20),
            medical_source="Dr. Johnson",
            relationship="Treating",
            opinion_type="RFC",
            source="4F@1-5",
        )
        assert opinion.medical_source == "Dr. Johnson"
        assert opinion.relationship == "Treating"
        assert opinion.opinion_type == "RFC"


class TestSurgicalProcedure:
    """Test SurgicalProcedure dataclass."""

    def test_create_procedure(self):
        """Test creating surgical procedure."""
        procedure = SurgicalProcedure(
            date=datetime(2022, 9, 15),
            procedure="Lumbar laminectomy L4-L5",
            facility_type="Hospital",
            source="5F@100-120",
        )
        assert procedure.procedure == "Lumbar laminectomy L4-L5"
        assert procedure.facility_type == "Hospital"


class TestDiagnosticTest:
    """Test DiagnosticTest dataclass."""

    def test_create_test(self):
        """Test creating diagnostic test."""
        test = DiagnosticTest(
            date=datetime(2023, 1, 10),
            test_name="MRI Lumbar Spine",
            category="Imaging",
            results_summary="Disc herniation at L4-L5",
            source="2F@45",
        )
        assert test.test_name == "MRI Lumbar Spine"
        assert test.category == "Imaging"

    def test_test_minimal(self):
        """Test diagnostic test with minimal fields."""
        test = DiagnosticTest(
            date=datetime(2023, 2, 1),
            test_name="CBC",
        )
        assert test.test_name == "CBC"
        assert test.results_summary == ""


class TestMedication:
    """Test Medication dataclass."""

    def test_create_medication(self):
        """Test creating medication entry."""
        med = Medication(
            medication="Gabapentin",
            dosage="300mg",
            frequency="TID",
            indication="Neuropathic pain",
            source="1F@30",
        )
        assert med.medication == "Gabapentin"
        assert med.dosage == "300mg"
        assert med.frequency == "TID"

    def test_medication_minimal(self):
        """Test medication with just name."""
        med = Medication(medication="Ibuprofen")
        assert med.medication == "Ibuprofen"
        assert med.dosage is None


class TestOccupationalHistory:
    """Test OccupationalHistory dataclass."""

    def test_create_job(self):
        """Test creating job history entry."""
        job = OccupationalHistory(
            position_title="Construction Worker",
            employment_period="03/2010 - 06/2021",
            exertional_level="Heavy",
            source="3E@5",
        )
        assert job.position_title == "Construction Worker"
        assert job.exertional_level == "Heavy"


class TestFunctionalLimitation:
    """Test FunctionalLimitation dataclass."""

    def test_create_limitation(self):
        """Test creating functional limitation."""
        limitation = FunctionalLimitation(
            activity_domain="Lifting",
            reported_limitation="Cannot lift more than 10 pounds",
            specific_examples="Cannot carry groceries",
            source="3E@10",
        )
        assert limitation.activity_domain == "Lifting"
        assert "10 pounds" in limitation.reported_limitation


class TestChronologyEntry:
    """Test ChronologyEntry dataclass."""

    def test_create_entry(self):
        """Test creating chronology entry."""
        entry = ChronologyEntry(
            date=datetime(2023, 3, 15),
            provider_specialty="Orthopedic Surgery",
            facility="Regional Medical Center",
            occurrence_treatment="Follow-up for lumbar fusion",
            source="6F@50",
            page_number=50,
        )
        assert entry.provider_specialty == "Orthopedic Surgery"
        assert entry.page_number == 50

    def test_entry_without_page(self):
        """Test entry without page number."""
        entry = ChronologyEntry(
            date=datetime(2023, 4, 1),
            provider_specialty="Primary Care",
            facility="Family Practice Clinic",
            occurrence_treatment="Annual physical",
            source="7F",
        )
        assert entry.page_number is None


class TestChartVisionReportData:
    """Test ChartVisionReportData dataclass."""

    def test_create_empty_report(self):
        """Test creating report with required fields only."""
        claimant = ClaimantData(
            full_name="Test Patient",
            date_of_birth=datetime(1980, 1, 1),
            case_file_reference="TEST-001",
            total_document_pages=100,
        )
        admin = AdministrativeData(claim_type="DIB")

        report = ChartVisionReportData(
            claimant=claimant,
            administrative=admin,
        )
        assert report.claimant.full_name == "Test Patient"
        assert report.alleged_impairments == []
        assert report.schema_version == "2.0.0"

    def test_create_full_report(self):
        """Test creating report with all sections populated."""
        claimant = ClaimantData(
            full_name="John Doe",
            date_of_birth=datetime(1970, 5, 15),
            case_file_reference="SSA-2023-12345",
            total_document_pages=500,
        )
        admin = AdministrativeData(
            claim_type="DIB",
            alleged_onset_date=datetime(2021, 6, 1),
        )

        report = ChartVisionReportData(
            claimant=claimant,
            administrative=admin,
            alleged_impairments=[
                AllegedImpairment("Back pain", "3E@5"),
            ],
            mdis=[
                MedicallyDeterminableImpairment("DDD", "M51.16"),
            ],
            medications=[
                Medication("Gabapentin"),
            ],
            chronology_entries=[
                ChronologyEntry(
                    date=datetime(2023, 1, 1),
                    provider_specialty="Ortho",
                    facility="Hospital",
                    occurrence_treatment="Visit",
                    source="1F@10",
                ),
            ],
        )
        assert len(report.alleged_impairments) == 1
        assert len(report.mdis) == 1
        assert len(report.chronology_entries) == 1

    def test_to_dict(self):
        """Test serialization to dictionary."""
        claimant = ClaimantData(
            full_name="Test",
            date_of_birth=datetime(1980, 1, 1),
            case_file_reference="TEST",
            total_document_pages=10,
        )
        admin = AdministrativeData(claim_type="SSI")
        report = ChartVisionReportData(claimant=claimant, administrative=admin)

        data = report.to_dict()
        assert isinstance(data, dict)
        assert data["claimant"]["full_name"] == "Test"
        assert data["administrative"]["claim_type"] == "SSI"
