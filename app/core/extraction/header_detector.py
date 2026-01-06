"""
Multi-format header detection for citation extraction.

Supports:
- ERE format: "25F - 33 of 74", "EXHIBIT NO. 25F / PAGE: 33"
- Bates stamps: "ABC000123"
- Court transcripts: "Page 45 of 120"
- Generic fallback: position-based inference
"""
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.core.extraction.pdf_exhibit_extractor import PageText


@dataclass
class HeaderDetectionResult:
    """Result of header detection attempt."""

    source_type: str  # "ere", "bates", "transcript", "generic"
    exhibit_id: Optional[str] = None
    relative_page: Optional[int] = None
    total_pages: Optional[int] = None
    bates_number: Optional[str] = None
    confidence: float = 0.0
    detection_method: str = "none"  # "regex", "fuzzy", "position", "fallback"
    raw_match: Optional[str] = None
    is_estimated: bool = False


class HeaderDetector:
    """
    Multi-strategy header detection with fallback chain.

    Detection order (by reliability):
    1. Exact regex match (confidence: 0.95)
    2. Fuzzy regex for OCR errors (confidence: 0.80)
    3. Position-based inference (confidence: 0.60)
    4. Generic fallback (confidence: 0.25)
    """

    # ERE header patterns
    ERE_BAR_PATTERN = re.compile(
        r"(\d+F)\s*[-\u2013\u2014]\s*(\d+)\s*of\s*(\d+)",
        re.IGNORECASE
    )
    ERE_STAMP_PATTERN = re.compile(
        r"EXHIBIT\s*NO\.?\s*(\d+F).*?PAGE:?\s*(\d+)\s*(?:OF\s*(\d+))?",
        re.IGNORECASE | re.DOTALL
    )

    # Bates pattern: 2-5 uppercase letters followed by 6-9 digits
    BATES_PATTERN = re.compile(r"\b([A-Z]{2,5}\d{6,9})\b")

    # Transcript pattern
    TRANSCRIPT_PATTERN = re.compile(
        r"Page\s+(\d+)(?:\s+of\s+(\d+))?",
        re.IGNORECASE
    )

    def __init__(self, min_confidence: float = 0.3):
        """
        Initialize header detector.

        Args:
            min_confidence: Minimum confidence threshold for detection
        """
        self.min_confidence = min_confidence

    def detect(
        self,
        page: PageText,
        exhibit_context: Dict[str, Any]
    ) -> HeaderDetectionResult:
        """
        Detect header info using fallback chain.

        Args:
            page: PageText with content to analyze
            exhibit_context: Dict with exhibit_id, exhibit_start, exhibit_end, total_pages

        Returns:
            HeaderDetectionResult with detected info and confidence
        """
        strategies = [
            self._try_ere_bar,
            self._try_ere_stamp,
            self._try_bates,
            self._try_transcript,
            self._try_position_inference,
            self._fallback,
        ]

        for strategy in strategies:
            result = strategy(page, exhibit_context)
            if result.confidence >= self.min_confidence:
                return result

        return self._fallback(page, exhibit_context)

    def _try_ere_bar(
        self,
        page: PageText,
        exhibit_context: Dict
    ) -> HeaderDetectionResult:
        """Try ERE blue bar format: '25F - 33 of 74'."""
        match = self.ERE_BAR_PATTERN.search(page.text[:500])  # Check first 500 chars
        if match:
            return HeaderDetectionResult(
                source_type="ere",
                exhibit_id=match.group(1).upper(),
                relative_page=int(match.group(2)),
                total_pages=int(match.group(3)),
                confidence=0.95,
                detection_method="regex",
                raw_match=match.group(0),
                is_estimated=False,
            )
        return HeaderDetectionResult(source_type="none", confidence=0.0)

    def _try_ere_stamp(
        self,
        page: PageText,
        exhibit_context: Dict
    ) -> HeaderDetectionResult:
        """Try ERE stamp format: 'EXHIBIT NO. 25F / PAGE: 33 OF 74'."""
        match = self.ERE_STAMP_PATTERN.search(page.text)
        if match:
            total = int(match.group(3)) if match.group(3) else None
            return HeaderDetectionResult(
                source_type="ere",
                exhibit_id=match.group(1).upper(),
                relative_page=int(match.group(2)),
                total_pages=total,
                confidence=0.90,
                detection_method="regex",
                raw_match=match.group(0),
                is_estimated=False,
            )
        return HeaderDetectionResult(source_type="none", confidence=0.0)

    def _try_bates(
        self,
        page: PageText,
        exhibit_context: Dict
    ) -> HeaderDetectionResult:
        """Try Bates stamp format: 'ABC000123'."""
        match = self.BATES_PATTERN.search(page.text[:500])
        if match:
            return HeaderDetectionResult(
                source_type="bates",
                bates_number=match.group(1),
                confidence=0.85,
                detection_method="regex",
                raw_match=match.group(0),
                is_estimated=False,
            )
        return HeaderDetectionResult(source_type="none", confidence=0.0)

    def _try_transcript(
        self,
        page: PageText,
        exhibit_context: Dict
    ) -> HeaderDetectionResult:
        """Try transcript format: 'Page 45 of 120'."""
        match = self.TRANSCRIPT_PATTERN.search(page.text[:500])
        if match:
            total = int(match.group(2)) if match.group(2) else None
            return HeaderDetectionResult(
                source_type="transcript",
                relative_page=int(match.group(1)),
                total_pages=total,
                confidence=0.80,
                detection_method="regex",
                raw_match=match.group(0),
                is_estimated=False,
            )
        return HeaderDetectionResult(source_type="none", confidence=0.0)

    def _try_position_inference(
        self,
        page: PageText,
        exhibit_context: Dict
    ) -> HeaderDetectionResult:
        """Infer page from position within exhibit bounds."""
        if not exhibit_context:
            return HeaderDetectionResult(source_type="none", confidence=0.0)

        exhibit_start = exhibit_context.get("exhibit_start", 0)
        exhibit_id = exhibit_context.get("exhibit_id", "")

        if exhibit_start and page.absolute_page >= exhibit_start:
            relative = page.absolute_page - exhibit_start + 1
            return HeaderDetectionResult(
                source_type="ere" if exhibit_id else "generic",
                exhibit_id=exhibit_id or None,
                relative_page=relative,
                total_pages=exhibit_context.get("total_pages"),
                confidence=0.60,
                detection_method="position",
                is_estimated=True,
            )
        return HeaderDetectionResult(source_type="none", confidence=0.0)

    def _fallback(
        self,
        page: PageText,
        exhibit_context: Dict
    ) -> HeaderDetectionResult:
        """Fallback when no pattern detected."""
        return HeaderDetectionResult(
            source_type="generic",
            exhibit_id=exhibit_context.get("exhibit_id") if exhibit_context else None,
            relative_page=None,
            confidence=0.25,
            detection_method="fallback",
            is_estimated=True,
        )
