"""
Markdown to PDF Converter.

Legal document formatting with citations. Uses styles from styles.py.
"""

import logging
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

from app.adapters.export import styles
from app.core.models.citation import Citation

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

try:
    import weasyprint
    HAS_WEASYPRINT = True
except (ImportError, OSError):
    HAS_WEASYPRINT = False

try:
    from app.adapters.export.gotenberg import GotenbergAdapter, get_gotenberg_adapter
    _gotenberg = get_gotenberg_adapter()
    HAS_GOTENBERG = _gotenberg._health_check_sync()
except (ImportError, Exception):
    HAS_GOTENBERG = False

logger = logging.getLogger(__name__)


# Citation patterns for legal documents
CITATION_PATTERNS = [
    # Case citations: Name v. Name, Volume Reporter Page (Year)
    (
        r"(\w+(?:\s+\w+)*)\s+v\.\s+(\w+(?:\s+\w+)*),\s+(\d+)\s+(\w+(?:\s+\w+)*)\s+(\d+)\s+\((\d{4})\)",
        r'<cite class="case-citation">\1 v. \2, \3 \4 \5 (\6)</cite>',
    ),
    # Statute citations: Title Code § Section
    (
        r"(\d+)\s+([A-Z]\.?[A-Z]\.?[A-Z]\.?)\s+§\s+(\d+(?:\.\d+)*)",
        r'<cite class="statute-citation">\1 \2 § \3</cite>',
    ),
    # CFR citations: Title C.F.R. § Section
    (
        r"(\d+)\s+C\.F\.R\.\s+§\s+(\d+(?:\.\d+)*)",
        r'<cite class="cfr-citation">\1 C.F.R. § \2</cite>',
    ),
    # Federal Register citations: Volume Fed. Reg. Page
    (
        r"(\d+)\s+Fed\.\s+Reg\.\s+(\d+)",
        r'<cite class="fed-reg-citation">\1 Fed. Reg. \2</cite>',
    ),
]


class MarkdownToPDFConverter:
    """Convert Markdown to PDF with legal document formatting."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the converter.

        Args:
            config: Configuration options for styling
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.page_size = self.config.get("page_size", "letter")
        self.margins = self.config.get(
            "margins",
            {"top": "0.5in", "bottom": "0.5in", "left": "0.3in", "right": "0.3in"}
        )
        self.font_family = self.config.get("font_family", "Times New Roman")
        self.font_size = self.config.get("font_size", "12pt")
        self.line_height = self.config.get("line_height", "1.5")

        # Legal formatting options
        self.double_space = self.config.get("double_space", False)
        self.line_numbers = self.config.get("line_numbers", False)

        self._check_dependencies()

    def convert_to_pdf(
        self,
        markdown_content: str,
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Convert markdown content to PDF.

        Args:
            markdown_content: Markdown content to convert
            output_path: Output PDF file path
            metadata: Document metadata for headers/footers

        Returns:
            Path to generated PDF file
        """
        html_content = self._markdown_to_html(markdown_content)
        styled_html = self._add_legal_styling(html_content, metadata)
        return self._html_to_pdf(styled_html, output_path)

    def convert_to_html(
        self,
        markdown_content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Convert markdown content to HTML.

        Args:
            markdown_content: Markdown content to convert
            metadata: Document metadata

        Returns:
            HTML content
        """
        html_content = self._markdown_to_html(markdown_content)
        return self._add_legal_styling(html_content, metadata)

    def convert_chartvision_to_pdf(
        self,
        markdown_content: str,
        output_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Convert ChartVision markdown to PDF with specialized styling.

        Args:
            markdown_content: ChartVision-format markdown content
            output_path: Output PDF file path
            metadata: Document metadata

        Returns:
            Path to generated PDF file
        """
        html_content = self._markdown_to_html(markdown_content)
        styled_html = self._add_chartvision_styling(html_content, metadata)
        return self._html_to_pdf(styled_html, output_path)

    def convert_chartvision_to_html(
        self,
        markdown_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Convert ChartVision markdown to HTML with specialized styling.

        Args:
            markdown_content: ChartVision-format markdown content
            metadata: Document metadata

        Returns:
            Styled HTML content
        """
        html_content = self._markdown_to_html(markdown_content)
        return self._add_chartvision_styling(html_content, metadata)

    def _markdown_to_html(self, markdown_content: str) -> str:
        """Convert markdown to HTML using python-markdown."""
        if not HAS_MARKDOWN:
            raise ImportError("python-markdown is required for markdown conversion")

        extensions = [
            "markdown.extensions.tables",
            "markdown.extensions.toc",
            "markdown.extensions.fenced_code",
            "markdown.extensions.attr_list",
            "markdown.extensions.def_list",
            "markdown.extensions.footnotes",
        ]

        md = markdown.Markdown(extensions=extensions, output_format="html5")
        html = md.convert(markdown_content)
        return self._process_citations(html)

    def _process_citations(self, html_content: str) -> str:
        """Process legal citations in HTML content."""
        for pattern, replacement in CITATION_PATTERNS:
            html_content = re.sub(pattern, replacement, html_content, flags=re.IGNORECASE)
        return html_content

    def _add_legal_styling(
        self,
        html_content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add legal document styling to HTML."""
        css_styles = styles.get_legal_css(
            font_family=self.font_family,
            font_size=self.font_size,
            line_height=self.line_height,
            margins=self.margins,
            double_space=self.double_space,
            line_numbers=self.line_numbers,
        )

        title = metadata.get("title", "Legal Document") if metadata else "Legal Document"

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>{css_styles}</style>
        </head>
        <body>
            {self._add_header(metadata) if metadata else ''}
            <div class="document-content">{html_content}</div>
            {self._add_footer(metadata) if metadata else ''}
        </body>
        </html>
        """

    def _add_chartvision_styling(
        self,
        html_content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add ChartVision styling to HTML."""
        css_styles = styles.get_chartvision_css()

        title = "Medical Chronology"
        if metadata:
            if metadata.get("patient_name"):
                title = f"Medical Chronology - {metadata['patient_name']}"
            elif metadata.get("title"):
                title = metadata["title"]

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>{css_styles}</style>
        </head>
        <body>
            <div class="document-content">{html_content}</div>
        </body>
        </html>
        """

    def _html_to_pdf(self, html_content: str, output_path: str) -> str:
        """Convert HTML to PDF using available backend."""
        # Priority 1: Gotenberg
        if HAS_GOTENBERG:
            try:
                return self._html_to_pdf_gotenberg(html_content, output_path)
            except Exception as e:
                self.logger.warning(f"Gotenberg failed, trying alternatives: {e}")

        # Priority 2: WeasyPrint
        if HAS_WEASYPRINT:
            try:
                return self._html_to_pdf_weasyprint(html_content, output_path)
            except Exception as e:
                self.logger.warning(f"WeasyPrint failed: {e}")

        # Priority 3: wkhtmltopdf fallback
        return self._html_to_pdf_wkhtmltopdf(html_content, output_path)

    def _html_to_pdf_gotenberg(self, html_content: str, output_path: str) -> str:
        """Convert HTML to PDF using Gotenberg."""
        options = {
            "margin_top": self.margins.get("top", "1in").replace("in", ""),
            "margin_bottom": self.margins.get("bottom", "1in").replace("in", ""),
            "margin_left": self.margins.get("left", "1in").replace("in", ""),
            "margin_right": self.margins.get("right", "1in").replace("in", ""),
            "print_background": "true",
        }

        adapter = get_gotenberg_adapter()
        adapter._html_to_pdf_sync(html_content, output_path, options)
        self.logger.info(f"Generated PDF via Gotenberg: {output_path}")
        return output_path

    def _html_to_pdf_weasyprint(self, html_content: str, output_path: str) -> str:
        """Convert HTML to PDF using WeasyPrint."""
        html_doc = weasyprint.HTML(string=html_content)
        css_string = styles.get_pdf_css(
            page_size=self.page_size,
            font_family=self.font_family,
            font_size=self.font_size,
            line_height=self.line_height,
            margins=self.margins,
            header_text=self.config.get("header_text", ""),
        )
        css_doc = weasyprint.CSS(string=css_string)
        html_doc.write_pdf(output_path, stylesheets=[css_doc])
        self.logger.info(f"Generated PDF via WeasyPrint: {output_path}")
        return output_path

    def _html_to_pdf_wkhtmltopdf(self, html_content: str, output_path: str) -> str:
        """Convert HTML to PDF using wkhtmltopdf (fallback)."""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False
            ) as tmp_file:
                tmp_file.write(html_content)
                tmp_html_path = tmp_file.name

            cmd = [
                "wkhtmltopdf",
                "--page-size", self.page_size.upper(),
                "--margin-top", self.margins["top"],
                "--margin-bottom", self.margins["bottom"],
                "--margin-left", self.margins["left"],
                "--margin-right", self.margins["right"],
                "--encoding", "UTF-8",
                "--print-media-type",
                tmp_html_path,
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            os.unlink(tmp_html_path)

            if result.returncode != 0:
                raise Exception(f"wkhtmltopdf failed: {result.stderr}")

            self.logger.info(f"Generated PDF using wkhtmltopdf: {output_path}")
            return output_path

        except FileNotFoundError:
            raise Exception("No PDF converter available (Gotenberg, WeasyPrint, or wkhtmltopdf)")
        except Exception:
            if "tmp_html_path" in locals():
                try:
                    os.unlink(tmp_html_path)
                except Exception:
                    pass
            raise

    def _add_header(self, metadata: Dict[str, Any]) -> str:
        """Add document header."""
        parts = []
        if metadata.get("case_number"):
            parts.append(f"Case No. {metadata['case_number']}")
        if metadata.get("court"):
            parts.append(metadata["court"])
        if metadata.get("title"):
            parts.append(f"<h1>{metadata['title']}</h1>")

        if parts:
            return f'<div class="document-header">{"<br>".join(parts)}</div>'
        return ""

    def _add_footer(self, metadata: Dict[str, Any]) -> str:
        """Add document footer."""
        parts = []
        if metadata.get("attorney_name"):
            parts.append(f"Attorney: {metadata['attorney_name']}")
        if metadata.get("bar_number"):
            parts.append(f"Bar No. {metadata['bar_number']}")
        if metadata.get("firm_name"):
            parts.append(metadata["firm_name"])

        if parts:
            return f'<div class="document-footer">{"<br>".join(parts)}</div>'
        return ""

    def _check_dependencies(self) -> None:
        """Check for required dependencies."""
        if not HAS_MARKDOWN:
            self.logger.warning("python-markdown not available")
        if not HAS_WEASYPRINT and not HAS_GOTENBERG:
            self.logger.warning("No PDF backend available")

    def add_page_break(self, content: str) -> str:
        """Add page break to content."""
        return content + '\n\n<div class="page-break"></div>\n\n'

    def create_table_of_contents(self, content: str) -> str:
        """Create table of contents from headers."""
        headers = re.findall(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE)
        if not headers:
            return ""

        toc_lines = ["## Table of Contents\n"]
        for level, title in headers:
            indent = "  " * (len(level) - 1)
            toc_lines.append(f"{indent}- {title}")

        return "\n".join(toc_lines) + "\n\n"

    def batch_convert(self, markdown_files: List[str], output_dir: str) -> List[str]:
        """Convert multiple markdown files to PDF."""
        output_files = []
        for markdown_file in markdown_files:
            try:
                with open(markdown_file, "r", encoding="utf-8") as f:
                    content = f.read()

                base_name = os.path.splitext(os.path.basename(markdown_file))[0]
                output_file = os.path.join(output_dir, f"{base_name}.pdf")
                self.convert_to_pdf(content, output_file)
                output_files.append(output_file)
            except Exception as e:
                self.logger.error(f"Error converting {markdown_file}: {e}")

        return output_files


def _get_citation_formatted(citation: Union[Citation, Dict[str, Any], None]) -> Optional[str]:
    """Extract formatted citation string from Citation object or dict.

    Args:
        citation: Citation object, dict with 'formatted' key, or None

    Returns:
        Formatted citation string or None
    """
    if citation is None:
        return None

    if isinstance(citation, Citation):
        return citation.format()

    if isinstance(citation, dict) and "formatted" in citation:
        return citation["formatted"]

    return None


def format_entry(entry: Dict[str, Any]) -> str:
    """Format a chronology entry as markdown with optional citation.

    Args:
        entry: Dict containing chronology entry data with optional 'citation' key

    Returns:
        Markdown-formatted entry string
    """
    lines = []

    # Date header
    date = entry.get("date", "Unknown Date")
    lines.append(f"### {date}")
    lines.append("")

    # Event type
    event_type = entry.get("event_type")
    if event_type:
        lines.append(f"**{event_type}**")
        lines.append("")

    # Provider/Facility
    provider = entry.get("provider")
    facility = entry.get("facility")
    if provider or facility:
        provider_line_parts = []
        if provider:
            provider_line_parts.append(provider)
        if facility:
            provider_line_parts.append(facility)
        lines.append(" - ".join(provider_line_parts))
        lines.append("")

    # Citation (source reference)
    citation = entry.get("citation")
    formatted_citation = _get_citation_formatted(citation)
    if formatted_citation:
        lines.append(f"**Source:** {formatted_citation}")
        lines.append("")

    # Description
    description = entry.get("description", "")
    if description:
        lines.append(description)
        lines.append("")

    return "\n".join(lines)


def format_footer(entries: List[Dict[str, Any]]) -> str:
    """Generate a sources footer aggregating citations by exhibit.

    Args:
        entries: List of chronology entry dicts, each with optional 'citation' key

    Returns:
        Markdown-formatted sources section
    """
    # Aggregate sources by exhibit
    exhibit_pages: Dict[str, List[int]] = defaultdict(list)
    generic_pages: List[int] = []

    for entry in entries:
        citation = entry.get("citation")
        if citation is None:
            continue

        # Handle Citation object or dict
        if isinstance(citation, Citation):
            exhibit_id = citation.exhibit_id
            abs_page = citation.absolute_page
        elif isinstance(citation, dict):
            exhibit_id = citation.get("exhibit_id")
            abs_page = citation.get("absolute_page")
        else:
            continue

        if abs_page is None:
            continue

        if exhibit_id:
            exhibit_pages[exhibit_id].append(abs_page)
        else:
            generic_pages.append(abs_page)

    # Build footer if we have any sources
    if not exhibit_pages and not generic_pages:
        return ""

    lines = ["## Sources", ""]

    # Sort exhibits naturally (1F, 2F, ..., 10F, 11F)
    def exhibit_sort_key(exhibit_id: str) -> tuple:
        """Extract numeric portion for natural sorting."""
        match = re.match(r"(\d+)([A-Z]*)", exhibit_id)
        if match:
            return (int(match.group(1)), match.group(2))
        return (999, exhibit_id)

    for exhibit_id in sorted(exhibit_pages.keys(), key=exhibit_sort_key):
        pages = sorted(set(exhibit_pages[exhibit_id]))
        page_count = len(pages)
        min_page = min(pages)
        max_page = max(pages)

        if min_page == max_page:
            page_range = f"p.{min_page}"
        else:
            page_range = f"pp.{min_page}-{max_page}"

        lines.append(f"- **Exhibit {exhibit_id}**: {page_count} citation(s), {page_range}")

    if generic_pages:
        pages = sorted(set(generic_pages))
        page_count = len(pages)
        min_page = min(pages)
        max_page = max(pages)

        if min_page == max_page:
            page_range = f"p.{min_page}"
        else:
            page_range = f"pp.{min_page}-{max_page}"

        lines.append(f"- **Other Sources**: {page_count} citation(s), {page_range}")

    lines.append("")
    return "\n".join(lines)
