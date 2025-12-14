"""
Court document header patterns.

Domain knowledge: regex patterns for SSA/court administrative text
that should be stripped from medical records. Court transcripts have
overlay text (case numbers, page IDs, filing dates) that is selectable
but not part of the actual medical record content.
"""

import re
from typing import List, Pattern

# Regex patterns for court header/footer stripping
COURT_HEADER_PATTERNS: List[Pattern] = [
    # Case numbers: "Case 4:20-cv-00123-XXX", "Case No. 1:19-cv-456"
    re.compile(r'Case\s+(?:No\.\s*)?[\d:]+[-\w]+', re.IGNORECASE),
    # Document IDs: "Document 123", "Doc. 45", "Dkt. 67"
    re.compile(r'(?:Document|Doc\.?|Dkt\.?)\s+\d+', re.IGNORECASE),
    # Page indicators: "Page 23 of 55", "23 of 55", "p. 23"
    re.compile(r'(?:Page\s+)?\d+\s+of\s+\d+', re.IGNORECASE),
    re.compile(r'p\.\s*\d+', re.IGNORECASE),
    # Filing dates: "Filed 01/15/2020", "Date Filed: 01/15/2020"
    re.compile(r'(?:Date\s+)?Filed:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', re.IGNORECASE),
    # Electronic stamp: "Electronically Filed", "E-Filed"
    re.compile(r'E(?:lectronically)?[-\s]*Filed', re.IGNORECASE),
    # Exhibit markers: "EXHIBIT 1F", "Ex. 2A" (must have period after Ex)
    re.compile(r'EXHIBIT\s*[\dA-Z]+', re.IGNORECASE),
    re.compile(r'\bEx\.\s*[\dA-Z]+', re.IGNORECASE),
    # Court/District names: "UNITED STATES DISTRICT COURT"
    re.compile(r'UNITED\s+STATES\s+(?:DISTRICT|BANKRUPTCY)\s+COURT', re.IGNORECASE),
    re.compile(r'(?:EASTERN|WESTERN|NORTHERN|SOUTHERN)\s+DISTRICT\s+OF', re.IGNORECASE),
    # Plaintiff/Defendant markers
    re.compile(r'(?:Plaintiff|Defendant|Claimant|Appellant|Appellee)[,\s]', re.IGNORECASE),
    # vs/v. patterns: "Smith v. Jones"
    re.compile(r'\bv\.?\s+', re.IGNORECASE),
    # Page stamping: "PageID 123", "PageID# 456", "PageID.789"
    re.compile(r'PageID[#.]?\s*\d+', re.IGNORECASE),
    # CM/ECF stamps
    re.compile(r'CM/ECF', re.IGNORECASE),
    # Standard legal formatting artifacts
    re.compile(r'^\s*\d+\s*$'),  # Standalone page numbers
]


def strip_court_headers(text: str) -> str:
    """
    Remove court administrative headers/footers from page text.

    Court transcripts contain overlay text (case numbers, page IDs, filing dates)
    that is selectable but not part of the actual medical record content.

    Args:
        text: Raw page text

    Returns:
        Text with court headers/footers removed
    """
    result = text
    for pattern in COURT_HEADER_PATTERNS:
        result = pattern.sub('', result)

    # Remove excessive whitespace left over
    result = re.sub(r'\s+', ' ', result).strip()

    return result
