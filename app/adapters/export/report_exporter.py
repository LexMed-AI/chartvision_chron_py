"""
Report Exporter - Markdown and PDF export via Gotenberg.

Combines markdown generation with GotenbergAdapter for PDF conversion.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from app.adapters.export.gotenberg import GotenbergAdapter, get_gotenberg_adapter
from app.adapters.export import styles
from app.adapters.export.markdown_converter import MarkdownToPDFConverter

logger = logging.getLogger(__name__)


class ReportExporter:
    """
    Export reports to markdown and PDF.

    Uses GotenbergAdapter for PDF conversion (requires Docker).
    """

    def __init__(self, output_dir: str = "results"):
        """
        Initialize exporter.

        Args:
            output_dir: Directory for output files (default: results/)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._gotenberg: Optional[GotenbergAdapter] = None

    @property
    def gotenberg(self) -> GotenbergAdapter:
        """Lazy-init Gotenberg adapter."""
        if self._gotenberg is None:
            self._gotenberg = get_gotenberg_adapter()
        return self._gotenberg

    def gotenberg_available(self) -> bool:
        """Check if Gotenberg Docker is running."""
        try:
            return self.gotenberg._health_check_sync()
        except Exception:
            return False

    def export_markdown(
        self,
        report_data: Any,
        job_id: str,
        filename: Optional[str] = None,
    ) -> str:
        """
        Export report to markdown file.

        Args:
            report_data: ChartVisionReportData or object with to_markdown()
            job_id: Job identifier for filename
            filename: Optional custom filename

        Returns:
            Path to saved markdown file
        """
        # Generate markdown content
        if hasattr(report_data, "to_markdown"):
            markdown_content = report_data.to_markdown()
        elif isinstance(report_data, str):
            markdown_content = report_data
        else:
            raise ValueError("report_data must have to_markdown() or be a string")

        # Create job output directory
        job_dir = self.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Save markdown
        md_filename = filename or f"{job_id}_report.md"
        md_path = job_dir / md_filename

        with open(md_path, "w") as f:
            f.write(markdown_content)

        logger.info(f"Saved markdown: {md_path}")
        return str(md_path)

    def export_pdf(
        self,
        markdown_content: str,
        job_id: str,
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Export markdown to PDF with automatic fallback.

        Uses MarkdownToPDFConverter which tries:
        1. Gotenberg (if Docker running)
        2. WeasyPrint (if installed)
        3. wkhtmltopdf (if installed)

        Args:
            markdown_content: Markdown content to convert
            job_id: Job identifier for filename
            filename: Optional custom filename
            metadata: Optional metadata (title, patient_name, etc.)

        Returns:
            Path to PDF file, or None if no PDF backend available
        """
        # Create job output directory
        job_dir = self.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Generate PDF
        pdf_filename = filename or f"{job_id}_report.pdf"
        pdf_path = str(job_dir / pdf_filename)

        try:
            # Use MarkdownToPDFConverter which has fallback chain
            converter = MarkdownToPDFConverter()
            converter.convert_chartvision_to_pdf(
                markdown_content=markdown_content,
                output_path=pdf_path,
                metadata=metadata,
            )
            logger.info(f"Generated PDF: {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return None

    def _markdown_to_html(
        self,
        markdown_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Convert markdown to styled HTML for PDF generation.

        Delegates to MarkdownToPDFConverter for centralized conversion.
        """
        converter = MarkdownToPDFConverter()
        return converter.convert_chartvision_to_html(markdown_content, metadata)

    def convert_chartvision_to_html(
        self,
        markdown_content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Convert ChartVision markdown to HTML (public method).

        Args:
            markdown_content: Markdown content to convert
            metadata: Optional metadata for title

        Returns:
            HTML content
        """
        return self._markdown_to_html(markdown_content, metadata)

    def export_pdf_from_results(
        self,
        results: Dict[str, Any],
        job_id: str,
        filename: Optional[str] = None,
        title: str = "ChartVision Medical Chronology",
    ) -> Optional[str]:
        """
        Export PDF directly from job results using HTML generation.

        Uses fallback chain: Gotenberg → WeasyPrint → wkhtmltopdf

        Args:
            results: Job results containing dde_extraction and entries
            job_id: Job identifier for filename
            filename: Optional custom filename
            title: Document title

        Returns:
            Path to PDF file, or None if no PDF backend available
        """
        # Create job output directory
        job_dir = self.output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Generate PDF
        pdf_filename = filename or f"{job_id}_report.pdf"
        pdf_path = str(job_dir / pdf_filename)

        try:
            from app.adapters.export.html_renderer import render_chronology_html

            # Generate HTML matching UI styles
            html_content = render_chronology_html(results, title)

            # Use converter with fallback chain
            converter = MarkdownToPDFConverter()
            converter._html_to_pdf(html_content, pdf_path)
            logger.info(f"Generated PDF from results: {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"PDF generation from results failed: {e}")
            return None

    def export(
        self,
        report_data: Any,
        job_id: str,
        include_pdf: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Export report to both markdown and PDF.

        Args:
            report_data: ChartVisionReportData or object with to_markdown()
            job_id: Job identifier
            include_pdf: Generate PDF (default True)
            metadata: Optional metadata for PDF

        Returns:
            Dict with 'markdown' and 'pdf' paths (pdf may be None)
        """
        # Generate markdown content
        if hasattr(report_data, "to_markdown"):
            markdown_content = report_data.to_markdown()
        elif isinstance(report_data, str):
            markdown_content = report_data
        else:
            raise ValueError("report_data must have to_markdown() or be a string")

        # Export markdown
        md_path = self.export_markdown(markdown_content, job_id)

        # Export PDF if requested
        pdf_path = None
        if include_pdf:
            pdf_path = self.export_pdf(markdown_content, job_id, metadata=metadata)

        return {
            "markdown": md_path,
            "pdf": pdf_path,
        }

    def _get_report_css(self) -> str:
        """Get CSS styling for PDF reports.

        Delegates to styles.py for centralized CSS management.
        """
        return styles.get_chartvision_css()


def export_report(
    report_data: Any,
    job_id: str,
    output_dir: str = "results",
    include_pdf: bool = True,
) -> Dict[str, Optional[str]]:
    """
    Export report to markdown and PDF.

    Args:
        report_data: ChartVisionReportData or markdown string
        job_id: Job identifier
        output_dir: Output directory
        include_pdf: Generate PDF (default True)

    Returns:
        Dict with 'markdown' and 'pdf' paths
    """
    exporter = ReportExporter(output_dir=output_dir)
    return exporter.export(report_data, job_id, include_pdf=include_pdf)
