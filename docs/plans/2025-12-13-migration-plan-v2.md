# Migration Plan v2: Services → Hexagonal Architecture

**Date:** 2025-12-13
**Status:** Draft
**Goal:** Complete Phase 4-5 of hexagonal architecture migration

---

## Guiding Principles

1. **Files < 350 lines** (target 100-300)
2. **Domain logic in core/** - business rules, ERE/SSA knowledge
3. **Infrastructure in adapters/** - PDF library, HTTP clients, external APIs
4. **Test**: "Would this exist if we changed our PDF library?"
   - No → `core/`
   - Yes → `adapters/`

---

## Current State

### Files Violating Architecture

```
core/extraction/engine.py:83
  → from app.services.llm.llm_manager import LLMManager

core/extraction/recovery_handler.py:17
  → from app.services.pdf.preprocessing import is_content_sparse

core/extraction/citation_resolver.py:11
  → from app.services.pdf.bookmarks.bookmark_extractor import BookmarkExtractor

core/extraction/utils.py:326
  → from app.services.pdf.preprocessing import is_scanned_page, render_page_to_image
```

### Services to Migrate

| File | Lines | Type |
|------|-------|------|
| `services/pdf/preprocessing.py` | 323 | Mixed (domain + infra) |
| `services/pdf/bookmarks/bookmark_extractor.py` | 376 | Mixed (domain + infra) |
| `services/llm/llm_manager.py` | 1025 | Infrastructure |
| `services/generators/*` | ~800 | Infrastructure |
| `services/pdf/parsers/dde_parser.py` | ~300 | Domain service |

---

## Target Structure

```
app/
├── core/                                    # Domain (NO external deps)
│   ├── extraction/
│   │   ├── engine.py                        # Existing (~300 lines)
│   │   ├── text_extractor.py                # Existing
│   │   ├── vision_extractor.py              # Existing
│   │   ├── content_analyzer.py              # NEW: is_content_sparse() (~80 lines)
│   │   ├── court_patterns.py                # NEW: COURT_HEADER_PATTERNS (~50 lines)
│   │   ├── exhibit_finder.py                # NEW: find_exhibits(), find_sections() (~100 lines)
│   │   └── ...existing files...
│   ├── models/
│   │   ├── bookmark.py                      # NEW: BookmarkTree dataclass (~30 lines)
│   │   └── ...existing files...
│   └── ports/
│       ├── llm.py                           # Existing (no changes)
│       ├── pdf.py                           # UPDATE: add preprocessing methods
│       ├── storage.py                       # Existing (no changes)
│       └── export.py                        # NEW: ExportPort interface (~40 lines)
│
├── adapters/
│   ├── llm/
│   │   ├── bedrock.py                       # UPDATE: integrate rate limiting (~220 lines)
│   │   ├── rate_limiter.py                  # NEW: from llm_manager (~60 lines)
│   │   └── usage_tracker.py                 # NEW: from llm_manager (~100 lines)
│   ├── pdf/
│   │   ├── pymupdf.py                       # UPDATE: compose modules (~200 lines)
│   │   ├── preprocessing.py                 # NEW: scanned detection (~150 lines)
│   │   └── bookmarks.py                     # NEW: structure analysis (~150 lines)
│   ├── storage/
│   │   └── redis_adapter.py                 # Existing (no changes)
│   └── export/
│       ├── gotenberg.py                     # NEW: PDF generation client (~120 lines)
│       ├── html_formatter.py                # NEW: HTML generation (~200 lines)
│       ├── markdown_converter.py            # NEW: MD→PDF (~200 lines)
│       └── report_exporter.py               # NEW: orchestrator (~150 lines)
│
└── workers/
    └── job_handlers.py                      # MOVE: from api/job_processors.py
```

---

## Phase 4: Migration Tasks

### 4.1 Core Domain Logic (No Dependencies)

#### 4.1.1 `core/extraction/content_analyzer.py` (~80 lines)

**Source:** `services/pdf/preprocessing.py:49-111`

```python
"""
Content analysis for chronology entries.

Domain logic for detecting sparse/incomplete medical record extractions.
"""

def is_content_sparse(entry: dict) -> bool:
    """
    Check if chronology entry has visit_type but empty/sparse details.

    Domain logic: knows what fields make a "complete" medical entry
    based on visit type (office_visit, imaging_report, etc.)
    """
    # Move entire function from preprocessing.py
```

**Why core/**: Business rule about what constitutes a "complete" entry. Independent of PDF library.

---

#### 4.1.2 `core/extraction/court_patterns.py` (~50 lines)

**Source:** `services/pdf/preprocessing.py:18-46`

```python
"""
Court document header patterns.

Domain knowledge: regex patterns for SSA/court administrative text
that should be stripped from medical records.
"""
import re

COURT_HEADER_PATTERNS = [
    re.compile(r'Case\s+(?:No\.\s*)?[\d:]+[-\w]+', re.IGNORECASE),
    re.compile(r'(?:Document|Doc\.?|Dkt\.?)\s+\d+', re.IGNORECASE),
    # ... rest of patterns
]
```

**Why core/**: Legal domain knowledge about court document structure. Would exist regardless of PDF library.

---

#### 4.1.3 `core/extraction/exhibit_finder.py` (~100 lines)

**Source:** `services/pdf/bookmarks/bookmark_extractor.py:212-272`

```python
"""
ERE exhibit and section identification.

Domain logic for identifying SSA disability case structure from bookmarks.
"""
import re
from typing import Dict, List, Optional
from app.core.ports.pdf import Bookmark

# ERE-specific exhibit patterns (domain knowledge)
EXHIBIT_PATTERNS = [
    r"\d+[A-F]\s*[-:]",      # "1F:", "2A:", "1F -"
    r"Exhibit\s+[A-Z0-9]+",
    r"Ex\.\s*[A-Z0-9]+",
]

# SSA section patterns (domain knowledge)
SECTION_PATTERNS = {
    "A": r"^[A-Z]?\.\s*Payment|Section\s*A",
    "B": r"^[A-Z]?\.\s*Jurisdictional|Section\s*B",
    "D": r"^[A-Z]?\.\s*Earnings|Section\s*D",
    "E": r"^[A-Z]?\.\s*Disability|Section\s*E",
    "F": r"^[A-Z]?\.\s*Medical|Section\s*F",
}

def find_exhibits(
    bookmarks: List[Bookmark],
    patterns: Optional[List[str]] = None
) -> List[Bookmark]:
    """Find bookmarks that represent exhibits."""
    # Pure function operating on domain model

def find_sections(bookmarks: List[Bookmark]) -> Dict[str, List[Bookmark]]:
    """Find ERE sections (A, B, D, E, F) from bookmarks."""
    # Pure function operating on domain model
```

**Why core/**: ERE/SSA-specific knowledge. No PDF library dependency. Pure functions on Bookmark model.

---

#### 4.1.4 `core/models/bookmark.py` (~30 lines)

**Source:** `services/pdf/bookmarks/bookmark_extractor.py:48-64`

```python
"""Extended bookmark models."""
from dataclasses import dataclass, field
from typing import Any, Dict, List
from app.core.ports.pdf import Bookmark

@dataclass
class BookmarkTree:
    """Hierarchical representation of bookmarks."""
    root_bookmarks: List[Bookmark]
    total_bookmarks: int
    max_depth: int
    page_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
```

---

### 4.2 Expand Ports

#### 4.2.1 `core/ports/pdf.py` - Add Methods

```python
# ADD to existing PDFPort:

@abstractmethod
def strip_court_headers(self, text: str) -> str:
    """Remove court administrative headers from text."""
    pass

@abstractmethod
def get_page_content(self, path: str, page: int) -> dict:
    """Get text or image content for single page.

    Returns: {"type": "text"|"image", "content": str|bytes, "page_num": int}
    """
    pass

@abstractmethod
def get_pages_content(self, path: str, start: int, end: int) -> dict:
    """Get content for page range, separating text and images.

    Returns: {"text_pages": [...], "image_pages": [...], "has_scanned": bool}
    """
    pass

@abstractmethod
def analyze_document(self, path: str, sample_pages: int = 20) -> dict:
    """Analyze document to determine extraction strategy.

    Returns: {"scanned_ratio": float, "recommendation": "text"|"vision"|"hybrid"}
    """
    pass

@abstractmethod
def get_exhibit_page_ranges(self, path: str) -> List[dict]:
    """Get page ranges for all exhibits in PDF.

    Returns: [{"exhibit_id": str, "start_page": int, "end_page": int}, ...]
    """
    pass
```

---

#### 4.2.2 `core/ports/export.py` (~40 lines) - NEW

```python
"""Export port for document generation."""
from abc import ABC, abstractmethod

class ExportPort(ABC):
    """Abstract interface for document export operations."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if export service is available."""
        pass

    @abstractmethod
    async def html_to_pdf(self, html: str, **options) -> bytes:
        """Convert HTML to PDF."""
        pass

    @abstractmethod
    async def markdown_to_pdf(self, markdown: str, **options) -> bytes:
        """Convert Markdown to PDF."""
        pass
```

---

### 4.3 PDF Adapter Modules

#### 4.3.1 `adapters/pdf/preprocessing.py` (~150 lines)

**Source:** `services/pdf/preprocessing.py` (infrastructure parts only)

```python
"""
PDF preprocessing utilities.

Infrastructure: scanned page detection and image rendering using PyMuPDF.
"""
import base64
import logging
from typing import Dict, List, Literal, Union
import fitz

from app.core.extraction.court_patterns import COURT_HEADER_PATTERNS

logger = logging.getLogger(__name__)

def strip_court_headers(text: str) -> str:
    """Remove court administrative headers from page text."""
    result = text
    for pattern in COURT_HEADER_PATTERNS:
        result = pattern.sub('', result)
    return re.sub(r'\s+', ' ', result).strip()

def is_scanned_page(page: fitz.Page, text_threshold: int = 150) -> bool:
    """Detect if page is scanned (low text + large image)."""
    # Infrastructure: uses fitz.Page directly

def render_page_to_image(page: fitz.Page, dpi: int = 150) -> bytes:
    """Render page to PNG bytes."""

def render_page_to_base64(page: fitz.Page, dpi: int = 150) -> str:
    """Render page to base64-encoded PNG."""

def get_page_content(doc: fitz.Document, page_num: int) -> dict:
    """Get page content, auto-detecting text vs scanned."""

def get_pages_content(doc: fitz.Document, start: int, end: int) -> dict:
    """Get content for page range."""

def analyze_document_content(doc: fitz.Document, sample_pages: int = 20) -> dict:
    """Analyze document extraction strategy."""
```

---

#### 4.3.2 `adapters/pdf/bookmarks.py` (~150 lines)

**Source:** `services/pdf/bookmarks/bookmark_extractor.py` (infrastructure parts only)

```python
"""
PDF bookmark analysis utilities.

Infrastructure: bookmark structure analysis using PyMuPDF.
Does NOT include exhibit/section finding (that's domain logic in core/).
"""
from typing import Any, Dict, List
import fitz

from app.core.ports.pdf import Bookmark
from app.core.models.bookmark import BookmarkTree

def analyze_structure(bookmarks: List[Bookmark]) -> BookmarkTree:
    """Build hierarchical bookmark tree."""

def map_to_content(pdf_path: str, bookmarks: List[Bookmark]) -> Dict[str, Any]:
    """Map bookmarks to page ranges."""

def get_exhibit_page_ranges(pdf_path: str, bookmarks: List[Bookmark]) -> List[dict]:
    """Get page ranges for exhibits.

    Note: Uses find_exhibits() from core/extraction/exhibit_finder.py
    """
    from app.core.extraction.exhibit_finder import find_exhibits
    exhibits = find_exhibits(bookmarks)
    # ... map to page ranges using fitz
```

---

#### 4.3.3 `adapters/pdf/pymupdf.py` - Update (~200 lines)

```python
"""
PyMuPDF adapter implementing PDFPort.

Composes preprocessing and bookmark modules.
"""
from typing import Dict, List
import fitz

from app.core.ports.pdf import PDFPort, Bookmark
from app.adapters.pdf import preprocessing, bookmarks

class PyMuPDFAdapter(PDFPort):
    """PyMuPDF implementation of PDFPort."""

    def extract_text(self, path: str, start_page: int, end_page: int) -> str:
        # Existing implementation

    def extract_bookmarks(self, path: str) -> List[Bookmark]:
        # Existing implementation

    def render_page_image(self, path: str, page: int, dpi: int = 150) -> bytes:
        # Existing implementation

    def is_scanned_page(self, path: str, page: int) -> bool:
        doc = fitz.open(path)
        result = preprocessing.is_scanned_page(doc[page - 1])
        doc.close()
        return result

    def strip_court_headers(self, text: str) -> str:
        return preprocessing.strip_court_headers(text)

    def get_page_content(self, path: str, page: int) -> dict:
        doc = fitz.open(path)
        result = preprocessing.get_page_content(doc, page - 1)
        doc.close()
        return result

    def get_pages_content(self, path: str, start: int, end: int) -> dict:
        doc = fitz.open(path)
        result = preprocessing.get_pages_content(doc, start, end)
        doc.close()
        return result

    def analyze_document(self, path: str, sample_pages: int = 20) -> dict:
        doc = fitz.open(path)
        result = preprocessing.analyze_document_content(doc, sample_pages)
        doc.close()
        return result

    def get_exhibit_page_ranges(self, path: str) -> List[dict]:
        bms = self.extract_bookmarks(path)
        return bookmarks.get_exhibit_page_ranges(path, bms)
```

---

### 4.4 LLM Adapter Modules

#### 4.4.1 `adapters/llm/rate_limiter.py` (~60 lines)

**Source:** `services/llm/llm_manager.py:107-129`

```python
"""Rate limiting for LLM API calls."""
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire rate limit token, waiting if necessary."""
        async with self.lock:
            now = datetime.now()
            self.requests = [r for r in self.requests if now - r < timedelta(minutes=1)]

            if len(self.requests) >= self.requests_per_minute:
                sleep_time = 60 - (now - self.requests[0]).total_seconds()
                await asyncio.sleep(sleep_time)

            self.requests.append(now)
```

---

#### 4.4.2 `adapters/llm/usage_tracker.py` (~100 lines)

**Source:** `services/llm/llm_manager.py:85-104, 783-836`

```python
"""Usage and cost tracking for LLM calls."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List

@dataclass
class UsageStats:
    """Single LLM call statistics."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_estimate: float
    response_time: float
    timestamp: datetime

class CostTracker:
    """Track and analyze LLM costs."""

    # Pricing per 1K tokens
    PRICING = {
        "haiku": {"input": 0.001, "output": 0.005},
        "sonnet": {"input": 0.003, "output": 0.015},
    }

    def __init__(self):
        self.stats: List[UsageStats] = []

    def track(self, stats: UsageStats):
        """Record usage statistics."""
        self.stats.append(stats)

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for token counts."""
        pricing = self.PRICING.get("haiku")  # Default
        for key, prices in self.PRICING.items():
            if key in model.lower():
                pricing = prices
                break
        return (prompt_tokens / 1000) * pricing["input"] + \
               (completion_tokens / 1000) * pricing["output"]

    def get_summary(self, hours: int = 24) -> Dict:
        """Get cost summary for time window."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [s for s in self.stats if s.timestamp >= cutoff]
        return {
            "total_cost": sum(s.cost_estimate for s in recent),
            "total_tokens": sum(s.total_tokens for s in recent),
            "request_count": len(recent),
        }
```

---

#### 4.4.3 `adapters/llm/bedrock.py` - Update (~220 lines)

Add rate limiting and usage tracking to existing adapter:

```python
# ADD to existing BedrockAdapter:

from app.adapters.llm.rate_limiter import RateLimiter
from app.adapters.llm.usage_tracker import UsageStats, CostTracker

class BedrockAdapter(LLMPort):
    def __init__(self):
        # ... existing init
        self.rate_limiter = RateLimiter(requests_per_minute=50)
        self.cost_tracker = CostTracker()

    async def generate(self, prompt: str, model: str, **kwargs) -> str:
        await self.rate_limiter.acquire()
        start_time = time.time()

        # ... existing generation code ...

        # Track usage
        usage = response_body.get("usage", {})
        stats = UsageStats(
            model=model,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            cost_estimate=self.cost_tracker.estimate_cost(
                model, usage.get("input_tokens", 0), usage.get("output_tokens", 0)
            ),
            response_time=time.time() - start_time,
            timestamp=datetime.now(),
        )
        self.cost_tracker.track(stats)

        return content
```

---

### 4.5 Export Adapter Modules

#### 4.5.1 `adapters/export/gotenberg.py` (~120 lines)

**Source:** `services/generators/gotenberg_client.py`

Implements `ExportPort` using Gotenberg HTTP API.

#### 4.5.2 `adapters/export/html_formatter.py` (~200 lines)

**Source:** `services/generators/html_report_generator.py`

Pure functions for HTML generation. No changes needed.

#### 4.5.3 `adapters/export/markdown_converter.py` (~200 lines)

**Source:** `services/generators/markdown_converter.py`

Update to use `ExportPort` via dependency injection.

#### 4.5.4 `adapters/export/report_exporter.py` (~150 lines)

**Source:** `services/generators/report_exporter.py`

Update to use `ExportPort` via dependency injection.

---

### 4.6 Update Core Imports

Files to update:

| File | Change |
|------|--------|
| `core/extraction/engine.py` | Remove LLMManager fallback, require LLMPort |
| `core/extraction/recovery_handler.py` | Import from `core/extraction/content_analyzer` |
| `core/extraction/citation_resolver.py` | Use PDFPort instead of BookmarkExtractor |
| `core/extraction/utils.py` | Use PDFPort methods |

---

### 4.7 Move Workers

```bash
mv app/api/job_processors.py app/workers/job_handlers.py
```

Update imports to use adapters instead of services.

---

## Phase 5: Cleanup

### 5.1 Delete Services Directory

After all consumers updated:

```bash
rm -rf app/services/
```

### 5.2 Verify

```bash
# All tests pass
PYTHONPATH=. pytest tests/ -v

# No service imports in core/
grep -r "from app.services" app/core/
# Should return nothing

# API still works
PYTHONPATH=. python -m uvicorn app.api.ere_api:create_app --factory
```

---

## Execution Order

```
1. Create core/extraction/content_analyzer.py
   └── No dependencies, enables recovery_handler.py update

2. Create core/extraction/court_patterns.py
   └── No dependencies, used by preprocessing.py

3. Create core/extraction/exhibit_finder.py
   └── Depends on: Bookmark model (exists)

4. Create core/models/bookmark.py
   └── No dependencies

5. Update core/ports/pdf.py
   └── Add new abstract methods

6. Create adapters/pdf/preprocessing.py
   └── Depends on: court_patterns.py

7. Create adapters/pdf/bookmarks.py
   └── Depends on: exhibit_finder.py

8. Update adapters/pdf/pymupdf.py
   └── Compose new modules

9. Create adapters/llm/rate_limiter.py
   └── No dependencies

10. Create adapters/llm/usage_tracker.py
    └── No dependencies

11. Update adapters/llm/bedrock.py
    └── Integrate rate_limiter, usage_tracker

12. Create core/ports/export.py
    └── No dependencies

13. Create adapters/export/*.py
    └── Depends on: ExportPort

14. Update core/ imports
    └── All new modules ready

15. Move job_processors.py → workers/
    └── Update to use adapters

16. Delete services/
    └── All consumers migrated
```

---

## File Size Summary

| File | Lines | Status |
|------|-------|--------|
| `core/extraction/content_analyzer.py` | ~80 | NEW |
| `core/extraction/court_patterns.py` | ~50 | NEW |
| `core/extraction/exhibit_finder.py` | ~100 | NEW |
| `core/models/bookmark.py` | ~30 | NEW |
| `core/ports/pdf.py` | ~100 | UPDATE |
| `core/ports/export.py` | ~40 | NEW |
| `adapters/pdf/preprocessing.py` | ~150 | NEW |
| `adapters/pdf/bookmarks.py` | ~150 | NEW |
| `adapters/pdf/pymupdf.py` | ~200 | UPDATE |
| `adapters/llm/rate_limiter.py` | ~60 | NEW |
| `adapters/llm/usage_tracker.py` | ~100 | NEW |
| `adapters/llm/bedrock.py` | ~220 | UPDATE |
| `adapters/export/gotenberg.py` | ~120 | NEW |
| `adapters/export/html_formatter.py` | ~200 | NEW |
| `adapters/export/markdown_converter.py` | ~200 | NEW |
| `adapters/export/report_exporter.py` | ~150 | NEW |
| `workers/job_handlers.py` | ~300 | MOVE |

**All files under 350 lines** ✅

---

---

## Additional Findings (Post-Inspection)

### Files Over 350 Lines (Must Split)

| File | Lines | Split Strategy |
|------|-------|----------------|
| `job_processors.py` | 612 | → `workers/ere_handler.py` + `workers/chartvision_handler.py` + shared utils |
| `markdown_converter.py` | 900 | → `adapters/export/markdown.py` + `adapters/export/css_styles.py` + `adapters/export/html_templates.py` |
| `html_report_generator.py` | 512 | → `adapters/export/html_formatter.py` + `adapters/export/html_sections.py` |

### Business Logic to Extract to Core

| Function | Current Location | Target | Lines |
|----------|------------------|--------|-------|
| `normalize_dde_result()` | job_processors.py:30-146 | `core/extraction/dde_normalizer.py` | ~120 |
| `DDEParser` | services/pdf/parsers/ | `core/parsers/dde_parser.py` | ~355 |

### DDEParser Refactoring

```python
# Before (services/pdf/parsers/dde_parser.py)
class DDEParser:
    def __init__(self):
        self._llm_manager = None  # Lazy init LLMManager

    @property
    def llm(self):
        if self._llm_manager is None:
            from app.services.llm.llm_manager import LLMManager
            self._llm_manager = LLMManager()  # BAD: service dependency
        return self._llm_manager

# After (core/parsers/dde_parser.py)
class DDEParser:
    def __init__(self, llm: LLMPort, pdf: PDFPort):
        self._llm = llm
        self._pdf = pdf

    async def parse(self, pdf_path: str, page_start: int, page_end: int):
        # Use self._pdf.get_pages_content() instead of preprocessing import
        # Use self._llm.generate() instead of llm_manager
```

### Workers Split Strategy

```
workers/
├── __init__.py
├── base_handler.py          # Shared logic (~150 lines)
│   ├── extract_bookmarks()
│   ├── parse_dde()
│   ├── extract_chronology()
│   └── build_report()
├── ere_handler.py           # ERE-specific (~150 lines)
└── chartvision_handler.py   # ChartVision-specific (~150 lines)
```

### Export Adapters Split Strategy

```
adapters/export/
├── __init__.py
├── gotenberg.py             # HTTP client (~200 lines) ✅
├── css_styles.py            # CSS generation (~150 lines)
├── html_templates.py        # HTML section renderers (~200 lines)
├── html_formatter.py        # Main HTML orchestrator (~150 lines)
├── markdown.py              # MD→HTML conversion (~200 lines)
└── report_exporter.py       # High-level export (~150 lines)
```

---

## Revised Execution Order

```
Phase 4.1: Core Domain Logic
├── 4.1.1 content_analyzer.py
├── 4.1.2 court_patterns.py
├── 4.1.3 exhibit_finder.py
├── 4.1.4 core/models/bookmark.py
└── 4.1.5 core/extraction/dde_normalizer.py  ← NEW

Phase 4.2: Ports
├── 4.2.1 Update core/ports/pdf.py
└── 4.2.2 Create core/ports/export.py

Phase 4.3: PDF Adapters
├── 4.3.1 adapters/pdf/preprocessing.py
└── 4.3.2 adapters/pdf/bookmarks.py

Phase 4.4: LLM Adapters
├── 4.4.1 adapters/llm/rate_limiter.py
└── 4.4.2 adapters/llm/usage_tracker.py

Phase 4.5: Export Adapters (6 files)  ← EXPANDED
├── 4.5.1 adapters/export/gotenberg.py
├── 4.5.2 adapters/export/css_styles.py
├── 4.5.3 adapters/export/html_templates.py
├── 4.5.4 adapters/export/html_formatter.py
├── 4.5.5 adapters/export/markdown.py
└── 4.5.6 adapters/export/report_exporter.py

Phase 4.6: Core Parsers  ← NEW
└── 4.6.1 core/parsers/dde_parser.py (refactored)

Phase 4.7: Workers (3 files)  ← EXPANDED
├── 4.7.1 workers/base_handler.py
├── 4.7.2 workers/ere_handler.py
└── 4.7.3 workers/chartvision_handler.py

Phase 4.8: Update Imports
└── Update all core/ files to use ports

Phase 5: Cleanup
└── Delete services/ directory
```

---

## Success Criteria

- [ ] All 229 tests pass
- [ ] Zero imports from `app.services` in `app/core/`
- [ ] All files under 350 lines
- [ ] API endpoints unchanged
- [ ] `services/` directory deleted
