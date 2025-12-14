"""
CSS styles for document export.

Contains all CSS generation functions for legal documents and ChartVision reports.
Extracted from markdown_converter.py for maintainability.
"""

from typing import Dict, Optional


def get_legal_css(
    font_family: str = "Times New Roman",
    font_size: str = "12pt",
    line_height: str = "1.5",
    margins: Optional[Dict[str, str]] = None,
    double_space: bool = False,
    line_numbers: bool = False,
) -> str:
    """Get CSS styles for legal documents.

    Args:
        font_family: Primary font family
        font_size: Base font size
        line_height: Line height (overridden if double_space)
        margins: Dict with top, bottom, left, right margins
        double_space: Whether to use double spacing
        line_numbers: Whether to include line number styles

    Returns:
        CSS string for legal document styling
    """
    if margins is None:
        margins = {"top": "0.5in", "bottom": "0.5in", "left": "0.3in", "right": "0.3in"}

    effective_line_height = "2.0" if double_space else line_height

    line_number_css = ""
    if line_numbers:
        line_number_css = "".join([
            f".line-{i}::before {{ content: '{i:3d}. '; color: #666; font-size: 10pt; }}"
            for i in range(1, 1001)
        ])

    return f"""
    body {{
        font-family: '{font_family}', serif;
        font-size: {font_size};
        line-height: {effective_line_height};
        margin: 0;
        padding: 0;
        color: #000;
        background: #fff;
    }}

    .document-content {{
        max-width: 8.5in;
        margin: 0 auto;
        padding: {margins['top']} {margins['right']} {margins['bottom']} {margins['left']};
    }}

    /* Headings */
    h1, h2, h3, h4, h5, h6 {{
        font-family: '{font_family}', serif;
        font-weight: bold;
        color: #000;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }}

    h1 {{
        font-size: 18pt;
        text-align: center;
        text-transform: uppercase;
        margin-bottom: 1em;
    }}

    h2 {{
        font-size: 14pt;
        text-decoration: underline;
    }}

    h3 {{
        font-size: 12pt;
        font-weight: bold;
    }}

    /* Paragraphs */
    p {{
        margin-bottom: 1em;
        text-align: justify;
        text-indent: 0.5in;
    }}

    /* Lists */
    ul, ol {{
        margin-left: 1in;
        margin-bottom: 1em;
    }}

    li {{
        margin-bottom: 0.25em;
    }}

    /* Tables */
    table {{
        border-collapse: collapse;
        margin: 1em 0;
        width: 100%;
    }}

    th, td {{
        border: 1px solid #000;
        padding: 0.25em 0.5em;
        text-align: left;
        vertical-align: top;
    }}

    th {{
        background-color: #f0f0f0;
        font-weight: bold;
    }}

    /* Citations */
    .case-citation {{
        font-style: italic;
        color: #000080;
    }}

    .statute-citation {{
        font-weight: bold;
        color: #800000;
    }}

    .cfr-citation {{
        color: #008000;
    }}

    .fed-reg-citation {{
        color: #800080;
    }}

    /* Footnotes */
    .footnote {{
        font-size: 10pt;
        line-height: 1.2;
        margin-top: 2em;
        border-top: 1px solid #000;
        padding-top: 0.5em;
    }}

    /* Block quotes */
    blockquote {{
        margin: 1em 0;
        padding-left: 1in;
        padding-right: 1in;
        font-style: italic;
    }}

    /* Code blocks */
    pre, code {{
        font-family: 'Courier New', monospace;
        font-size: 10pt;
        background-color: #f5f5f5;
        padding: 0.25em;
    }}

    pre {{
        white-space: pre-wrap;
        margin: 1em 0;
        padding: 0.5em;
        border: 1px solid #ccc;
    }}

    {line_number_css}

    /* Page breaks */
    .page-break {{
        page-break-before: always;
    }}

    /* Print styles */
    @media print {{
        body {{
            -webkit-print-color-adjust: exact;
            color-adjust: exact;
        }}

        .document-content {{
            margin: 0;
            padding: 0;
        }}
    }}
    """


def get_pdf_css(
    page_size: str = "letter",
    font_family: str = "Times New Roman",
    font_size: str = "12pt",
    line_height: str = "1.5",
    margins: Optional[Dict[str, str]] = None,
    header_text: str = "",
) -> str:
    """Get CSS styles specifically for PDF generation.

    Args:
        page_size: Page size (letter, A4, etc.)
        font_family: Primary font family
        font_size: Base font size
        line_height: Line height
        margins: Dict with top, bottom, left, right margins
        header_text: Text to display in page header

    Returns:
        CSS string for PDF-specific styling
    """
    if margins is None:
        margins = {"top": "0.5in", "bottom": "0.5in", "left": "0.3in", "right": "0.3in"}

    return f"""
    @page {{
        size: {page_size};
        margin: {margins['top']} {margins['right']} {margins['bottom']} {margins['left']};

        @top-center {{
            content: "{header_text}";
            font-size: 10pt;
            font-family: '{font_family}', serif;
        }}

        @bottom-center {{
            content: "Page " counter(page) " of " counter(pages);
            font-size: 10pt;
            font-family: '{font_family}', serif;
        }}
    }}

    body {{
        font-family: '{font_family}', serif;
        font-size: {font_size};
        line-height: {line_height};
        color: #000;
    }}

    /* Ensure proper page breaks */
    h1, h2, h3 {{
        page-break-after: avoid;
    }}

    p {{
        orphans: 2;
        widows: 2;
    }}

    table {{
        page-break-inside: avoid;
    }}

    .page-break {{
        page-break-before: always;
    }}
    """


def get_chartvision_css() -> str:
    """Get ChartVision-specific CSS styles matching SandefurChron.pdf.

    Returns:
        CSS string for ChartVision medical chronology styling
    """
    return """
    :root {
        --header-blue: #1a3a5c;
        --row-alt: #f8f9fa;
        --border-gray: #dee2e6;
        --text-dark: #212529;
    }

    body {
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 11pt;
        line-height: 1.4;
        color: var(--text-dark);
        margin: 0;
        padding: 0;
    }

    .document-content {
        width: 100%;
        max-width: 100%;
        margin: 0;
        padding: 0;
    }

    /* Main title */
    h1 {
        color: var(--header-blue);
        font-size: 18pt;
        text-align: center;
        margin-bottom: 20px;
        border-bottom: 3px solid var(--header-blue);
        padding-bottom: 10px;
    }

    /* Section headers - dark blue bars */
    h2 {
        background: var(--header-blue);
        color: white;
        padding: 8px 12px;
        margin: 20px 0 10px;
        font-size: 12pt;
        page-break-after: avoid;
    }

    h3 {
        border-bottom: 2px solid var(--header-blue);
        padding-bottom: 4px;
        font-size: 11pt;
        page-break-after: avoid;
        color: var(--header-blue);
    }

    /* Paragraphs */
    p {
        margin-bottom: 0.75em;
        text-align: left;
        text-indent: 0;
    }

    /* Tables - full width with minimal padding */
    table {
        width: 100% !important;
        border-collapse: collapse;
        margin: 8px 0;
        font-size: 9pt;
        page-break-inside: auto;
    }

    th {
        background: #e9ecef;
        font-weight: 600;
        text-align: left;
        padding: 4px 6px;
        border: 1px solid var(--border-gray);
    }

    td {
        padding: 4px 6px;
        border: 1px solid var(--border-gray);
        vertical-align: top;
    }

    /* Zebra striping */
    tr:nth-child(even) { background: var(--row-alt); }

    /* Bold table headers in first column */
    td strong, th strong {
        font-weight: 600;
    }

    /* Lists */
    ul, ol {
        margin-left: 20px;
        margin-bottom: 10px;
    }

    li {
        margin-bottom: 4px;
    }

    /* Horizontal rules */
    hr {
        border: none;
        border-top: 1px solid var(--border-gray);
        margin: 15px 0;
    }

    /* Notes/warnings */
    p strong:first-child {
        color: #856404;
    }

    /* Print-specific adjustments */
    @media print {
        body {
            font-size: 10pt;
        }

        .document-content {
            max-width: none;
            margin: 0;
            padding: 0;
        }

        h2 {
            page-break-after: avoid;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        table { page-break-inside: avoid; }
        tr { page-break-inside: avoid; }

        th, tr:nth-child(even) {
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }

        @page {
            margin: 0.4in 0.3in;
            size: letter;

            @top-center {
                content: "Medical Chronology";
                font-size: 9pt;
                color: #666;
            }

            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }
    }

    @media screen {
        body {
            background: #f0f0f0;
        }
        .document-content {
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-radius: 4px;
        }
        table {
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
    }
    """


def get_chronology_table_css() -> str:
    """Get CSS for chronology table in PDF export.

    Specific styling for the medical event timeline table,
    designed for PDF/print output via Gotenberg.

    Returns:
        CSS string for chronology table styling
    """
    return """
/* Chronology Table - specific styling for PDF export */
.chronology-table {
    width: 100%;
    border-collapse: collapse;
    margin: 12pt 0;
    font-family: 'Times New Roman', Times, serif;
    font-size: 10pt;
}

.chronology-table th,
.chronology-table td {
    border: 1px solid #000000;
    padding: 6pt 8pt;
    text-align: left;
    vertical-align: top;
}

.chronology-table th {
    background: #f0f0f0;
    color: #000000;
    font-weight: bold;
    text-transform: uppercase;
    font-size: 9pt;
}

.chronology-table tr:nth-child(even) { background: #fafafa; }

.chronology-table td:nth-child(1) { white-space: nowrap; width: 10%; }
.chronology-table td:nth-child(2) { width: 15%; }
.chronology-table td:nth-child(3) { width: 15%; }
.chronology-table td:nth-child(4) { width: 10%; }
.chronology-table td:nth-child(5) { width: 40%; line-height: 1.4; }
.chronology-table td:nth-child(6) { white-space: nowrap; width: 10%; }

.dde-section {
    margin-bottom: 24pt;
}

.dde-section p { margin-bottom: 3pt; }
"""


def get_citation_css() -> str:
    """Get CSS styles for legal citations.

    Returns:
        CSS string for citation styling
    """
    return """
    .case-citation {
        font-style: italic;
        color: #000080;
    }

    .statute-citation {
        font-weight: bold;
        color: #800000;
    }

    .cfr-citation {
        color: #008000;
    }

    .fed-reg-citation {
        color: #800080;
    }

    cite {
        font-style: normal;
    }
    """
