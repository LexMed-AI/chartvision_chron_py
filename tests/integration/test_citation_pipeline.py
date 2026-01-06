"""Integration tests for citation tracking through full pipeline."""
import pytest
from app.core.models.citation import Citation
from app.core.extraction.pdf_exhibit_extractor import PageText, build_combined_text
from app.core.extraction.header_detector import HeaderDetector
from app.core.extraction.citation_matcher import CitationMatcher


class TestCitationPipelineIntegration:
    """End-to-end citation tracking tests."""

    def test_header_detection_to_citation_flow(self):
        """Header detection flows through to final citation."""
        # Simulate ERE page with header
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="25F - 33 of 74    Medical Evidence of Record\n"
                 "03/15/2019 Dr. Smith examined patient...",
        )

        exhibit_context = {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

        # Step 1: Detect header
        detector = HeaderDetector()
        header_result = detector.detect(page, exhibit_context)

        assert header_result.source_type == "ere"
        assert header_result.relative_page == 33
        assert header_result.confidence >= 0.9

        # Step 2: Match entry to page
        page.header_info = {
            "source_type": header_result.source_type,
            "confidence": header_result.confidence,
        }

        matcher = CitationMatcher([page], exhibit_context)
        entry = {
            "date": "03/15/2019",
            "provider": "Dr. Smith",
        }

        result = matcher.match(entry)

        # Step 3: Verify citation
        assert result.citation.exhibit_id == "25F"
        assert result.citation.relative_page == 33
        assert result.citation.absolute_page == 1847
        assert result.citation.format() == "25F@33 (p.1847)"

    def test_fallback_citation_when_no_header(self):
        """Fallback works when no header detected."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Patient presented with symptoms on 03/15/2019. Dr. Smith evaluated.",
            header_info=None,
        )

        exhibit_context = {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

        matcher = CitationMatcher([page], exhibit_context)
        entry = {
            "date": "03/15/2019",
            "provider": "Dr. Smith",
        }

        result = matcher.match(entry)

        # Should still match based on content
        assert result.citation.absolute_page == 1847
        assert result.match_score >= 3.0

    def test_combined_text_marker_injection(self):
        """Page markers injected for headerless pages."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="Content without header",
                header_info=None,
            ),
        ]

        combined = build_combined_text(pages)
        assert "[PAGE 1847]" in combined

    def test_combined_text_no_marker_when_header_present(self):
        """No marker injected when header confidence is high."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="25F - 33 of 74\nContent with header",
                header_info={"confidence": 0.95, "source_type": "ere"},
            ),
        ]

        combined = build_combined_text(pages)
        assert "[PAGE 1847]" not in combined
        assert "25F - 33 of 74" in combined

    def test_citation_format_styles(self):
        """All citation format styles work correctly."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            total_pages=74,
        )

        assert citation.format("full") == "25F@33 (p.1847)"
        assert citation.format("exhibit") == "Ex. 25F@33"
        assert citation.format("absolute") == "p.1847"

    def test_estimated_citation_format(self):
        """Estimated citations show tilde prefix."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            is_estimated=True,
        )

        assert citation.format() == "25F@~33 (p.1847)"

    def test_multi_page_citation_format(self):
        """Multi-page citations show range."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            end_relative_page=35,
            end_absolute_page=1849,
        )

        assert citation.format() == "25F@33-35 (pp.1847-1849)"

    def test_bates_citation_format(self):
        """Bates citations use bates number."""
        citation = Citation(
            absolute_page=1847,
            bates_number="ABC000123",
            source_type="bates",
        )

        assert citation.format() == "ABC000123"

    def test_header_detector_fallback_chain(self):
        """HeaderDetector tries multiple strategies."""
        detector = HeaderDetector()

        # Page with no recognizable header
        page = PageText(
            absolute_page=1847,
            relative_page=0,
            exhibit_id="25F",
            text="Just some text without any headers",
        )

        exhibit_context = {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

        result = detector.detect(page, exhibit_context)

        # Should fall back to position inference
        assert result.detection_method == "position"
        assert result.relative_page == 33  # 1847 - 1815 + 1
        assert result.is_estimated is True

    def test_citation_is_valid(self):
        """Citation validation checks absolute_page."""
        valid = Citation(absolute_page=100)
        invalid = Citation(absolute_page=0)

        assert valid.is_valid() is True
        assert invalid.is_valid() is False

    def test_generic_citation_fallback(self):
        """Generic citation with no exhibit info."""
        citation = Citation(
            absolute_page=1847,
            source_type="generic",
        )

        # Should fall back to absolute page only
        assert citation.format() == "p.1847"

    def test_header_detector_ere_bar_pattern(self):
        """HeaderDetector recognizes ERE bar pattern."""
        detector = HeaderDetector()

        page = PageText(
            absolute_page=1000,
            relative_page=1,
            exhibit_id="10F",
            text="10F - 5 of 20\nSome medical content here",
        )

        result = detector.detect(page, {"exhibit_id": "10F"})

        assert result.source_type == "ere"
        assert result.exhibit_id == "10F"
        assert result.relative_page == 5
        assert result.total_pages == 20
        assert result.confidence == 0.95
        assert result.detection_method == "regex"

    def test_header_detector_bates_pattern(self):
        """HeaderDetector recognizes Bates stamps."""
        detector = HeaderDetector()

        page = PageText(
            absolute_page=500,
            relative_page=1,
            exhibit_id="5F",
            text="ABC000123\nMedical records for patient",
        )

        result = detector.detect(page, {"exhibit_id": "5F"})

        assert result.source_type == "bates"
        assert result.bates_number == "ABC000123"
        assert result.confidence == 0.85
        assert result.detection_method == "regex"

    def test_citation_matcher_multi_page_result(self):
        """CitationMatcher handles entries spanning multiple pages."""
        pages = [
            PageText(
                absolute_page=100,
                relative_page=1,
                exhibit_id="5F",
                text="03/15/2019 Dr. Smith began examination",
            ),
            PageText(
                absolute_page=101,
                relative_page=2,
                exhibit_id="5F",
                text="03/15/2019 Dr. Smith continued examination",
            ),
        ]

        exhibit_context = {
            "exhibit_id": "5F",
            "exhibit_start": 100,
            "exhibit_end": 150,
            "total_pages": 51,
        }

        matcher = CitationMatcher(pages, exhibit_context)
        entry = {
            "date": "03/15/2019",
            "provider": "Dr. Smith",
        }

        result = matcher.match(entry)

        # Should match both pages
        assert result.citation.absolute_page in [100, 101]
        assert result.match_score >= 5.0  # date (3.0) + provider (2.0)

    def test_citation_matcher_no_match_fallback(self):
        """CitationMatcher falls back when no terms match."""
        pages = [
            PageText(
                absolute_page=100,
                relative_page=1,
                exhibit_id="5F",
                text="Unrelated medical content about headaches",
            ),
        ]

        exhibit_context = {
            "exhibit_id": "5F",
            "exhibit_start": 100,
            "exhibit_end": 150,
            "total_pages": 51,
        }

        matcher = CitationMatcher(pages, exhibit_context)
        entry = {
            "date": "01/01/2020",
            "provider": "Dr. Jones",
        }

        result = matcher.match(entry)

        # Should use fallback
        assert result.match_method == "fallback"
        assert result.citation.is_estimated is True
        assert result.match_score == 0.0

    def test_full_pipeline_multiple_entries(self):
        """Full pipeline handles multiple entries across pages."""
        # Create pages with headers
        pages = [
            PageText(
                absolute_page=200,
                relative_page=1,
                exhibit_id="10F",
                text="10F - 1 of 50\n01/15/2019 Dr. Adams initial visit",
                header_info={"confidence": 0.95, "source_type": "ere"},
            ),
            PageText(
                absolute_page=201,
                relative_page=2,
                exhibit_id="10F",
                text="10F - 2 of 50\n02/20/2019 Dr. Brown follow up",
                header_info={"confidence": 0.95, "source_type": "ere"},
            ),
            PageText(
                absolute_page=202,
                relative_page=3,
                exhibit_id="10F",
                text="10F - 3 of 50\n03/25/2019 Dr. Carter specialist",
                header_info={"confidence": 0.95, "source_type": "ere"},
            ),
        ]

        exhibit_context = {
            "exhibit_id": "10F",
            "exhibit_start": 200,
            "exhibit_end": 250,
            "total_pages": 50,
        }

        matcher = CitationMatcher(pages, exhibit_context)

        # Test multiple entries
        entries = [
            {"date": "01/15/2019", "provider": "Dr. Adams"},
            {"date": "02/20/2019", "provider": "Dr. Brown"},
            {"date": "03/25/2019", "provider": "Dr. Carter"},
        ]

        results = [matcher.match(e) for e in entries]

        # Each entry should match its respective page
        assert results[0].citation.absolute_page == 200
        assert results[1].citation.absolute_page == 201
        assert results[2].citation.absolute_page == 202

        # All should be search matches (not fallback)
        assert all(r.match_method == "search" for r in results)

    def test_header_detector_transcript_pattern(self):
        """HeaderDetector recognizes transcript format."""
        detector = HeaderDetector()

        page = PageText(
            absolute_page=50,
            relative_page=1,
            exhibit_id="1F",
            text="Page 25 of 100\nQ: Can you describe your symptoms?",
        )

        result = detector.detect(page, {"exhibit_id": "1F"})

        assert result.source_type == "transcript"
        assert result.relative_page == 25
        assert result.total_pages == 100
        assert result.detection_method == "regex"
