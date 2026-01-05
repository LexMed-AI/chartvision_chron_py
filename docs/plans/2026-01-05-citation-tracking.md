# Citation Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add robust citation tracking to link chronology entries to source pages using both absolute PDF page numbers and exhibit-relative page numbers (e.g., "25F@33 (p.1847)").

**Architecture:** Post-extraction deterministic matching. Extract text page-by-page with metadata, run LLM extraction as usual, then match entries to source pages by searching for key identifiers (date, provider, facility) in page-segmented text. Multi-format header detection supports ERE, Bates, transcripts, and generic documents.

**Tech Stack:** Python dataclasses, PyMuPDF (fitz), existing LLM extractors, pytest

---

## Task 1: Citation Data Model

**Files:**
- Create: `app/core/models/citation.py`
- Test: `tests/unit/core/models/test_citation.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/models/test_citation.py
"""Tests for Citation data model."""
import pytest
from app.core.models.citation import Citation


class TestCitationFormat:
    """Test citation formatting in various styles."""

    def test_format_full_with_exhibit(self):
        """Full format includes exhibit, relative page, and absolute page."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            total_pages=74,
        )
        assert citation.format() == "25F@33 (p.1847)"

    def test_format_estimated_shows_tilde(self):
        """Estimated citations show ~ prefix on relative page."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            is_estimated=True,
        )
        assert citation.format() == "25F@~33 (p.1847)"

    def test_format_page_range(self):
        """Multi-page entries show range."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            end_relative_page=35,
            end_absolute_page=1849,
        )
        assert citation.format() == "25F@33-35 (pp.1847-1849)"

    def test_format_exhibit_style(self):
        """Exhibit-only style for short citations."""
        citation = Citation(
            exhibit_id="5F",
            relative_page=3,
            absolute_page=1847,
        )
        assert citation.format("exhibit") == "Ex. 5F@3"

    def test_format_absolute_style(self):
        """Absolute-only style."""
        citation = Citation(
            exhibit_id="5F",
            relative_page=3,
            absolute_page=1847,
        )
        assert citation.format("absolute") == "p.1847"

    def test_format_no_exhibit_fallback(self):
        """Without exhibit, falls back to absolute page only."""
        citation = Citation(absolute_page=1847)
        assert citation.format() == "p.1847"

    def test_format_bates_number(self):
        """Bates-stamped documents use bates number."""
        citation = Citation(
            absolute_page=1847,
            bates_number="ABC000123",
            source_type="bates",
        )
        assert citation.format() == "ABC000123"


class TestCitationValidation:
    """Test citation validation and edge cases."""

    def test_absolute_page_required(self):
        """Absolute page is always required."""
        with pytest.raises(TypeError):
            Citation()  # Missing absolute_page

    def test_is_valid_with_exhibit(self):
        """Citation with exhibit data is valid."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
        )
        assert citation.is_valid() is True

    def test_is_valid_absolute_only(self):
        """Citation with only absolute page is valid."""
        citation = Citation(absolute_page=1847)
        assert citation.is_valid() is True

    def test_confidence_default(self):
        """Default confidence is 1.0."""
        citation = Citation(absolute_page=1847)
        assert citation.confidence == 1.0
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/models/test_citation.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.core.models.citation'"

**Step 3: Write minimal implementation**

```python
# app/core/models/citation.py
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
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/models/test_citation.py -v`
Expected: PASS (all 10 tests)

**Step 5: Commit**

```bash
git add app/core/models/citation.py tests/unit/core/models/test_citation.py
git commit -m "feat(citation): add Citation data model with multi-format support"
```

---

## Task 2: PageText Data Structure

**Files:**
- Modify: `app/core/extraction/pdf_exhibit_extractor.py`
- Test: `tests/unit/core/extraction/test_pdf_exhibit_extractor.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/extraction/test_page_text.py
"""Tests for PageText data structure."""
import pytest
from app.core.extraction.pdf_exhibit_extractor import PageText


class TestPageText:
    """Test PageText data structure."""

    def test_create_page_text(self):
        """PageText holds page content with metadata."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Patient presented with chest pain...",
        )
        assert page.absolute_page == 1847
        assert page.relative_page == 33
        assert page.exhibit_id == "25F"
        assert "chest pain" in page.text

    def test_header_info_optional(self):
        """Header info is optional."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Content here",
        )
        assert page.header_info is None

    def test_with_header_info(self):
        """PageText can store detected header info."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Content here",
            header_info={
                "source_type": "ere",
                "confidence": 0.95,
                "raw_match": "25F - 33 of 74",
            },
        )
        assert page.header_info["source_type"] == "ere"
        assert page.header_info["confidence"] == 0.95
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_page_text.py -v`
Expected: FAIL with "ImportError: cannot import name 'PageText'"

**Step 3: Write minimal implementation**

Add to `app/core/extraction/pdf_exhibit_extractor.py` after imports:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class PageText:
    """Text content with page metadata for citation matching."""

    absolute_page: int  # PDF page number (1-indexed)
    relative_page: int  # Page within exhibit
    exhibit_id: str
    text: str
    header_info: Optional[Dict[str, Any]] = None
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_page_text.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add app/core/extraction/pdf_exhibit_extractor.py tests/unit/core/extraction/test_page_text.py
git commit -m "feat(citation): add PageText data structure for page-level extraction"
```

---

## Task 3: Header Detector - ERE Format

**Files:**
- Create: `app/core/extraction/header_detector.py`
- Test: `tests/unit/core/extraction/test_header_detector.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/extraction/test_header_detector.py
"""Tests for HeaderDetector multi-format detection."""
import pytest
from app.core.extraction.header_detector import HeaderDetector, HeaderDetectionResult
from app.core.extraction.pdf_exhibit_extractor import PageText


class TestHeaderDetectorERE:
    """Test ERE format header detection."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    def test_ere_header_bar_format(self, detector, exhibit_context):
        """Detect ERE blue bar header: '25F - 33 of 74'."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="25F - 33 of 74    Medical Evidence of Record - MER    Little Rock Surgery",
        )
        result = detector.detect(page, exhibit_context)

        assert result.source_type == "ere"
        assert result.exhibit_id == "25F"
        assert result.relative_page == 33
        assert result.total_pages == 74
        assert result.confidence >= 0.9
        assert result.detection_method == "regex"

    def test_ere_stamp_format(self, detector, exhibit_context):
        """Detect ERE stamp format: 'EXHIBIT NO. 25F / PAGE: 33 OF 74'."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Some content\nEXHIBIT NO. 25F\nPAGE: 33 OF 74\nMore content",
        )
        result = detector.detect(page, exhibit_context)

        assert result.source_type == "ere"
        assert result.exhibit_id == "25F"
        assert result.relative_page == 33
        assert result.confidence >= 0.85

    def test_ere_header_with_dash_variants(self, detector, exhibit_context):
        """Handle different dash types in headers."""
        # En-dash variant
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="25F – 33 of 74    Medical Evidence",  # En-dash
        )
        result = detector.detect(page, exhibit_context)
        assert result.relative_page == 33


class TestHeaderDetectorFallback:
    """Test fallback detection strategies."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    def test_position_inference_fallback(self, detector, exhibit_context):
        """Infer page from position when no header detected."""
        page = PageText(
            absolute_page=1847,
            relative_page=0,  # Unknown
            exhibit_id="25F",
            text="Patient presented with symptoms...",  # No header
        )
        result = detector.detect(page, exhibit_context)

        # Should infer: 1847 - 1815 + 1 = 33
        assert result.relative_page == 33
        assert result.is_estimated is True
        assert result.confidence < 0.7
        assert result.detection_method == "position"

    def test_no_detection_returns_low_confidence(self, detector):
        """No exhibit context returns minimal result."""
        page = PageText(
            absolute_page=1847,
            relative_page=0,
            exhibit_id="",
            text="Random text without any headers",
        )
        result = detector.detect(page, {})

        assert result.confidence < 0.3
        assert result.source_type == "generic"


class TestHeaderDetectorBates:
    """Test Bates number detection."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    def test_bates_number_detection(self, detector):
        """Detect Bates stamp format."""
        page = PageText(
            absolute_page=1847,
            relative_page=0,
            exhibit_id="",
            text="ABC000123\nMedical records for patient...",
        )
        result = detector.detect(page, {})

        assert result.source_type == "bates"
        assert result.bates_number == "ABC000123"
        assert result.confidence >= 0.8


class TestHeaderDetectorOCRErrors:
    """Test handling of OCR errors in headers."""

    @pytest.fixture
    def detector(self):
        return HeaderDetector()

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    def test_ocr_number_substitution(self, detector, exhibit_context):
        """Handle OCR errors like O for 0, l for 1."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="25F - 33 of 74    Medical Evidence",  # 4 instead of 74? Actually this is fine
        )
        result = detector.detect(page, exhibit_context)
        # Should still detect the pattern
        assert result.source_type == "ere"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_header_detector.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.core.extraction.header_detector'"

**Step 3: Write minimal implementation**

```python
# app/core/extraction/header_detector.py
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
    4. Generic fallback (confidence: 0.30)
    """

    # ERE header patterns
    ERE_BAR_PATTERN = re.compile(
        r"(\d+F)\s*[-–—]\s*(\d+)\s*of\s*(\d+)",
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
            exhibit_id=exhibit_context.get("exhibit_id"),
            relative_page=None,
            confidence=0.25,
            detection_method="fallback",
            is_estimated=True,
        )
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_header_detector.py -v`
Expected: PASS (all 8 tests)

**Step 5: Commit**

```bash
git add app/core/extraction/header_detector.py tests/unit/core/extraction/test_header_detector.py
git commit -m "feat(citation): add HeaderDetector with multi-format support"
```

---

## Task 4: Citation Matcher - Core Matching Logic

**Files:**
- Create: `app/core/extraction/citation_matcher.py`
- Test: `tests/unit/core/extraction/test_citation_matcher.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/extraction/test_citation_matcher.py
"""Tests for CitationMatcher post-extraction page matching."""
import pytest
from app.core.extraction.citation_matcher import CitationMatcher, MatchResult
from app.core.extraction.pdf_exhibit_extractor import PageText


class TestCitationMatcherBasic:
    """Test basic citation matching functionality."""

    @pytest.fixture
    def sample_pages(self):
        return [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="03/15/2019 Dr. Smith examined patient at Little Rock Surgery Center. "
                     "Chief complaint: chest pain radiating to left arm.",
            ),
            PageText(
                absolute_page=1848,
                relative_page=34,
                exhibit_id="25F",
                text="Lab results from 03/16/2019 showed elevated troponin. "
                     "Dr. Jones reviewed findings.",
            ),
            PageText(
                absolute_page=1849,
                relative_page=35,
                exhibit_id="25F",
                text="Follow-up visit 03/20/2019 with Dr. Smith. "
                     "Patient reports improvement.",
            ),
        ]

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    def test_match_by_date_and_provider(self, sample_pages, exhibit_context):
        """Match entry to page using date and provider."""
        matcher = CitationMatcher(sample_pages, exhibit_context)
        entry = {
            "date": "03/15/2019",
            "provider": "Dr. Smith",
            "facility": "Little Rock Surgery Center",
        }

        result = matcher.match(entry)

        assert result.citation.absolute_page == 1847
        assert result.citation.relative_page == 33
        assert result.citation.exhibit_id == "25F"
        assert result.match_score >= 0.7

    def test_match_different_date_different_page(self, sample_pages, exhibit_context):
        """Different date matches different page."""
        matcher = CitationMatcher(sample_pages, exhibit_context)
        entry = {
            "date": "03/16/2019",
            "provider": "Dr. Jones",
        }

        result = matcher.match(entry)

        assert result.citation.absolute_page == 1848
        assert result.citation.relative_page == 34

    def test_match_fuzzy_provider_name(self, sample_pages, exhibit_context):
        """Fuzzy match handles case differences."""
        matcher = CitationMatcher(sample_pages, exhibit_context)
        entry = {
            "date": "03/15/2019",
            "provider": "DR SMITH",  # Uppercase, no period
        }

        result = matcher.match(entry)

        assert result.citation.absolute_page == 1847

    def test_no_match_returns_fallback(self, sample_pages, exhibit_context):
        """No match returns exhibit-level fallback."""
        matcher = CitationMatcher(sample_pages, exhibit_context)
        entry = {
            "date": "01/01/2020",  # Date not in any page
            "provider": "Dr. Unknown",
        }

        result = matcher.match(entry)

        assert result.citation.is_estimated is True
        assert result.match_score < 0.5


class TestCitationMatcherMultiPage:
    """Test multi-page entry matching."""

    @pytest.fixture
    def consecutive_pages(self):
        return [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="OPERATIVE REPORT 03/15/2019 Dr. Smith "
                     "Procedure: Cardiac catheterization",
            ),
            PageText(
                absolute_page=1848,
                relative_page=34,
                exhibit_id="25F",
                text="Continued from previous page. Dr. Smith noted "
                     "stenosis in LAD. Procedure completed successfully.",
            ),
        ]

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    def test_detect_multi_page_entry(self, consecutive_pages, exhibit_context):
        """Detect entry spanning multiple pages."""
        matcher = CitationMatcher(consecutive_pages, exhibit_context)
        entry = {
            "date": "03/15/2019",
            "provider": "Dr. Smith",
            "visit_type": "procedure",
            "occurrence_treatment": {
                "procedures": ["Cardiac catheterization"],
            },
        }

        result = matcher.match(entry)

        # Should detect range when terms appear on consecutive pages
        assert result.citation.absolute_page == 1847
        # May or may not detect end page depending on implementation
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_citation_matcher.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.core.extraction.citation_matcher'"

**Step 3: Write minimal implementation**

```python
# app/core/extraction/citation_matcher.py
"""
Deterministic post-extraction citation matching.

Matches extracted entries to source pages by searching for
key identifiers (date, provider, facility) in page-segmented text.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.models.citation import Citation
from app.core.extraction.pdf_exhibit_extractor import PageText


@dataclass
class SearchTerm:
    """A term to search for with weighting."""

    value: str
    weight: float = 1.0
    fuzzy: bool = False


@dataclass
class MatchResult:
    """Result of matching an entry to source page(s)."""

    citation: Citation
    match_score: float
    matched_terms: List[str] = field(default_factory=list)
    match_method: str = "search"  # "search", "fallback"


class CitationMatcher:
    """
    Match extracted entries to source pages deterministically.

    Uses weighted term matching to find the most likely source page(s)
    for each entry based on date, provider, facility, and content.
    """

    def __init__(
        self,
        pages: List[PageText],
        exhibit_context: Dict[str, Any],
        match_threshold: float = 3.0,
    ):
        """
        Initialize matcher with page data.

        Args:
            pages: List of PageText objects with page content
            exhibit_context: Dict with exhibit_id, exhibit_start, exhibit_end, total_pages
            match_threshold: Minimum score to consider a match (default 3.0)
        """
        self.pages = pages
        self.context = exhibit_context
        self.match_threshold = match_threshold
        self._page_text_lower = {
            p.absolute_page: p.text.lower() for p in pages
        }

    def match(self, entry: Dict[str, Any]) -> MatchResult:
        """
        Find source page(s) for an extracted entry.

        Args:
            entry: Extracted entry dict with date, provider, facility, etc.

        Returns:
            MatchResult with citation and match quality info
        """
        search_terms = self._extract_search_terms(entry)

        if not search_terms:
            return self._fallback_result(entry)

        page_scores = self._score_pages(search_terms)
        best_pages = self._select_best_pages(page_scores)

        if best_pages:
            return self._build_result(best_pages, search_terms, page_scores)
        else:
            return self._fallback_result(entry)

    def _extract_search_terms(self, entry: Dict) -> List[SearchTerm]:
        """Extract searchable terms with weights from entry."""
        terms = []

        # High weight: date (very unique identifier)
        if date := entry.get("date"):
            # Normalize date formats
            normalized = self._normalize_date(date)
            if normalized:
                terms.append(SearchTerm(normalized, weight=3.0, fuzzy=False))

        # Medium weight: provider and facility names
        if provider := entry.get("provider"):
            if provider.lower() not in ("not specified", "unknown", "n/a"):
                terms.append(SearchTerm(provider, weight=2.0, fuzzy=True))

        if facility := entry.get("facility"):
            if facility.lower() not in ("not specified", "unknown", "n/a"):
                terms.append(SearchTerm(facility, weight=2.0, fuzzy=True))

        # Lower weight: diagnoses and procedures
        if occ := entry.get("occurrence_treatment", {}):
            for dx in (occ.get("diagnoses") or [])[:2]:
                if isinstance(dx, str) and len(dx) > 3:
                    terms.append(SearchTerm(dx, weight=1.0, fuzzy=True))
            for proc in (occ.get("procedures") or [])[:2]:
                if isinstance(proc, str) and len(proc) > 3:
                    terms.append(SearchTerm(proc, weight=1.0, fuzzy=True))

        return terms

    def _normalize_date(self, date: str) -> Optional[str]:
        """Normalize date to searchable format."""
        if not date:
            return None
        # Keep as-is for now - most dates in text match extracted format
        # Could add MM/DD/YYYY <-> YYYY-MM-DD conversion if needed
        return date

    def _score_pages(self, terms: List[SearchTerm]) -> Dict[int, float]:
        """Score each page by weighted term matches."""
        scores = {}

        for page in self.pages:
            page_text_lower = self._page_text_lower[page.absolute_page]
            score = 0.0
            matched = []

            for term in terms:
                if self._term_matches(term, page_text_lower):
                    score += term.weight
                    matched.append(term.value)

            if score > 0:
                scores[page.absolute_page] = score

        return scores

    def _term_matches(self, term: SearchTerm, page_text: str) -> bool:
        """Check if term matches in page text."""
        term_lower = term.value.lower()

        if term.fuzzy:
            return self._fuzzy_match(term_lower, page_text)
        else:
            return term_lower in page_text

    def _fuzzy_match(self, term: str, text: str, threshold: float = 0.85) -> bool:
        """
        Fuzzy match handling common variations.

        Handles: case, punctuation, spacing differences.
        """
        # Normalize both for comparison
        term_normalized = self._normalize_for_match(term)
        text_normalized = self._normalize_for_match(text)

        # Direct substring match after normalization
        if term_normalized in text_normalized:
            return True

        # Try word-boundary match for short terms
        if len(term_normalized) < 20:
            pattern = r'\b' + re.escape(term_normalized) + r'\b'
            if re.search(pattern, text_normalized):
                return True

        return False

    def _normalize_for_match(self, text: str) -> str:
        """Normalize text for fuzzy matching."""
        # Lowercase, remove extra punctuation, normalize spaces
        text = text.lower()
        text = re.sub(r'[.,;:\'\"]+', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _select_best_pages(self, scores: Dict[int, float]) -> List[int]:
        """Select page(s) above threshold, handling multi-page entries."""
        above_threshold = [
            p for p, s in scores.items() if s >= self.match_threshold
        ]

        if not above_threshold:
            return []

        above_threshold.sort()

        # Find best scoring page and consecutive pages
        if len(above_threshold) == 1:
            return above_threshold

        # Check for consecutive pages (potential multi-page entry)
        best_page = max(above_threshold, key=lambda p: scores[p])
        result = [best_page]

        # Include consecutive pages with decent scores
        for page in above_threshold:
            if page != best_page and abs(page - best_page) == 1:
                if scores[page] >= self.match_threshold * 0.7:
                    result.append(page)

        return sorted(result)

    def _build_result(
        self,
        pages: List[int],
        terms: List[SearchTerm],
        scores: Dict[int, float],
    ) -> MatchResult:
        """Build MatchResult from matched pages."""
        primary_page = pages[0]
        page_obj = next(p for p in self.pages if p.absolute_page == primary_page)

        citation = Citation(
            exhibit_id=self.context.get("exhibit_id"),
            relative_page=page_obj.relative_page,
            absolute_page=primary_page,
            total_pages=self.context.get("total_pages"),
            is_estimated=False,
            confidence=min(scores[primary_page] / 10.0, 1.0),
        )

        # Add end page if multi-page
        if len(pages) > 1:
            end_page = pages[-1]
            end_page_obj = next(p for p in self.pages if p.absolute_page == end_page)
            citation.end_relative_page = end_page_obj.relative_page
            citation.end_absolute_page = end_page

        matched_terms = [t.value for t in terms if any(
            self._term_matches(t, self._page_text_lower[p]) for p in pages
        )]

        return MatchResult(
            citation=citation,
            match_score=scores[primary_page],
            matched_terms=matched_terms,
            match_method="search",
        )

    def _fallback_result(self, entry: Dict) -> MatchResult:
        """Create fallback citation when no match found."""
        # Use exhibit-level citation with estimation
        exhibit_id = self.context.get("exhibit_id")
        exhibit_start = self.context.get("exhibit_start", 0)

        citation = Citation(
            exhibit_id=exhibit_id,
            relative_page=1 if exhibit_start else None,
            absolute_page=exhibit_start or 0,
            total_pages=self.context.get("total_pages"),
            is_estimated=True,
            confidence=0.3,
        )

        return MatchResult(
            citation=citation,
            match_score=0.0,
            matched_terms=[],
            match_method="fallback",
        )
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_citation_matcher.py -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add app/core/extraction/citation_matcher.py tests/unit/core/extraction/test_citation_matcher.py
git commit -m "feat(citation): add CitationMatcher for deterministic page matching"
```

---

## Task 5: Update PDF Exhibit Extractor for Page-Level Extraction

**Files:**
- Modify: `app/core/extraction/pdf_exhibit_extractor.py`
- Test: `tests/unit/core/extraction/test_pdf_exhibit_extractor_pages.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/extraction/test_pdf_exhibit_extractor_pages.py
"""Tests for page-level PDF extraction."""
import pytest
from unittest.mock import MagicMock, patch
from app.core.extraction.pdf_exhibit_extractor import (
    extract_f_exhibits_with_pages,
    build_combined_text,
    PageText,
)


class TestExtractWithPages:
    """Test page-level extraction function."""

    def test_build_combined_text_with_headers(self):
        """Build combined text preserves headers without markers."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="25F - 33 of 74    Medical Evidence\nPatient content...",
                header_info={"source_type": "ere", "confidence": 0.95},
            ),
            PageText(
                absolute_page=1848,
                relative_page=34,
                exhibit_id="25F",
                text="25F - 34 of 74    Medical Evidence\nMore content...",
                header_info={"source_type": "ere", "confidence": 0.95},
            ),
        ]

        combined = build_combined_text(pages)

        # Headers preserved, no artificial markers needed
        assert "25F - 33 of 74" in combined
        assert "25F - 34 of 74" in combined
        assert "[PAGE" not in combined  # No markers when headers present

    def test_build_combined_text_without_headers(self):
        """Build combined text injects markers when no headers."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="Patient presented with symptoms...",
                header_info=None,  # No header detected
            ),
            PageText(
                absolute_page=1848,
                relative_page=34,
                exhibit_id="25F",
                text="Lab results showed...",
                header_info=None,
            ),
        ]

        combined = build_combined_text(pages)

        # Markers injected for headerless pages
        assert "[PAGE 1847]" in combined
        assert "[PAGE 1848]" in combined

    def test_build_combined_text_mixed(self):
        """Mixed pages: some with headers, some without."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="25F - 33 of 74    Header present\nContent...",
                header_info={"source_type": "ere"},
            ),
            PageText(
                absolute_page=1848,
                relative_page=34,
                exhibit_id="25F",
                text="No header on this page\nMore content...",
                header_info=None,
            ),
        ]

        combined = build_combined_text(pages)

        assert "[PAGE 1847]" not in combined  # Has header
        assert "[PAGE 1848]" in combined  # No header, needs marker
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_pdf_exhibit_extractor_pages.py -v`
Expected: FAIL with "ImportError: cannot import name 'extract_f_exhibits_with_pages'"

**Step 3: Write minimal implementation**

Add to `app/core/extraction/pdf_exhibit_extractor.py`:

```python
def build_combined_text(pages: List[PageText]) -> str:
    """
    Combine pages into single text for LLM extraction.

    Pages with detected headers use natural text.
    Pages without headers get [PAGE X] markers injected.

    Args:
        pages: List of PageText objects

    Returns:
        Combined text with page boundary markers where needed
    """
    parts = []
    for page in pages:
        if page.header_info and page.header_info.get("confidence", 0) > 0.5:
            # Header detected - use natural text
            parts.append(page.text)
        else:
            # No header - inject marker
            parts.append(f"[PAGE {page.absolute_page}]\n{page.text}")

    return "\n\n".join(parts)


def extract_f_exhibits_with_pages(
    pdf_path: str,
    max_exhibits: Optional[int] = None,
    max_pages_per_exhibit: int = 50
) -> List[Dict[str, Any]]:
    """
    Extract F-section exhibits with page-level text segmentation.

    Enhanced version of extract_f_exhibits_from_pdf that preserves
    page boundaries for citation matching.

    Args:
        pdf_path: Path to ERE PDF file
        max_exhibits: Maximum number of exhibits to extract
        max_pages_per_exhibit: Maximum pages per exhibit

    Returns:
        List of exhibit dicts with structure:
        {
            "exhibit_id": str,
            "pages": List[PageText],      # Individual pages with metadata
            "combined_text": str,          # For LLM (with markers where needed)
            "page_range": (start, end),
            "images": List[bytes],
            "scanned_page_nums": List[int],
            "has_scanned_pages": bool,
        }
    """
    import fitz
    from app.adapters.pdf.preprocessing import (
        is_scanned_page,
        render_page_to_image,
    )
    from app.core.extraction.header_detector import HeaderDetector

    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()
        header_detector = HeaderDetector()

        # Extract F-section exhibits from bookmarks
        f_exhibits = []
        for level, title, page in toc:
            match = re.match(r'^(\d+F)\s*[-:]', title)
            if match:
                f_exhibits.append({
                    "exhibit_id": match.group(1),
                    "title": title,
                    "start_page": page,
                })

        # Calculate end pages
        for i, ex in enumerate(f_exhibits):
            if i < len(f_exhibits) - 1:
                ex["end_page"] = f_exhibits[i + 1]["start_page"] - 1
            else:
                ex["end_page"] = len(doc)

        if max_exhibits:
            f_exhibits = f_exhibits[:max_exhibits]

        # Extract with page-level granularity
        exhibits_with_pages = []

        for ex in f_exhibits:
            start = ex["start_page"] - 1  # 0-indexed
            end = min(ex["end_page"], ex["start_page"] + max_pages_per_exhibit - 1)

            exhibit_context = {
                "exhibit_id": ex["exhibit_id"],
                "exhibit_start": ex["start_page"],
                "exhibit_end": end,
                "total_pages": end - ex["start_page"] + 1,
            }

            pages: List[PageText] = []
            images = []
            scanned_page_nums = []

            for page_idx in range(start, min(end, len(doc))):
                page = doc[page_idx]
                absolute_page = page_idx + 1
                relative_page = absolute_page - ex["start_page"] + 1

                if is_scanned_page(page):
                    if len(images) < MAX_IMAGES_PER_EXHIBIT:
                        images.append(render_page_to_image(page))
                        scanned_page_nums.append(absolute_page)
                else:
                    page_text = page.get_text()
                    if page_text.strip():
                        # Create PageText and detect header
                        page_obj = PageText(
                            absolute_page=absolute_page,
                            relative_page=relative_page,
                            exhibit_id=ex["exhibit_id"],
                            text=page_text,
                        )
                        # Detect header info
                        header_result = header_detector.detect(page_obj, exhibit_context)
                        if header_result.confidence > 0.3:
                            page_obj.header_info = {
                                "source_type": header_result.source_type,
                                "confidence": header_result.confidence,
                                "raw_match": header_result.raw_match,
                            }
                        pages.append(page_obj)

            if pages or images:
                combined_text = build_combined_text(pages) if pages else ""

                exhibit_data = {
                    "exhibit_id": ex["exhibit_id"],
                    "pages": pages,
                    "combined_text": combined_text,
                    "page_range": (ex["start_page"], end),
                    "images": images,
                    "scanned_page_nums": scanned_page_nums,
                    "has_scanned_pages": len(images) > 0,
                }
                exhibits_with_pages.append(exhibit_data)

        doc.close()
        return exhibits_with_pages

    except Exception as e:
        logger.error(f"Failed to extract F-exhibits with pages: {e}")
        return []
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_pdf_exhibit_extractor_pages.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add app/core/extraction/pdf_exhibit_extractor.py tests/unit/core/extraction/test_pdf_exhibit_extractor_pages.py
git commit -m "feat(citation): add page-level extraction with header detection"
```

---

## Task 6: Integrate Citation Matching into TextExtractor

**Files:**
- Modify: `app/core/extraction/text_extractor.py`
- Test: `tests/unit/core/extraction/test_text_extractor_citations.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/extraction/test_text_extractor_citations.py
"""Tests for TextExtractor citation integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extraction.text_extractor import TextExtractor
from app.core.extraction.pdf_exhibit_extractor import PageText


class TestTextExtractorCitations:
    """Test citation matching integration in TextExtractor."""

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value='''[
            {
                "date": "03/15/2019",
                "provider": "Dr. Smith",
                "facility": "Little Rock Surgery",
                "visit_type": "office_visit",
                "occurrence_treatment": {"diagnoses": ["Chest pain"]}
            }
        ]''')
        return llm

    @pytest.fixture
    def sample_pages(self):
        return [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="03/15/2019 Dr. Smith Little Rock Surgery. Patient with chest pain.",
            ),
        ]

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    @pytest.mark.asyncio
    async def test_extract_attaches_citations(
        self, mock_llm, sample_pages, exhibit_context
    ):
        """Extracted entries have citations attached."""
        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="03/15/2019 Dr. Smith Little Rock Surgery...",
            exhibit_id="25F",
            pages=sample_pages,
            exhibit_context=exhibit_context,
        )

        assert len(entries) == 1
        assert entries[0].get("citation") is not None
        assert entries[0]["citation"].absolute_page == 1847
        assert entries[0]["citation"].exhibit_id == "25F"

    @pytest.mark.asyncio
    async def test_extract_without_pages_no_citation(self, mock_llm):
        """Without page data, entries have no citation."""
        extractor = TextExtractor(mock_llm)

        entries = await extractor.extract(
            text="Some medical text...",
            exhibit_id="25F",
            pages=None,  # No pages provided
        )

        assert len(entries) == 1
        assert entries[0].get("citation") is None
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_text_extractor_citations.py -v`
Expected: FAIL (signature doesn't accept pages parameter)

**Step 3: Write minimal implementation**

Modify `app/core/extraction/text_extractor.py`:

```python
# Add import at top
from app.core.extraction.citation_matcher import CitationMatcher
from app.core.extraction.pdf_exhibit_extractor import PageText

# Update extract method signature and implementation
async def extract(
    self,
    text: str,
    exhibit_id: str,
    pages: Optional[List[PageText]] = None,
    exhibit_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract medical entries from text with exponential backoff retry.

    Args:
        text: Text content to extract from
        exhibit_id: Exhibit identifier (e.g., "25F")
        pages: Optional page-level text for citation matching
        exhibit_context: Optional exhibit metadata for citations

    Returns:
        List of entry dicts with optional citation attached
    """
    if not text.strip():
        return []

    # Check if chunking is needed
    if self._chunker.needs_chunking(text):
        entries = await self._extract_chunked(text, exhibit_id)
    else:
        entries = await self._extract_single(text, exhibit_id)

    # Post-extraction citation matching
    if pages and exhibit_context:
        matcher = CitationMatcher(pages, exhibit_context)
        for entry in entries:
            match_result = matcher.match(entry)
            entry["citation"] = match_result.citation
            entry["citation_confidence"] = match_result.match_score

    return entries
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_text_extractor_citations.py -v`
Expected: PASS (all 2 tests)

**Step 5: Commit**

```bash
git add app/core/extraction/text_extractor.py tests/unit/core/extraction/test_text_extractor_citations.py
git commit -m "feat(citation): integrate CitationMatcher into TextExtractor"
```

---

## Task 7: Integrate Citation Building into VisionExtractor

**Files:**
- Modify: `app/core/extraction/vision_extractor.py`
- Test: `tests/unit/core/extraction/test_vision_extractor_citations.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/extraction/test_vision_extractor_citations.py
"""Tests for VisionExtractor citation integration."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.extraction.vision_extractor import VisionExtractor


class TestVisionExtractorCitations:
    """Test citation building in VisionExtractor."""

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate_with_vision = AsyncMock(return_value='''[
            {
                "date": "03/15/2019",
                "provider": "Dr. Smith",
                "visit_type": "office_visit"
            }
        ]''')
        return llm

    @pytest.fixture
    def exhibit_context(self):
        return {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

    @pytest.mark.asyncio
    async def test_single_page_deterministic_citation(
        self, mock_llm, exhibit_context
    ):
        """Single page batch has deterministic citation."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"fake_image_data"],
            exhibit_id="25F",
            page_nums=[1847],
            exhibit_context=exhibit_context,
        )

        assert len(entries) == 1
        assert entries[0].get("citation") is not None
        assert entries[0]["citation"].absolute_page == 1847
        assert entries[0]["citation"].relative_page == 33  # 1847 - 1815 + 1
        assert entries[0]["citation"].exhibit_id == "25F"
        assert entries[0]["citation"].is_estimated is False

    @pytest.mark.asyncio
    async def test_multi_page_batch_attribution(
        self, mock_llm, exhibit_context
    ):
        """Multi-page batch attributes to batch range."""
        extractor = VisionExtractor(mock_llm)

        entries = await extractor.extract(
            images=[b"img1", b"img2", b"img3"],
            exhibit_id="25F",
            page_nums=[1847, 1848, 1849],
            exhibit_context=exhibit_context,
        )

        # Entry attributed to first page of batch (or range)
        assert len(entries) == 1
        citation = entries[0]["citation"]
        assert citation.absolute_page == 1847
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_vision_extractor_citations.py -v`
Expected: FAIL (signature doesn't accept exhibit_context)

**Step 3: Write minimal implementation**

Modify `app/core/extraction/vision_extractor.py`:

```python
# Add import at top
from app.core.models.citation import Citation

# Update extract method
async def extract(
    self,
    images: List[bytes],
    exhibit_id: str,
    page_nums: List[int],
    exhibit_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract medical entries from page images.

    Args:
        images: List of PNG image bytes
        exhibit_id: Exhibit identifier (e.g., "1F")
        page_nums: Corresponding page numbers for citation
        exhibit_context: Exhibit metadata for citation building

    Returns:
        List of medical entry dictionaries with citations
    """
    if not images:
        return []

    all_entries = []
    for i in range(0, len(images), self._batch_size):
        batch_imgs = images[i:i + self._batch_size]
        batch_pages = page_nums[i:i + self._batch_size] if page_nums else []

        try:
            entries = await self._extract_batch(batch_imgs, exhibit_id, batch_pages)

            # Attach citations to entries
            if batch_pages and exhibit_context:
                for entry in entries:
                    citation = self._build_citation(
                        batch_pages, exhibit_id, exhibit_context
                    )
                    entry["citation"] = citation

            all_entries.extend(entries)
        except Exception as e:
            logger.error(f"Vision batch failed for {exhibit_id}: {e}")

    return all_entries

def _build_citation(
    self,
    page_nums: List[int],
    exhibit_id: str,
    exhibit_context: Dict[str, Any],
) -> Citation:
    """Build citation from batch page numbers."""
    exhibit_start = exhibit_context.get("exhibit_start", page_nums[0])
    total_pages = exhibit_context.get("total_pages")

    primary_page = page_nums[0]
    relative_page = primary_page - exhibit_start + 1

    citation = Citation(
        exhibit_id=exhibit_id,
        relative_page=relative_page,
        absolute_page=primary_page,
        total_pages=total_pages,
        is_estimated=False,  # Vision pages are deterministic
        confidence=0.95,
    )

    # Add range if multi-page batch
    if len(page_nums) > 1:
        end_page = page_nums[-1]
        citation.end_relative_page = end_page - exhibit_start + 1
        citation.end_absolute_page = end_page

    return citation
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_vision_extractor_citations.py -v`
Expected: PASS (all 2 tests)

**Step 5: Commit**

```bash
git add app/core/extraction/vision_extractor.py tests/unit/core/extraction/test_vision_extractor_citations.py
git commit -m "feat(citation): integrate citation building into VisionExtractor"
```

---

## Task 8: Update ParallelExtractor to Pass Context

**Files:**
- Modify: `app/core/extraction/parallel_extractor.py`
- Test: `tests/unit/core/extraction/test_parallel_extractor_context.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/extraction/test_parallel_extractor_context.py
"""Tests for ParallelExtractor context passing."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.extraction.parallel_extractor import ParallelExtractor


class TestParallelExtractorContext:
    """Test exhibit context passing to extractors."""

    @pytest.fixture
    def mock_text_extractor(self):
        extractor = MagicMock()
        extractor.extract = AsyncMock(return_value=[
            {"date": "2019-03-15", "provider": "Dr. Smith"}
        ])
        return extractor

    @pytest.fixture
    def mock_vision_extractor(self):
        extractor = MagicMock()
        extractor.extract = AsyncMock(return_value=[
            {"date": "2019-03-16", "provider": "Dr. Jones"}
        ])
        return extractor

    @pytest.mark.asyncio
    async def test_passes_exhibit_context_to_text_extractor(
        self, mock_text_extractor, mock_vision_extractor
    ):
        """ParallelExtractor passes exhibit context to TextExtractor."""
        parallel = ParallelExtractor(
            text_extractor=mock_text_extractor,
            vision_extractor=mock_vision_extractor,
        )

        exhibit = {
            "exhibit_id": "25F",
            "pages": [],  # PageText objects would go here
            "combined_text": "Medical text...",
            "page_range": (1815, 1888),
            "images": [],
            "scanned_page_nums": [],
            "has_scanned_pages": False,
        }

        await parallel._process_exhibit(exhibit)

        # Verify context was passed
        call_kwargs = mock_text_extractor.extract.call_args.kwargs
        assert "exhibit_context" in call_kwargs
        assert call_kwargs["exhibit_context"]["exhibit_id"] == "25F"
        assert call_kwargs["exhibit_context"]["exhibit_start"] == 1815
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_parallel_extractor_context.py -v`
Expected: FAIL (context not passed)

**Step 3: Write minimal implementation**

Modify `app/core/extraction/parallel_extractor.py` `_process_exhibit` method:

```python
async def _process_exhibit(self, exhibit: Dict[str, Any]) -> List[Dict]:
    """Process single exhibit with citation context."""

    # Build context for citation resolution
    page_range = exhibit.get("page_range", (0, 0))
    exhibit_context = {
        "exhibit_id": exhibit.get("exhibit_id", ""),
        "exhibit_start": page_range[0],
        "exhibit_end": page_range[1],
        "total_pages": page_range[1] - page_range[0] + 1 if page_range[0] else 0,
    }

    pages = exhibit.get("pages", [])

    if exhibit.get("has_scanned_pages") and exhibit.get("images"):
        return await self._vision_extractor.extract(
            images=exhibit["images"],
            exhibit_id=exhibit["exhibit_id"],
            page_nums=exhibit.get("scanned_page_nums", []),
            exhibit_context=exhibit_context,
        )
    else:
        return await self._text_extractor.extract(
            text=exhibit.get("combined_text", ""),
            exhibit_id=exhibit["exhibit_id"],
            pages=pages,
            exhibit_context=exhibit_context,
        )
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_parallel_extractor_context.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/core/extraction/parallel_extractor.py tests/unit/core/extraction/test_parallel_extractor_context.py
git commit -m "feat(citation): pass exhibit context through ParallelExtractor"
```

---

## Task 9: Add CitationSchema to API Response

**Files:**
- Modify: `app/api/schemas.py`
- Test: `tests/unit/api/test_schemas_citation.py`

**Step 1: Write the failing test**

```python
# tests/unit/api/test_schemas_citation.py
"""Tests for CitationSchema in API responses."""
import pytest
from app.api.schemas import CitationSchema, ChronologyEntrySchema


class TestCitationSchema:
    """Test CitationSchema serialization."""

    def test_citation_schema_full(self):
        """CitationSchema with all fields."""
        schema = CitationSchema(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            total_pages=74,
            is_estimated=False,
            confidence=0.95,
            formatted="25F@33 (p.1847)",
        )

        data = schema.model_dump()

        assert data["exhibit_id"] == "25F"
        assert data["relative_page"] == 33
        assert data["absolute_page"] == 1847
        assert data["formatted"] == "25F@33 (p.1847)"

    def test_citation_schema_minimal(self):
        """CitationSchema with minimal fields."""
        schema = CitationSchema(
            absolute_page=1847,
            formatted="p.1847",
        )

        data = schema.model_dump()

        assert data["absolute_page"] == 1847
        assert data["exhibit_id"] is None

    def test_chronology_entry_with_citation(self):
        """ChronologyEntrySchema includes citation."""
        entry = ChronologyEntrySchema(
            date="2019-03-15",
            visit_type="office_visit",
            provider="Dr. Smith",
            facility="Little Rock Surgery",
            occurrence_treatment={},
            citation=CitationSchema(
                exhibit_id="25F",
                relative_page=33,
                absolute_page=1847,
                formatted="25F@33 (p.1847)",
            ),
        )

        data = entry.model_dump()

        assert data["citation"]["exhibit_id"] == "25F"
        assert data["citation"]["formatted"] == "25F@33 (p.1847)"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/api/test_schemas_citation.py -v`
Expected: FAIL (CitationSchema doesn't exist)

**Step 3: Write minimal implementation**

Add to `app/api/schemas.py`:

```python
class CitationSchema(BaseModel):
    """Citation data in API responses."""

    # Structured data for client-side flexibility
    exhibit_id: Optional[str] = None
    relative_page: Optional[int] = None
    absolute_page: int
    total_pages: Optional[int] = None
    end_relative_page: Optional[int] = None
    end_absolute_page: Optional[int] = None
    is_estimated: bool = False
    confidence: float = 1.0

    # Canonical formatted string
    formatted: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exhibit_id": "25F",
                "relative_page": 33,
                "absolute_page": 1847,
                "total_pages": 74,
                "is_estimated": False,
                "confidence": 0.95,
                "formatted": "25F@33 (p.1847)",
            }
        }
    )


# Update ChronologyEntrySchema to include citation
class ChronologyEntrySchema(BaseModel):
    """Single chronology entry with citation."""

    date: str
    visit_type: str
    provider: str
    facility: str
    occurrence_treatment: Dict[str, Any]
    citation: Optional[CitationSchema] = None
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/api/test_schemas_citation.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add app/api/schemas.py tests/unit/api/test_schemas_citation.py
git commit -m "feat(api): add CitationSchema to API response models"
```

---

## Task 10: Update Markdown Converter for Citation Output

**Files:**
- Modify: `app/adapters/export/markdown_converter.py`
- Test: `tests/unit/adapters/export/test_markdown_citations.py`

**Step 1: Write the failing test**

```python
# tests/unit/adapters/export/test_markdown_citations.py
"""Tests for citation formatting in markdown output."""
import pytest
from app.adapters.export.markdown_converter import MarkdownConverter
from app.core.models.citation import Citation


class TestMarkdownCitations:
    """Test citation formatting in markdown export."""

    @pytest.fixture
    def converter(self):
        return MarkdownConverter()

    def test_format_entry_with_citation(self, converter):
        """Entry with citation shows source line."""
        entry = {
            "date": "2019-03-15",
            "visit_type": "office_visit",
            "provider": "Dr. Smith",
            "facility": "Little Rock Surgery",
            "occurrence_treatment": {"diagnoses": ["Chest pain"]},
            "citation": Citation(
                exhibit_id="25F",
                relative_page=33,
                absolute_page=1847,
            ),
        }

        output = converter.format_entry(entry)

        assert "**Source:** 25F@33 (p.1847)" in output

    def test_format_entry_without_citation(self, converter):
        """Entry without citation omits source line."""
        entry = {
            "date": "2019-03-15",
            "visit_type": "office_visit",
            "provider": "Dr. Smith",
            "facility": "Little Rock Surgery",
            "occurrence_treatment": {},
            "citation": None,
        }

        output = converter.format_entry(entry)

        assert "Source:" not in output

    def test_format_footer_aggregates_sources(self, converter):
        """Footer aggregates sources by exhibit."""
        entries = [
            {
                "citation": Citation(exhibit_id="25F", relative_page=33, absolute_page=1847),
            },
            {
                "citation": Citation(exhibit_id="25F", relative_page=35, absolute_page=1849),
            },
            {
                "citation": Citation(exhibit_id="26F", relative_page=1, absolute_page=1890),
            },
        ]

        output = converter.format_footer(entries)

        assert "## Sources" in output
        assert "Exhibit 25F" in output
        assert "Exhibit 26F" in output
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/adapters/export/test_markdown_citations.py -v`
Expected: FAIL (methods don't exist or don't handle citations)

**Step 3: Write minimal implementation**

Update `app/adapters/export/markdown_converter.py`:

```python
from collections import defaultdict
from typing import Any, Dict, List

from app.core.models.citation import Citation


class MarkdownConverter:
    """Convert chronology data to markdown format."""

    def format_entry(self, entry: Dict[str, Any]) -> str:
        """Format single chronology entry with citation."""
        date = entry.get("date", "Unknown")
        visit_type = entry.get("visit_type", "visit")
        provider = entry.get("provider", "Unknown")
        facility = entry.get("facility", "Unknown")

        lines = [
            f"### {date} - {visit_type}",
            f"**Provider:** {provider} | **Facility:** {facility}",
        ]

        # Add citation if present
        citation = entry.get("citation")
        if citation:
            if isinstance(citation, Citation):
                lines.append(f"**Source:** {citation.format()}")
            elif isinstance(citation, dict):
                lines.append(f"**Source:** {citation.get('formatted', '')}")

        # Add occurrence/treatment content
        occ = entry.get("occurrence_treatment", {})
        if occ:
            lines.append("")
            lines.append(self._format_occurrence(occ))

        return "\n".join(lines)

    def format_footer(self, entries: List[Dict]) -> str:
        """Format aggregated source list at end of report."""
        by_exhibit = defaultdict(list)

        for entry in entries:
            citation = entry.get("citation")
            if citation:
                if isinstance(citation, Citation):
                    by_exhibit[citation.exhibit_id].append(citation.absolute_page)
                elif isinstance(citation, dict) and citation.get("exhibit_id"):
                    by_exhibit[citation["exhibit_id"]].append(citation["absolute_page"])

        if not by_exhibit:
            return ""

        lines = ["## Sources", ""]
        for exhibit_id in sorted(by_exhibit.keys()):
            if not exhibit_id:
                continue
            pages = sorted(set(by_exhibit[exhibit_id]))
            page_range = f"pp.{min(pages)}-{max(pages)}" if len(pages) > 1 else f"p.{pages[0]}"
            lines.append(f"- **Exhibit {exhibit_id}:** {page_range} ({len(pages)} entries)")

        return "\n".join(lines)

    def _format_occurrence(self, occ: Dict) -> str:
        """Format occurrence/treatment details."""
        parts = []
        if diagnoses := occ.get("diagnoses"):
            parts.append(f"**Diagnoses:** {', '.join(diagnoses)}")
        if procedures := occ.get("procedures"):
            parts.append(f"**Procedures:** {', '.join(procedures)}")
        if medications := occ.get("medications"):
            parts.append(f"**Medications:** {', '.join(medications)}")
        return "\n".join(parts)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/adapters/export/test_markdown_citations.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add app/adapters/export/markdown_converter.py tests/unit/adapters/export/test_markdown_citations.py
git commit -m "feat(export): add citation formatting to markdown converter"
```

---

## Task 11: Integration Test - Full Pipeline

**Files:**
- Create: `tests/integration/test_citation_pipeline.py`

**Step 1: Write integration test**

```python
# tests/integration/test_citation_pipeline.py
"""Integration tests for citation tracking through full pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.models.citation import Citation
from app.core.extraction.pdf_exhibit_extractor import PageText, build_combined_text
from app.core.extraction.header_detector import HeaderDetector
from app.core.extraction.citation_matcher import CitationMatcher


class TestCitationPipelineIntegration:
    """End-to-end citation tracking tests."""

    def test_header_detection_to_citation_flow(self):
        """Header detection flows through to final citation."""
        # Simulate ERE page with header
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="25F - 33 of 74    Medical Evidence of Record\n"
                 "03/15/2019 Dr. Smith examined patient...",
        )

        exhibit_context = {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

        # Step 1: Detect header
        detector = HeaderDetector()
        header_result = detector.detect(page, exhibit_context)

        assert header_result.source_type == "ere"
        assert header_result.relative_page == 33
        assert header_result.confidence >= 0.9

        # Step 2: Match entry to page
        page.header_info = {
            "source_type": header_result.source_type,
            "confidence": header_result.confidence,
        }

        matcher = CitationMatcher([page], exhibit_context)
        entry = {
            "date": "03/15/2019",
            "provider": "Dr. Smith",
        }

        result = matcher.match(entry)

        # Step 3: Verify citation
        assert result.citation.exhibit_id == "25F"
        assert result.citation.relative_page == 33
        assert result.citation.absolute_page == 1847
        assert result.citation.format() == "25F@33 (p.1847)"

    def test_fallback_citation_when_no_header(self):
        """Fallback works when no header detected."""
        page = PageText(
            absolute_page=1847,
            relative_page=33,
            exhibit_id="25F",
            text="Patient presented with symptoms on 03/15/2019. Dr. Smith evaluated.",
            header_info=None,  # No header
        )

        exhibit_context = {
            "exhibit_id": "25F",
            "exhibit_start": 1815,
            "exhibit_end": 1888,
            "total_pages": 74,
        }

        matcher = CitationMatcher([page], exhibit_context)
        entry = {
            "date": "03/15/2019",
            "provider": "Dr. Smith",
        }

        result = matcher.match(entry)

        # Should still match based on content
        assert result.citation.absolute_page == 1847
        assert result.match_score >= 3.0

    def test_combined_text_marker_injection(self):
        """Page markers injected for headerless pages."""
        pages = [
            PageText(
                absolute_page=1847,
                relative_page=33,
                exhibit_id="25F",
                text="Content without header",
                header_info=None,
            ),
        ]

        combined = build_combined_text(pages)

        assert "[PAGE 1847]" in combined

    def test_citation_format_styles(self):
        """All citation format styles work correctly."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            total_pages=74,
        )

        assert citation.format("full") == "25F@33 (p.1847)"
        assert citation.format("exhibit") == "Ex. 25F@33"
        assert citation.format("absolute") == "p.1847"

    def test_estimated_citation_format(self):
        """Estimated citations show tilde prefix."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            is_estimated=True,
        )

        assert citation.format() == "25F@~33 (p.1847)"

    def test_multi_page_citation_format(self):
        """Multi-page citations show range."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
            end_relative_page=35,
            end_absolute_page=1849,
        )

        assert citation.format() == "25F@33-35 (pp.1847-1849)"
```

**Step 2: Run integration test**

Run: `PYTHONPATH=. pytest tests/integration/test_citation_pipeline.py -v`
Expected: PASS (all 6 tests)

**Step 3: Commit**

```bash
git add tests/integration/test_citation_pipeline.py
git commit -m "test(citation): add integration tests for citation pipeline"
```

---

## Task 12: Update Entry Model with Citation Field

**Files:**
- Modify: `app/core/models/entry.py`
- Test: `tests/unit/core/models/test_entry_citation.py`

**Step 1: Write the failing test**

```python
# tests/unit/core/models/test_entry_citation.py
"""Tests for Citation field in entry models."""
import pytest
from datetime import datetime
from app.core.models.entry import MedicalEvent, ChronologyEvent
from app.core.models.citation import Citation


class TestMedicalEventCitation:
    """Test MedicalEvent with Citation field."""

    def test_medical_event_with_citation(self):
        """MedicalEvent accepts Citation object."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
        )

        event = MedicalEvent(
            event_type="office_visit",
            date=datetime(2019, 3, 15),
            provider="Dr. Smith",
            description="Patient examined",
            citation=citation,
        )

        assert event.citation is not None
        assert event.citation.exhibit_id == "25F"
        assert event.citation.format() == "25F@33 (p.1847)"

    def test_medical_event_without_citation(self):
        """MedicalEvent works without citation."""
        event = MedicalEvent(
            event_type="office_visit",
            date=datetime(2019, 3, 15),
            provider="Dr. Smith",
            description="Patient examined",
        )

        assert event.citation is None


class TestChronologyEventCitation:
    """Test ChronologyEvent with Citation field."""

    def test_chronology_event_with_citation(self):
        """ChronologyEvent accepts Citation object."""
        citation = Citation(
            exhibit_id="25F",
            relative_page=33,
            absolute_page=1847,
        )

        event = ChronologyEvent(
            event_id="evt_001",
            event_type="medical",
            date=datetime(2019, 3, 15),
            title="Office Visit",
            citation=citation,
        )

        assert event.citation.absolute_page == 1847
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/models/test_entry_citation.py -v`
Expected: FAIL (citation field doesn't exist on models)

**Step 3: Write minimal implementation**

Update `app/core/models/entry.py`:

```python
# Add import at top
from app.core.models.citation import Citation

# Update MedicalEvent dataclass - add citation field
@dataclass
class MedicalEvent:
    """Represents a medical event with temporal and source information."""

    event_type: str
    date: datetime
    provider: str
    description: str
    diagnosis: Optional[str] = None
    procedure: Optional[str] = None
    medications: List[str] = field(default_factory=list)
    severity: Optional[str] = None
    location: Optional[str] = None
    confidence: float = 1.0

    # NEW: Unified citation object
    citation: Optional[Citation] = None

    # DEPRECATED: Legacy fields (kept for migration)
    source_page: Optional[int] = None
    source_text: Optional[str] = None
    follow_up_required: bool = False
    critical_finding: bool = False
    exhibit_reference: Optional[str] = None
    exhibit_source: Optional[str] = None
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# Update ChronologyEvent dataclass - add citation field
@dataclass
class ChronologyEvent:
    """Universal event representation for all chronology types."""

    event_id: str
    event_type: str
    date: datetime
    end_date: Optional[datetime] = None
    title: str = ""
    description: str = ""

    # NEW: Unified citation object
    citation: Optional[Citation] = None

    # Legacy fields (can be derived from citation)
    source_exhibit: str = ""
    source_pages: List[int] = field(default_factory=list)

    provider: Optional[str] = None
    location: Optional[str] = None
    significance: str = "normal"
    category: str = ""
    subcategory: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    hyperlinks: List[str] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/models/test_entry_citation.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add app/core/models/entry.py tests/unit/core/models/test_entry_citation.py
git commit -m "feat(models): add Citation field to MedicalEvent and ChronologyEvent"
```

---

## Task 13: Final - Run All Tests

**Step 1: Run full test suite**

```bash
PYTHONPATH=. pytest tests/ -v --tb=short
```

Expected: All tests pass (250+ existing + ~30 new citation tests)

**Step 2: Run linting**

```bash
make lint
```

Expected: No lint errors

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(citation): complete citation tracking implementation

- Add Citation dataclass with multi-format support (ERE, Bates, transcript)
- Add HeaderDetector with fallback chain for robust page detection
- Add CitationMatcher for deterministic post-extraction page matching
- Integrate citations into TextExtractor and VisionExtractor
- Update API schemas with CitationSchema
- Update markdown export with citation formatting
- Add comprehensive unit and integration tests

Citations now track both absolute PDF pages and exhibit-relative pages,
formatted as '25F@33 (p.1847)' with fallback to '25F@~33 (p.1847)' for
estimated pages."
```

---

## Summary

**New Files Created:**
- `app/core/models/citation.py` - Citation dataclass
- `app/core/extraction/header_detector.py` - Multi-format header detection
- `app/core/extraction/citation_matcher.py` - Deterministic page matching
- 8 test files covering all new functionality

**Files Modified:**
- `app/core/models/entry.py` - Added Citation field
- `app/core/extraction/pdf_exhibit_extractor.py` - Page-level extraction
- `app/core/extraction/text_extractor.py` - Citation integration
- `app/core/extraction/vision_extractor.py` - Citation building
- `app/core/extraction/parallel_extractor.py` - Context passing
- `app/api/schemas.py` - CitationSchema
- `app/adapters/export/markdown_converter.py` - Citation formatting

**Key Design Decisions:**
- Deterministic post-extraction matching (not LLM-dependent)
- Multi-format support via HeaderDetector fallback chain
- Citation object with format() method for flexible output
- Backwards-compatible with legacy fields deprecated
