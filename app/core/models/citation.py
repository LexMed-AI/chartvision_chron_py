"""
Citation data model for tracking source page references.

Supports multiple document formats:
- ERE: "25F@33 (p.1847)"
- Bates: "ABC000123"
- Transcript: "p.45"
- Generic: "p.1847"
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Citation:
    """
    Citation linking an entry to its source page(s).

    Supports both exhibit-relative and absolute page references,
    with fallback handling for different document formats.
    """

    # Required: absolute PDF page (1-indexed)
    absolute_page: int

    # Exhibit-based (ERE format)
    exhibit_id: Optional[str] = None
    relative_page: Optional[int] = None
    total_pages: Optional[int] = None

    # Range support for multi-page entries
    end_relative_page: Optional[int] = None
    end_absolute_page: Optional[int] = None

    # Alternative identifiers
    bates_number: Optional[str] = None
    transcript_line: Optional[int] = None

    # Metadata
    source_type: str = "generic"  # "ere", "bates", "transcript", "generic"
    is_estimated: bool = False
    confidence: float = 1.0

    def format(self, style: str = "full") -> str:
        """
        Format citation in requested style.

        Args:
            style: "full", "exhibit", or "absolute"

        Returns:
            Formatted citation string.
        """
        # Bates format takes priority if present
        if self.bates_number and self.source_type == "bates":
            return self.bates_number

        # Exhibit-based formatting
        if self.exhibit_id and self.relative_page is not None:
            prefix = "~" if self.is_estimated else ""

            if style == "exhibit":
                return f"Ex. {self.exhibit_id}@{prefix}{self.relative_page}"

            if style == "absolute":
                return f"p.{self.absolute_page}"

            # Full format with optional range
            if self.end_absolute_page and self.end_absolute_page != self.absolute_page:
                return (
                    f"{self.exhibit_id}@{prefix}{self.relative_page}-"
                    f"{self.end_relative_page} "
                    f"(pp.{self.absolute_page}-{self.end_absolute_page})"
                )

            return f"{self.exhibit_id}@{prefix}{self.relative_page} (p.{self.absolute_page})"

        # Fallback to absolute page only
        return f"p.{self.absolute_page}"

    def is_valid(self) -> bool:
        """Check if citation has minimum required data."""
        return self.absolute_page > 0
