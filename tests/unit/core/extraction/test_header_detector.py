"""Tests for HeaderDetector multi-format detection."""
import pytest
from app.core.extraction.header_detector import HeaderDetector, HeaderDetectionResult
from app.core.extraction.pdf_exhibit_extractor import PageText


class TestHeaderDetectorERE:
    """Test ERE format header detection."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    def test_ere_header_bar_format(self, detector, exhibit_context):
        """Detect ERE blue bar header: '25F - 33 of 74'."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="25F - 33 of 74    Medical Evidence of Record - MER    Little Rock Surgery",
        )
        result = detector.detect(page, exhibit_context)

        assert result.source_type == "ere"
        assert result.exhibit_id == "25F"
        assert result.relative_page == 33
        assert result.total_pages == 74
        assert result.confidence >= 0.9
        assert result.detection_method == "regex"

    def test_ere_stamp_format(self, detector, exhibit_context):
        """Detect ERE stamp format: 'EXHIBIT NO. 25F / PAGE: 33 OF 74'."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Some content\nEXHIBIT NO. 25F\nPAGE: 33 OF 74\nMore content",
        )
        result = detector.detect(page, exhibit_context)

        assert result.source_type == "ere"
        assert result.exhibit_id == "25F"
        assert result.relative_page == 33
        assert result.confidence >= 0.85

    def test_ere_header_with_dash_variants(self, detector, exhibit_context):
        """Handle different dash types in headers."""
        # En-dash variant
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="25F \u2013 33 of 74    Medical Evidence",  # En-dash
        )
        result = detector.detect(page, exhibit_context)
        assert result.relative_page == 33


class TestHeaderDetectorFallback:
    """Test fallback detection strategies."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    def test_position_inference_fallback(self, detector, exhibit_context):
        """Infer page from position when no header detected."""
        page = PageText(
            absolute_page=1847,
            relative_page=0,  # Unknown
            exhibit_id="25F",
            text="Patient presented with symptoms...",  # No header
        )
        result = detector.detect(page, exhibit_context)

        # Should infer: 1847 - 1815 + 1 = 33
        assert result.relative_page == 33
        assert result.is_estimated is True
        assert result.confidence < 0.7
        assert result.detection_method == "position"

    def test_no_detection_returns_low_confidence(self, detector):
        """No exhibit context returns minimal result."""
        page = PageText(
            absolute_page=1847,
            relative_page=0,
            exhibit_id="",
            text="Random text without any headers",
        )
        result = detector.detect(page, {})

        assert result.confidence < 0.3
        assert result.source_type == "generic"


class TestHeaderDetectorBates:
    """Test Bates number detection."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    def test_bates_number_detection(self, detector):
        """Detect Bates stamp format."""
        page = PageText(
            absolute_page=1847,
            relative_page=0,
            exhibit_id="",
            text="ABC000123\nMedical records for patient...",
        )
        result = detector.detect(page, {})

        assert result.source_type == "bates"
        assert result.bates_number == "ABC000123"
        assert result.confidence >= 0.8


class TestHeaderDetectorTranscript:
    """Test transcript format detection."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    def test_transcript_page_detection(self, detector):
        """Detect transcript format: 'Page 45 of 120'."""
        page = PageText(
            absolute_page=100,
            relative_page=0,
            exhibit_id="",
            text="Page 45 of 120\nQ: Can you state your name for the record?",
        )
        result = detector.detect(page, {})

        assert result.source_type == "transcript"
        assert result.relative_page == 45
        assert result.total_pages == 120
        assert result.confidence >= 0.8


class TestHeaderDetectorOCRErrors:
    """Test handling of OCR errors in headers."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    def test_ocr_number_substitution(self, detector, exhibit_context):
        """Handle OCR errors like O for 0, l for 1."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="25F - 33 of 74    Medical Evidence",
        )
        result = detector.detect(page, exhibit_context)
        # Should still detect the pattern
        assert result.source_type == "ere"
