"""
CitationResolver - Map absolute PDF pages to exhibit references.

This bridges BookmarkExtractor (page ranges) to the extraction pipeline,
enabling accurate citations like 'Ex. 4F@3 (p.1403)'.

Works alongside the existing citation module which handles text pattern
matching for citations found IN documents.

Usage:
    from app.adapters.pdf.pymupdf import PyMuPDFAdapter
    from app.core.extraction.citation_resolver import CitationResolver

    # Get exhibit ranges via PDFPort
    pdf = PyMuPDFAdapter()
    ranges = pdf.get_exhibit_page_ranges(pdf_path)

    # Create resolver
    resolver = CitationResolver(ranges)

    # Format citations for output
    citation = resolver.format(1403)  # "Ex. 4F@3 (p.1403)"
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ResolvedCitation:
    """Result of resolving an absolute page to exhibit reference."""
    exhibit_id: str
    relative_page: int
    absolute_page: int


class CitationResolver:
    """
    Map absolute PDF page numbers to exhibit references.

    Bridges BookmarkExtractor output to the extraction pipeline,
    enabling accurate citations like 'Ex. 4F@3 (p.1403)'.
    """

    def __init__(self, exhibit_ranges: List[Dict]):
        """
        Initialize with exhibit page ranges.

        Args:
            exhibit_ranges: Output from BookmarkExtractor.get_exhibit_page_ranges()
                           List of dicts with exhibit_id, start_page, end_page
        """
        self._index: Dict[int, tuple] = {}
        for ex in exhibit_ranges:
            exhibit_id = ex.get("exhibit_id", "")
            start = ex.get("start_page", 0)
            end = ex.get("end_page", 0)
            if exhibit_id and start:
                for page in range(start, end + 1):
                    self._index[page] = (exhibit_id, page - start + 1)

    def resolve(self, absolute_page: int) -> Optional[ResolvedCitation]:
        """
        Resolve absolute page to exhibit reference.

        Args:
            absolute_page: 1-indexed PDF page number

        Returns:
            ResolvedCitation or None if page not in any exhibit
        """
        if absolute_page in self._index:
            exhibit_id, relative = self._index[absolute_page]
            return ResolvedCitation(exhibit_id, relative, absolute_page)
        return None

    def format(self, absolute_page: int) -> str:
        """
        Format page as citation string.

        Args:
            absolute_page: 1-indexed PDF page number

        Returns:
            'Ex. 4F@3 (p.1403)' or 'p.1403' if not in exhibit
        """
        resolved = self.resolve(absolute_page)
        if resolved:
            return f"Ex. {resolved.exhibit_id}@{resolved.relative_page} (p.{absolute_page})"
        return f"p.{absolute_page}"

    def format_range(self, start_page: int, end_page: int) -> str:
        """
        Format page range as citation string.

        Args:
            start_page: First page (1-indexed)
            end_page: Last page (1-indexed)

        Returns:
            'Ex. 4F@1-5 (pp.1401-1405)' or 'pp.1401-1405'
        """
        start = self.resolve(start_page)
        end = self.resolve(end_page)

        if start and end and start.exhibit_id == end.exhibit_id:
            return (
                f"Ex. {start.exhibit_id}@{start.relative_page}-{end.relative_page} "
                f"(pp.{start_page}-{end_page})"
            )
        return f"pp.{start_page}-{end_page}"
