# Hexagonal Architecture Gaps Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the hexagonal restructure by fixing critical path issues, adding missing adapters, eliminating duplicates, and achieving test coverage.

**Architecture:** Port/Adapter pattern with core domain isolated from infrastructure. Prompts centralized in `app/config/prompts/`, adapters in `app/adapters/`, core logic in `app/core/`.

**Tech Stack:** Python 3.11+, pytest, PyMuPDF, boto3 (Bedrock), Redis, FastAPI

---

## Phase 1: Critical Fixes (Blocks Functionality)

### Task 1: Fix TextExtractor Prompt Path

**Files:**
- Modify: `app/core/extraction/text_extractor.py:24-31`
- Test: `tests/unit/core/extraction/test_text_extractor.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/core/extraction/test_text_extractor.py

def test_load_prompt_template_finds_yaml():
    """Verify prompt template loads from correct config path."""
    from app.core.extraction.text_extractor import _load_prompt_template

    template = _load_prompt_template()

    assert template is not None
    assert "system_prompt" in template or "extraction" in template
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_text_extractor.py::test_load_prompt_template_finds_yaml -v`
Expected: FAIL (returns empty dict, warning logged about missing file)

**Step 3: Write minimal implementation**

```python
# app/core/extraction/text_extractor.py - replace lines 24-31

def _load_prompt_template() -> Dict[str, Any]:
    """Load prompt template from YAML file."""
    # Use centralized config path
    config_path = Path(__file__).parents[2] / "config" / "prompts" / "extraction" / "text_extraction.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    # Fallback to legacy path during migration
    legacy_path = Path(__file__).parent / "prompts" / "text_extraction.yaml"
    if legacy_path.exists():
        with open(legacy_path, "r") as f:
            return yaml.safe_load(f)
    logger.warning(f"Text extraction template not found at {config_path}")
    return {}
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_text_extractor.py::test_load_prompt_template_finds_yaml -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/core/extraction/text_extractor.py tests/unit/core/extraction/test_text_extractor.py
git commit -m "fix: update TextExtractor prompt path to config/prompts"
```

---

### Task 2: Fix VisionExtractor Prompt Path

**Files:**
- Modify: `app/core/extraction/vision_extractor.py:22-29`
- Test: `tests/unit/core/extraction/test_vision_extractor.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/core/extraction/test_vision_extractor.py

def test_load_prompt_template_finds_yaml():
    """Verify prompt template loads from correct config path."""
    from app.core.extraction.vision_extractor import _load_prompt_template

    template = _load_prompt_template()

    assert template is not None
    assert "system_prompt" in template or "extraction" in template
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_vision_extractor.py::test_load_prompt_template_finds_yaml -v`
Expected: FAIL (returns empty dict)

**Step 3: Write minimal implementation**

```python
# app/core/extraction/vision_extractor.py - replace lines 22-29

def _load_prompt_template() -> Dict[str, Any]:
    """Load prompt template from YAML file."""
    # Use centralized config path
    config_path = Path(__file__).parents[2] / "config" / "prompts" / "extraction" / "vision_extraction.yaml"
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    # Fallback to legacy path during migration
    legacy_path = Path(__file__).parent / "prompts" / "vision_extraction.yaml"
    if legacy_path.exists():
        with open(legacy_path, "r") as f:
            return yaml.safe_load(f)
    logger.warning(f"Vision extraction template not found at {config_path}")
    return {}
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_vision_extractor.py::test_load_prompt_template_finds_yaml -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/core/extraction/vision_extractor.py tests/unit/core/extraction/test_vision_extractor.py
git commit -m "fix: update VisionExtractor prompt path to config/prompts"
```

---

### Task 3: Create Missing formatter_config.yaml

**Files:**
- Create: `app/core/builders/formatter_config.yaml`
- Verify: `app/core/builders/occurrence_formatter.py:27`

**Step 1: Read occurrence_formatter to understand expected config structure**

Run: `PYTHONPATH=. python -c "from app.core.builders.occurrence_formatter import OccurrenceFormatter; print('imports ok')"`
Expected: Should work or show what config keys are expected

**Step 2: Create minimal config file**

```yaml
# app/core/builders/formatter_config.yaml
# Configuration for OccurrenceFormatter

# Date format patterns
date_formats:
  display: "%B %d, %Y"
  short: "%m/%d/%Y"
  iso: "%Y-%m-%d"

# Field mapping for output
field_order:
  - date
  - provider
  - facility
  - visit_type
  - findings
  - diagnoses
  - treatments

# Formatting options
options:
  include_page_citations: true
  group_by_provider: false
  sort_chronological: true
```

**Step 3: Verify config loads**

Run: `PYTHONPATH=. python -c "from app.core.builders.occurrence_formatter import OccurrenceFormatter; f = OccurrenceFormatter(); print('OK')"`
Expected: No errors

**Step 4: Commit**

```bash
git add app/core/builders/formatter_config.yaml
git commit -m "feat: add formatter_config.yaml for OccurrenceFormatter"
```

---

## Phase 2: Architecture Debt

### Task 4: Delete Duplicate citation_resolver.py

**Files:**
- Delete: `app/services/citation_resolver.py`
- Verify: No imports reference old location

**Step 1: Verify no imports use old path**

Run: `grep -rn "from app.services.citation_resolver" app/ --include="*.py"`
Expected: No matches (or list files to update)

**Step 2: Delete duplicate file**

```bash
rm app/services/citation_resolver.py
```

**Step 3: Run tests to verify nothing breaks**

Run: `PYTHONPATH=. pytest tests/ -v --tb=short 2>&1 | head -50`
Expected: All tests pass

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove duplicate citation_resolver.py from services"
```

---

### Task 5: Create RedisAdapter for JobStoragePort

**Files:**
- Create: `app/adapters/storage/redis_adapter.py`
- Modify: `app/adapters/storage/__init__.py`
- Create: `tests/unit/adapters/storage/__init__.py`
- Create: `tests/unit/adapters/storage/test_redis_adapter.py`

**Step 1: Write the failing test**

```python
# tests/unit/adapters/storage/test_redis_adapter.py
"""Tests for RedisAdapter implementing JobStoragePort."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.adapters.storage.redis_adapter import RedisAdapter
from app.core.ports.storage import JobStoragePort


class TestRedisAdapter:
    """Test RedisAdapter implements JobStoragePort correctly."""

    def test_implements_job_storage_port(self):
        """Verify RedisAdapter is a JobStoragePort."""
        mock_redis = MagicMock()
        adapter = RedisAdapter(mock_redis)
        assert isinstance(adapter, JobStoragePort)

    @pytest.mark.asyncio
    async def test_save_job(self):
        """Test saving job data to Redis."""
        mock_redis = MagicMock()
        mock_redis.set = MagicMock()
        adapter = RedisAdapter(mock_redis)

        await adapter.save_job("job-123", {"status": "pending"})

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "job-123" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_job_returns_data(self):
        """Test retrieving job data from Redis."""
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=b'{"status": "complete"}')
        adapter = RedisAdapter(mock_redis)

        result = await adapter.get_job("job-123")

        assert result == {"status": "complete"}

    @pytest.mark.asyncio
    async def test_get_job_returns_none_when_missing(self):
        """Test get_job returns None for missing job."""
        mock_redis = MagicMock()
        mock_redis.get = MagicMock(return_value=None)
        adapter = RedisAdapter(mock_redis)

        result = await adapter.get_job("nonexistent")

        assert result is None
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/adapters/storage/test_redis_adapter.py -v`
Expected: FAIL (module not found)

**Step 3: Create __init__.py for test directory**

```python
# tests/unit/adapters/storage/__init__.py
"""Storage adapter tests."""
```

**Step 4: Write minimal implementation**

```python
# app/adapters/storage/redis_adapter.py
"""Redis implementation of JobStoragePort.

Provides job state persistence using Redis as the backing store.
"""
import json
from typing import Optional

from app.core.ports.storage import JobStoragePort


class RedisAdapter(JobStoragePort):
    """Redis implementation of JobStoragePort.

    Args:
        redis_client: Configured redis.Redis instance
        key_prefix: Prefix for all job keys (default: "job:")
        ttl_seconds: Time-to-live for job data (default: 86400 = 24h)
    """

    def __init__(
        self,
        redis_client,
        key_prefix: str = "job:",
        ttl_seconds: int = 86400,
    ):
        self._redis = redis_client
        self._prefix = key_prefix
        self._ttl = ttl_seconds

    def _key(self, job_id: str) -> str:
        """Build Redis key for job."""
        return f"{self._prefix}{job_id}"

    async def save_job(self, job_id: str, data: dict) -> None:
        """Save job data to Redis with TTL."""
        key = self._key(job_id)
        self._redis.set(key, json.dumps(data), ex=self._ttl)

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Retrieve job data from Redis."""
        key = self._key(job_id)
        raw = self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def update_job(self, job_id: str, updates: dict) -> None:
        """Update job data in Redis (merge with existing)."""
        existing = await self.get_job(job_id)
        if existing is None:
            existing = {}
        existing.update(updates)
        await self.save_job(job_id, existing)

    async def delete_job(self, job_id: str) -> None:
        """Delete job data from Redis."""
        key = self._key(job_id)
        self._redis.delete(key)
```

**Step 5: Update __init__.py exports**

```python
# app/adapters/storage/__init__.py
"""Storage adapters (Redis, filesystem)."""
from app.adapters.storage.redis_adapter import RedisAdapter

__all__ = ["RedisAdapter"]
```

**Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/adapters/storage/test_redis_adapter.py -v`
Expected: PASS (all 4 tests)

**Step 7: Commit**

```bash
git add app/adapters/storage/ tests/unit/adapters/storage/
git commit -m "feat: add RedisAdapter implementing JobStoragePort"
```

---

### Task 6: Migrate ere_api.py to Use JobStoragePort

**Files:**
- Modify: `app/api/ere_api.py:110,190-195`

**Step 1: Identify current Redis usage**

Current code at line ~190:
```python
self.redis_client = redis.Redis(...)
```

**Step 2: Update to use RedisAdapter**

```python
# app/api/ere_api.py - update imports (around line 110)
# Change:
import redis
# To:
import redis
from app.adapters.storage import RedisAdapter
from app.core.ports.storage import JobStoragePort
```

```python
# app/api/ere_api.py - update initialization (around line 190-195)
# Change:
self.redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=False,
)
# To:
_redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=False,
)
self.job_storage: JobStoragePort = RedisAdapter(_redis_client)
# Keep redis_client for backwards compat during migration
self.redis_client = _redis_client
```

**Step 3: Run existing tests**

Run: `PYTHONPATH=. pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: All tests pass

**Step 4: Commit**

```bash
git add app/api/ere_api.py
git commit -m "refactor: inject JobStoragePort into ere_api via RedisAdapter"
```

---

## Phase 3: Test Coverage

### Task 7: Add Tests for citation_resolver.py

**Files:**
- Create: `tests/unit/core/extraction/test_citation_resolver.py`
- Reference: `app/core/extraction/citation_resolver.py`

**Step 1: Read the module to understand what to test**

Review `app/core/extraction/citation_resolver.py` for public functions/classes.

**Step 2: Write tests**

```python
# tests/unit/core/extraction/test_citation_resolver.py
"""Tests for citation_resolver module."""
import pytest

from app.core.extraction.citation_resolver import (
    resolve_citation,
    CitationResolver,
)


class TestResolveCitation:
    """Test resolve_citation function."""

    def test_resolves_simple_page_reference(self):
        """Test resolving a simple page number."""
        result = resolve_citation("Page 5", total_pages=100)
        assert result == 5

    def test_returns_none_for_invalid_citation(self):
        """Test invalid citation returns None."""
        result = resolve_citation("invalid", total_pages=100)
        assert result is None

    def test_handles_exhibit_reference(self):
        """Test resolving exhibit reference like '1F/5'."""
        result = resolve_citation("1F/5", exhibit_map={"1F": 10})
        assert result == 15  # 10 (exhibit start) + 5 (page within)


class TestCitationResolver:
    """Test CitationResolver class."""

    def test_init_with_exhibit_map(self):
        """Test initialization with exhibit mapping."""
        resolver = CitationResolver(exhibit_map={"1F": 10, "2F": 50})
        assert resolver.exhibit_map == {"1F": 10, "2F": 50}

    def test_resolve_returns_absolute_page(self):
        """Test resolve method returns absolute page number."""
        resolver = CitationResolver(exhibit_map={"1F": 10})
        result = resolver.resolve("1F/3")
        assert result == 13
```

**Step 3: Run test to verify implementation matches**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_citation_resolver.py -v`
Expected: PASS (adjust tests if API differs)

**Step 4: Commit**

```bash
git add tests/unit/core/extraction/test_citation_resolver.py
git commit -m "test: add tests for citation_resolver module"
```

---

### Task 8: Add Tests for utils.py

**Files:**
- Create: `tests/unit/core/extraction/test_utils.py`
- Reference: `app/core/extraction/utils.py`

**Step 1: Read utils.py to identify public functions**

Review `app/core/extraction/utils.py` for testable utilities.

**Step 2: Write tests for identified utilities**

```python
# tests/unit/core/extraction/test_utils.py
"""Tests for extraction utility functions."""
import pytest

from app.core.extraction.utils import (
    # Import public functions after reviewing utils.py
    # Examples - adjust based on actual API:
    normalize_date,
    clean_text,
    extract_page_number,
)


class TestNormalizeDate:
    """Test date normalization utility."""

    def test_normalizes_mm_dd_yyyy(self):
        """Test MM/DD/YYYY format."""
        result = normalize_date("12/25/2023")
        assert result == "2023-12-25"

    def test_normalizes_written_date(self):
        """Test written date format."""
        result = normalize_date("December 25, 2023")
        assert result == "2023-12-25"

    def test_returns_none_for_invalid(self):
        """Test invalid date returns None."""
        result = normalize_date("not a date")
        assert result is None


class TestCleanText:
    """Test text cleaning utility."""

    def test_removes_extra_whitespace(self):
        """Test collapsing multiple spaces."""
        result = clean_text("hello    world")
        assert result == "hello world"

    def test_strips_leading_trailing(self):
        """Test stripping whitespace."""
        result = clean_text("  hello  ")
        assert result == "hello"
```

**Step 3: Run tests and adjust based on actual API**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_utils.py -v`
Expected: Adjust tests to match actual function signatures

**Step 4: Commit**

```bash
git add tests/unit/core/extraction/test_utils.py
git commit -m "test: add tests for extraction utils module"
```

---

### Task 9: Add Tests for core/builders/

**Files:**
- Create: `tests/unit/core/builders/__init__.py`
- Create: `tests/unit/core/builders/test_chartvision_builder.py`
- Create: `tests/unit/core/builders/test_occurrence_formatter.py`
- Create: `tests/unit/core/builders/test_report_generator.py`

**Step 1: Create test directory**

```python
# tests/unit/core/builders/__init__.py
"""Builder tests."""
```

**Step 2: Write test for chartvision_builder**

```python
# tests/unit/core/builders/test_chartvision_builder.py
"""Tests for ChartVisionBuilder."""
import pytest

from app.core.builders.chartvision_builder import ChartVisionBuilder


class TestChartVisionBuilder:
    """Test ChartVisionBuilder functionality."""

    def test_init_creates_empty_builder(self):
        """Test builder initializes with empty state."""
        builder = ChartVisionBuilder()
        assert builder is not None

    def test_add_entry(self):
        """Test adding a chronology entry."""
        builder = ChartVisionBuilder()
        entry = {
            "date": "2023-01-15",
            "provider": "Dr. Smith",
            "visit_type": "Office Visit",
        }
        builder.add_entry(entry)
        assert len(builder.entries) == 1

    def test_build_returns_chronology(self):
        """Test build produces final chronology."""
        builder = ChartVisionBuilder()
        builder.add_entry({"date": "2023-01-15", "provider": "Dr. Smith"})
        result = builder.build()
        assert "entries" in result or isinstance(result, list)
```

**Step 3: Write test for occurrence_formatter**

```python
# tests/unit/core/builders/test_occurrence_formatter.py
"""Tests for OccurrenceFormatter."""
import pytest

from app.core.builders.occurrence_formatter import OccurrenceFormatter


class TestOccurrenceFormatter:
    """Test OccurrenceFormatter functionality."""

    def test_init_loads_config(self):
        """Test formatter loads configuration."""
        formatter = OccurrenceFormatter()
        assert formatter is not None

    def test_format_entry(self):
        """Test formatting a single entry."""
        formatter = OccurrenceFormatter()
        entry = {
            "date": "2023-01-15",
            "provider": "Dr. Smith",
            "findings": "Normal exam",
        }
        result = formatter.format(entry)
        assert isinstance(result, (str, dict))
```

**Step 4: Write test for report_generator**

```python
# tests/unit/core/builders/test_report_generator.py
"""Tests for ReportGenerator."""
import pytest

from app.core.builders.report_generator import ReportGenerator


class TestReportGenerator:
    """Test ReportGenerator functionality."""

    def test_init(self):
        """Test generator initializes."""
        generator = ReportGenerator()
        assert generator is not None

    def test_generate_markdown(self):
        """Test generating markdown report."""
        generator = ReportGenerator()
        entries = [
            {"date": "2023-01-15", "provider": "Dr. Smith"},
        ]
        result = generator.generate(entries, format="markdown")
        assert isinstance(result, str)
        assert "2023" in result or "Smith" in result
```

**Step 5: Run all builder tests**

Run: `PYTHONPATH=. pytest tests/unit/core/builders/ -v`
Expected: PASS (adjust based on actual API)

**Step 6: Commit**

```bash
git add tests/unit/core/builders/
git commit -m "test: add tests for core/builders module"
```

---

### Task 10: Add Tests for core/models/

**Files:**
- Create: `tests/unit/core/models/__init__.py`
- Create: `tests/unit/core/models/test_entry.py`
- Create: `tests/unit/core/models/test_chartvision.py`

**Step 1: Create test directory**

```python
# tests/unit/core/models/__init__.py
"""Model tests."""
```

**Step 2: Write test for entry.py**

```python
# tests/unit/core/models/test_entry.py
"""Tests for Entry model."""
import pytest

from app.core.models.entry import Entry, ChronologyEntry


class TestEntry:
    """Test Entry dataclass/model."""

    def test_create_entry(self):
        """Test creating an entry."""
        entry = Entry(
            date="2023-01-15",
            provider="Dr. Smith",
            visit_type="Office Visit",
        )
        assert entry.date == "2023-01-15"
        assert entry.provider == "Dr. Smith"

    def test_entry_with_optional_fields(self):
        """Test entry with optional fields."""
        entry = Entry(
            date="2023-01-15",
            provider="Dr. Smith",
            findings="Normal",
            diagnoses=["Hypertension"],
        )
        assert entry.findings == "Normal"
        assert "Hypertension" in entry.diagnoses


class TestChronologyEntry:
    """Test ChronologyEntry if different from Entry."""

    def test_create_chronology_entry(self):
        """Test creating chronology entry."""
        entry = ChronologyEntry(
            date="2023-01-15",
            exhibit="1F",
            page=5,
        )
        assert entry.exhibit == "1F"
```

**Step 3: Write test for chartvision.py**

```python
# tests/unit/core/models/test_chartvision.py
"""Tests for ChartVision models."""
import pytest

from app.core.models.chartvision import ChartVisionReport, ChartVisionConfig


class TestChartVisionReport:
    """Test ChartVisionReport model."""

    def test_create_report(self):
        """Test creating a report."""
        report = ChartVisionReport(
            claimant_name="John Doe",
            entries=[],
        )
        assert report.claimant_name == "John Doe"

    def test_report_with_entries(self):
        """Test report with entries."""
        report = ChartVisionReport(
            claimant_name="John Doe",
            entries=[{"date": "2023-01-15"}],
        )
        assert len(report.entries) == 1


class TestChartVisionConfig:
    """Test ChartVisionConfig model."""

    def test_default_config(self):
        """Test default configuration."""
        config = ChartVisionConfig()
        assert config is not None
```

**Step 4: Run all model tests**

Run: `PYTHONPATH=. pytest tests/unit/core/models/ -v`
Expected: PASS (adjust based on actual model API)

**Step 5: Commit**

```bash
git add tests/unit/core/models/
git commit -m "test: add tests for core/models module"
```

---

## Phase 4: Cleanup

### Task 11: Delete Legacy services/llm/prompts/

**Files:**
- Delete: `app/services/llm/prompts/` (entire directory)
- Verify: No imports reference this path

**Step 1: Verify no imports use old prompts path**

Run: `grep -rn "from app.services.llm.prompts" app/ --include="*.py"`
Expected: No matches

**Step 2: Verify prompts are not loaded from old path**

Run: `grep -rn "services/llm/prompts" app/ --include="*.py"`
Expected: Only comments/docstrings, no actual usage

**Step 3: Delete legacy directory**

```bash
rm -rf app/services/llm/prompts/
```

**Step 4: Run tests to verify nothing breaks**

Run: `PYTHONPATH=. pytest tests/ -v --tb=short 2>&1 | tail -20`
Expected: All tests pass

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy services/llm/prompts directory"
```

---

### Task 12: Update Sparse __init__.py Files with Exports

**Files:**
- Modify: `app/core/models/__init__.py`
- Modify: `app/api/routes/__init__.py`

**Step 1: Update models __init__.py**

```python
# app/core/models/__init__.py
"""Core domain models."""
from app.core.models.entry import Entry, ChronologyEntry
from app.core.models.chartvision import ChartVisionReport, ChartVisionConfig

__all__ = [
    "Entry",
    "ChronologyEntry",
    "ChartVisionReport",
    "ChartVisionConfig",
]
```

**Step 2: Update routes __init__.py**

```python
# app/api/routes/__init__.py
"""API route handlers."""
# Add exports as routes are implemented
```

**Step 3: Verify imports work**

Run: `PYTHONPATH=. python -c "from app.core.models import Entry, ChronologyEntry; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add app/core/models/__init__.py app/api/routes/__init__.py
git commit -m "refactor: add exports to sparse __init__.py files"
```

---

## Final Verification

### Task 13: Run Full Test Suite

**Step 1: Run all tests**

Run: `PYTHONPATH=. pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Run linter**

Run: `PYTHONPATH=. python -m ruff check app/ tests/`
Expected: No errors (or document known issues)

**Step 3: Verify server starts**

Run: `PYTHONPATH=. timeout 5 python -m uvicorn app.api.ere_api:create_app --factory --host 0.0.0.0 --port 8811 || true`
Expected: Server starts without import errors

**Step 4: Final commit with summary**

```bash
git add -A
git commit -m "chore: complete hexagonal architecture migration

- Fixed prompt paths in TextExtractor and VisionExtractor
- Added formatter_config.yaml
- Created RedisAdapter implementing JobStoragePort
- Removed duplicate citation_resolver.py
- Added test coverage for builders, models, utils
- Cleaned up legacy prompts directory
- Updated __init__.py exports"
```

---

## Summary

| Phase | Tasks | Priority |
|-------|-------|----------|
| Critical Fixes | 1-3 | 🔴 Do First |
| Architecture Debt | 4-6 | 🟠 High |
| Test Coverage | 7-10 | 🟡 Medium |
| Cleanup | 11-12 | 🟢 Low |
| Verification | 13 | ✅ Final |

**Total Tasks:** 13
**Estimated Steps:** ~65 (5 steps avg per task)
