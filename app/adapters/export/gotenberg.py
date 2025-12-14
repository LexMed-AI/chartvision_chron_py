"""
Gotenberg adapter for PDF generation.

Implements ExportPort using the Gotenberg Docker API for HTML/Markdown to PDF conversion.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from app.core.ports.export import ExportPort

logger = logging.getLogger(__name__)


class GotenbergAdapter(ExportPort):
    """
    Gotenberg implementation of ExportPort.

    Uses Gotenberg Docker API for PDF generation via Chromium.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: int = 120):
        """
        Initialize the Gotenberg adapter.

        Args:
            base_url: Gotenberg API URL (default: http://localhost:3030)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("GOTENBERG_URL", "http://localhost:3030")
        self.timeout = timeout
        logger.info(f"Initialized GotenbergAdapter: {self.base_url}")

    async def health_check(self) -> bool:
        """Check if Gotenberg is available."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._health_check_sync)

    def _health_check_sync(self) -> bool:
        """Synchronous health check."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    async def html_to_pdf(
        self,
        html: str,
        output_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convert HTML to PDF."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._html_to_pdf_sync, html, output_path, options
        )

    def _html_to_pdf_sync(
        self,
        html: str,
        output_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Synchronous HTML to PDF conversion."""
        options = options or {}

        files = {
            "index.html": ("index.html", html, "text/html")
        }

        data = {
            "marginTop": options.get("margin_top", "1"),
            "marginBottom": options.get("margin_bottom", "1"),
            "marginLeft": options.get("margin_left", "1"),
            "marginRight": options.get("margin_right", "1"),
            "paperWidth": options.get("paper_width", "8.5"),
            "paperHeight": options.get("paper_height", "11"),
            "printBackground": options.get("print_background", "true"),
        }

        # Add header/footer if provided
        if options.get("header_html"):
            files["header.html"] = ("header.html", options["header_html"], "text/html")
        if options.get("footer_html"):
            files["footer.html"] = ("footer.html", options["footer_html"], "text/html")

        try:
            response = requests.post(
                f"{self.base_url}/forms/chromium/convert/html",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)

            logger.info(f"Generated PDF: {output_path}")
            return output_path

        except requests.RequestException as e:
            logger.error(f"Gotenberg HTML to PDF failed: {e}")
            raise

    async def markdown_to_pdf(
        self,
        markdown: str,
        output_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convert Markdown to PDF."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._markdown_to_pdf_sync, markdown, output_path, options
        )

    def _markdown_to_pdf_sync(
        self,
        markdown: str,
        output_path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Synchronous Markdown to PDF conversion."""
        options = options or {}

        files = {
            "index.html": ("index.html", markdown, "text/markdown")
        }

        if options.get("css"):
            files["style.css"] = ("style.css", options["css"], "text/css")

        data = {
            "marginTop": options.get("margin_top", "1"),
            "marginBottom": options.get("margin_bottom", "1"),
            "marginLeft": options.get("margin_left", "1"),
            "marginRight": options.get("margin_right", "1"),
        }

        try:
            response = requests.post(
                f"{self.base_url}/forms/chromium/convert/markdown",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)

            logger.info(f"Generated PDF from Markdown: {output_path}")
            return output_path

        except requests.RequestException as e:
            logger.error(f"Gotenberg Markdown to PDF failed: {e}")
            raise

    async def markdown_to_html(
        self,
        markdown: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convert Markdown to HTML.

        Note: This uses python-markdown locally, not Gotenberg.
        """
        try:
            import markdown as md_lib
        except ImportError:
            raise ImportError("python-markdown is required for markdown_to_html")

        extensions = [
            "markdown.extensions.tables",
            "markdown.extensions.toc",
            "markdown.extensions.fenced_code",
            "markdown.extensions.attr_list",
        ]

        converter = md_lib.Markdown(extensions=extensions, output_format="html5")
        return converter.convert(markdown)


# Singleton instance
_adapter: Optional[GotenbergAdapter] = None


def get_gotenberg_adapter() -> GotenbergAdapter:
    """Get or create the Gotenberg adapter singleton."""
    global _adapter
    if _adapter is None:
        _adapter = GotenbergAdapter()
    return _adapter
