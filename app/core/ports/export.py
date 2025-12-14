"""Export port interface.

Defines the contract for document export operations. Core code depends only
on this abstraction, not on specific implementations like Gotenberg or WeasyPrint.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ExportPort(ABC):
    """Abstract interface for document export operations.

    Implementations: GotenbergAdapter, WeasyPrintAdapter
    """

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if export service is available.

        Returns:
            True if service is ready
        """
        pass

    @abstractmethod
    async def html_to_pdf(
        self,
        html: str,
        output_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convert HTML to PDF.

        Args:
            html: HTML content to convert
            output_path: Path for output PDF
            options: Optional conversion options (margins, page size, etc.)

        Returns:
            Path to generated PDF
        """
        pass

    @abstractmethod
    async def markdown_to_pdf(
        self,
        markdown: str,
        output_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convert Markdown to PDF.

        Args:
            markdown: Markdown content to convert
            output_path: Path for output PDF
            options: Optional conversion options

        Returns:
            Path to generated PDF
        """
        pass

    @abstractmethod
    async def markdown_to_html(
        self,
        markdown: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convert Markdown to HTML.

        Args:
            markdown: Markdown content to convert
            options: Optional conversion options (styling, metadata)

        Returns:
            HTML content
        """
        pass
