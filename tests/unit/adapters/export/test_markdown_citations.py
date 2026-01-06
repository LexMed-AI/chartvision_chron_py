"""Tests for citation support in markdown_converter."""
import pytest

from app.adapters.export.markdown_converter import format_entry, format_footer
from app.core.models.citation import Citation


class TestFormatEntry:
    """Test format_entry function with citation support."""

    def test_format_entry_with_citation(self):
        """Entry with citation includes Source line."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
        )

        entry = {
            "date": "03/15/2023",
            "provider": "Dr. Smith",
            "facility": "General Hospital",
            "event_type": "Office Visit",
            "description": "Follow-up for chronic back pain",
            "citation": citation,
        }

        result = format_entry(entry)

        assert "### 03/15/2023" in result
        assert "**Office Visit**" in result
        assert "Dr. Smith - General Hospital" in result
        assert "**Source:** 25F@33 (p.1847)" in result
        assert "Follow-up for chronic back pain" in result

    def test_format_entry_without_citation(self):
        """Entry without citation omits Source line."""
        entry = {
            "date": "01/01/2024",
            "provider": "Dr. Jones",
            "description": "Annual physical examination",
        }

        result = format_entry(entry)

        assert "### 01/01/2024" in result
        assert "Dr. Jones" in result
        assert "**Source:**" not in result
        assert "Annual physical examination" in result

    def test_format_entry_with_dict_citation(self):
        """Entry with dict citation (from JSON) includes Source line."""
        entry = {
            "date": "05/20/2023",
            "provider": "Dr. Williams",
            "description": "MRI of lumbar spine",
            "citation": {
                "exhibit_id": "10F",
                "relative_page": 5,
                "absolute_page": 500,
                "formatted": "10F@5 (p.500)",
            },
        }

        result = format_entry(entry)

        assert "### 05/20/2023" in result
        assert "**Source:** 10F@5 (p.500)" in result
        assert "MRI of lumbar spine" in result

    def test_format_entry_citation_object_formats_dynamically(self):
        """Citation object uses format() method dynamically."""
        citation = Citation(
            exhibit_id="5F",
            relative_page=10,
            absolute_page=250,
            is_estimated=True,  # Should show tilde
        )

        entry = {
            "date": "07/04/2023",
            "description": "Lab results",
            "citation": citation,
        }

        result = format_entry(entry)

        # format() should include ~ for estimated
        assert "**Source:** 5F@~10 (p.250)" in result

    def test_format_entry_minimal(self):
        """Entry with only description still works."""
        entry = {
            "description": "Medical event",
        }

        result = format_entry(entry)

        assert "### Unknown Date" in result
        assert "Medical event" in result

    def test_format_entry_provider_only(self):
        """Entry with only provider (no facility)."""
        entry = {
            "date": "02/28/2024",
            "provider": "Dr. Adams",
            "description": "Consultation",
        }

        result = format_entry(entry)

        assert "Dr. Adams" in result
        assert " - " not in result.split("\n")[4]  # No separator without facility

    def test_format_entry_facility_only(self):
        """Entry with only facility (no provider)."""
        entry = {
            "date": "02/28/2024",
            "facility": "City Hospital",
            "description": "Emergency room visit",
        }

        result = format_entry(entry)

        assert "City Hospital" in result


class TestFormatFooter:
    """Test format_footer function for source aggregation."""

    def test_format_footer_aggregates_sources(self):
        """Footer aggregates citations by exhibit."""
        entries = [
            {
                "date": "01/01/2024",
                "description": "Event 1",
                "citation": Citation(
                    exhibit_id="5F",
                    relative_page=1,
                    absolute_page=100,
                ),
            },
            {
                "date": "01/02/2024",
                "description": "Event 2",
                "citation": Citation(
                    exhibit_id="5F",
                    relative_page=5,
                    absolute_page=104,
                ),
            },
            {
                "date": "01/03/2024",
                "description": "Event 3",
                "citation": Citation(
                    exhibit_id="10F",
                    relative_page=10,
                    absolute_page=500,
                ),
            },
        ]

        result = format_footer(entries)

        assert "## Sources" in result
        assert "**Exhibit 5F**" in result
        assert "2 citation(s)" in result
        assert "pp.100-104" in result
        assert "**Exhibit 10F**" in result
        assert "1 citation(s)" in result
        assert "p.500" in result

    def test_format_footer_no_citations(self):
        """Footer returns empty string when no citations present."""
        entries = [
            {"date": "01/01/2024", "description": "No citation"},
            {"date": "01/02/2024", "description": "Also no citation"},
        ]

        result = format_footer(entries)

        assert result == ""

    def test_format_footer_mixed_citations(self):
        """Footer handles mix of entries with and without citations."""
        entries = [
            {
                "description": "With citation",
                "citation": Citation(
                    exhibit_id="1F",
                    relative_page=1,
                    absolute_page=50,
                ),
            },
            {
                "description": "Without citation",
            },
            {
                "description": "Also with citation",
                "citation": Citation(
                    exhibit_id="1F",
                    relative_page=2,
                    absolute_page=51,
                ),
            },
        ]

        result = format_footer(entries)

        assert "## Sources" in result
        assert "**Exhibit 1F**" in result
        assert "2 citation(s)" in result

    def test_format_footer_sorts_exhibits_naturally(self):
        """Exhibits are sorted naturally (1F, 2F, 10F, not 1F, 10F, 2F)."""
        entries = [
            {
                "description": "Event",
                "citation": Citation(exhibit_id="10F", relative_page=1, absolute_page=300),
            },
            {
                "description": "Event",
                "citation": Citation(exhibit_id="2F", relative_page=1, absolute_page=100),
            },
            {
                "description": "Event",
                "citation": Citation(exhibit_id="1F", relative_page=1, absolute_page=50),
            },
        ]

        result = format_footer(entries)

        lines = result.split("\n")
        exhibit_lines = [line for line in lines if "**Exhibit" in line]

        assert len(exhibit_lines) == 3
        assert "1F" in exhibit_lines[0]
        assert "2F" in exhibit_lines[1]
        assert "10F" in exhibit_lines[2]

    def test_format_footer_with_dict_citations(self):
        """Footer handles dict citations (from JSON deserialization)."""
        entries = [
            {
                "description": "Event 1",
                "citation": {
                    "exhibit_id": "3F",
                    "relative_page": 5,
                    "absolute_page": 150,
                    "formatted": "3F@5 (p.150)",
                },
            },
            {
                "description": "Event 2",
                "citation": {
                    "exhibit_id": "3F",
                    "relative_page": 10,
                    "absolute_page": 155,
                    "formatted": "3F@10 (p.155)",
                },
            },
        ]

        result = format_footer(entries)

        assert "## Sources" in result
        assert "**Exhibit 3F**" in result
        assert "2 citation(s)" in result
        assert "pp.150-155" in result

    def test_format_footer_generic_pages(self):
        """Footer includes 'Other Sources' for citations without exhibit_id."""
        entries = [
            {
                "description": "Generic citation",
                "citation": Citation(
                    absolute_page=999,
                ),
            },
        ]

        result = format_footer(entries)

        assert "## Sources" in result
        assert "**Other Sources**" in result
        assert "1 citation(s)" in result
        assert "p.999" in result

    def test_format_footer_deduplicates_pages(self):
        """Footer deduplicates repeated pages for same exhibit."""
        entries = [
            {
                "description": "Event 1",
                "citation": Citation(exhibit_id="5F", relative_page=1, absolute_page=100),
            },
            {
                "description": "Event 2",
                "citation": Citation(exhibit_id="5F", relative_page=1, absolute_page=100),  # Same page
            },
        ]

        result = format_footer(entries)

        assert "**Exhibit 5F**" in result
        # Should show 1 unique page, not 2
        assert "p.100" in result  # Singular page reference
