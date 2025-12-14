"""
Extended bookmark models for analysis results.

Domain models for representing PDF bookmark structure analysis.
The base Bookmark class is in core/ports/pdf.py.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from app.core.ports.pdf import Bookmark


@dataclass
class BookmarkTree:
    """Hierarchical representation of bookmarks with analysis metadata."""

    root_bookmarks: List[Bookmark]
    total_bookmarks: int
    max_depth: int
    page_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "root_bookmarks": [
                {
                    "title": bm.title,
                    "page_start": bm.page_start,
                    "page_end": bm.page_end,
                    "level": bm.level,
                }
                for bm in self.root_bookmarks
            ],
            "total_bookmarks": self.total_bookmarks,
            "max_depth": self.max_depth,
            "page_count": self.page_count,
        }
