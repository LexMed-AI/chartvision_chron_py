# Phase 6: Wire Domain to Ports Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove infrastructure imports from domain layer by injecting `LLMPort` instead of importing `LLMManager`.

**Architecture:** Domain code will depend only on abstract `LLMPort` interface. Adapters (BedrockAdapter) are wired at composition root in API layer. Extractors change from `provider=` to `model=` parameter to match `LLMPort` signature.

**Tech Stack:** Python 3.11, pytest, async/await

**Key Files:**
- `app/core/extraction/text_extractor.py` - Uses `provider=` (should be `model=`)
- `app/core/extraction/vision_extractor.py` - Uses `provider=` (should be `model=`)
- `app/core/extraction/engine.py` - Imports `LLMManager` directly
- `app/api/job_processors.py` - Creates `ChronologyEngine`, needs to inject adapter

---

## Task 6.1: Update TextExtractor to Use LLMPort Interface

**Goal:** Change `provider="haiku"` to `model="haiku"` to match `LLMPort.generate()` signature.

**Files:**
- Modify: `app/core/extraction/text_extractor.py:86-96`
- Test: `tests/unit/core/extraction/test_text_extractor.py`

### Step 1: Update existing test to use `model=` parameter

The existing test at `tests/unit/domain/medical/engine/test_text_extractor.py` mocks the LLM. Verify it still works after our change.

```bash
PYTHONPATH=. pytest tests/unit/domain/medical/engine/test_text_extractor.py -v
```

### Step 2: Update text_extractor.py to use `model=` instead of `provider=`

Change line 89 from `provider="haiku"` to `model="haiku"`:

```python
# app/core/extraction/text_extractor.py - lines 85-96
# BEFORE:
response = await retry_with_backoff(
    self._llm.generate,
    prompt=prompt,
    provider="haiku",  # <-- OLD
    max_tokens=self._max_tokens,
    ...
)

# AFTER:
response = await retry_with_backoff(
    self._llm.generate,
    prompt=prompt,
    model="haiku",  # <-- NEW (matches LLMPort)
    max_tokens=self._max_tokens,
    ...
)
```

### Step 3: Run test to verify change works

```bash
PYTHONPATH=. pytest tests/unit/domain/medical/engine/test_text_extractor.py -v
```

Expected: PASS

---

## Task 6.2: Update VisionExtractor to Use LLMPort Interface

**Goal:** Change `provider="haiku"` to `model="haiku"` to match `LLMPort.generate_with_vision()` signature.

**Files:**
- Modify: `app/core/extraction/vision_extractor.py:94-105`
- Test: `tests/unit/domain/medical/engine/test_vision_extractor.py`

### Step 1: Update vision_extractor.py to use `model=` instead of `provider=`

Change line 98 from `provider="haiku"` to `model="haiku"`:

```python
# app/core/extraction/vision_extractor.py - lines 94-105
# BEFORE:
response = await retry_with_backoff(
    self._llm.generate_with_vision,
    prompt=prompt,
    images=images,
    provider="haiku",  # <-- OLD
    max_tokens=self._max_tokens,
    ...
)

# AFTER:
response = await retry_with_backoff(
    self._llm.generate_with_vision,
    prompt=prompt,
    images=images,
    model="haiku",  # <-- NEW (matches LLMPort)
    max_tokens=self._max_tokens,
    ...
)
```

### Step 2: Run test to verify change works

```bash
PYTHONPATH=. pytest tests/unit/domain/medical/engine/test_vision_extractor.py -v
```

Expected: PASS

---

## Task 6.3: Update Domain Extractors (app/domain/medical/engine/)

**Goal:** The `app/domain/medical/engine/` files are duplicates of `app/core/extraction/`. Apply same changes.

**Files:**
- Modify: `app/domain/medical/engine/text_extractor.py:89` - `provider=` → `model=`
- Modify: `app/domain/medical/engine/vision_extractor.py:98` - `provider=` → `model=`

### Step 1: Update domain text_extractor.py

Same change as Task 6.1 Step 2.

### Step 2: Update domain vision_extractor.py

Same change as Task 6.2 Step 1.

### Step 3: Run all extractor tests

```bash
PYTHONPATH=. pytest tests/unit/domain/medical/engine/test_text_extractor.py tests/unit/domain/medical/engine/test_vision_extractor.py -v
```

Expected: All PASS

---

## Task 6.4: Update ChronologyEngine to Accept LLMPort

**Goal:** Replace lazy `LLMManager` import with constructor injection of `LLMPort`.

**Files:**
- Modify: `app/core/extraction/engine.py`
- Create: `tests/unit/core/extraction/test_engine_injection.py`

### Step 1: Write test for LLMPort injection

```python
# tests/unit/core/extraction/test_engine_injection.py
"""Tests for ChronologyEngine port injection."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.core.extraction.engine import ChronologyEngine
from app.core.ports.llm import LLMPort


class TestChronologyEngineInjection:
    def test_accepts_llm_port(self):
        """Engine should accept LLMPort via constructor."""
        mock_llm = MagicMock(spec=LLMPort)
        engine = ChronologyEngine(llm=mock_llm)

        assert engine._llm_port is mock_llm

    def test_extractors_receive_injected_port(self):
        """Extractors should use the injected LLMPort."""
        mock_llm = MagicMock(spec=LLMPort)
        engine = ChronologyEngine(llm=mock_llm)

        # Access text_extractor property
        text_ext = engine.text_extractor
        assert text_ext is not None
        assert text_ext._llm is mock_llm

    def test_raises_without_llm(self):
        """Engine should raise if no LLM provided and lazy init disabled."""
        engine = ChronologyEngine(llm=None, allow_lazy_init=False)

        with pytest.raises(ValueError, match="LLM port required"):
            _ = engine.text_extractor

    def test_backward_compat_lazy_init(self):
        """For backward compatibility, allow lazy init if not disabled."""
        # This test verifies old code still works during migration
        engine = ChronologyEngine()  # No llm provided
        # Should not raise yet - lazy init is default
        assert engine._llm_port is None
```

### Step 2: Run test to verify it fails

```bash
PYTHONPATH=. pytest tests/unit/core/extraction/test_engine_injection.py -v
```

Expected: FAIL (engine doesn't have `llm=` parameter yet)

### Step 3: Update ChronologyEngine to accept LLMPort

```python
# app/core/extraction/engine.py - Update __init__ method

class ChronologyEngine:
    """
    Slim orchestrator for medical chronology extraction.

    Delegates to:
    - TextExtractor: LLM text extraction
    - VisionExtractor: Scanned page extraction
    - CitationResolver: Accurate page→exhibit citations

    Compatible with UnifiedChronologyEngine API for drop-in replacement.
    """

    def __init__(
        self,
        llm: "LLMPort" = None,  # NEW: Accept LLMPort
        llm_manager=None,  # DEPRECATED: For backward compatibility
        enable_recovery: bool = True,
        enable_parallel: bool = True,
        max_concurrent: int = 5,
        allow_lazy_init: bool = True,  # NEW: Control lazy init
    ):
        """Initialize engine with LLM port.

        Args:
            llm: LLMPort implementation (preferred)
            llm_manager: Deprecated - use llm parameter instead
            enable_recovery: Enable sparse entry recovery via vision retry
            enable_parallel: Enable parallel exhibit extraction
            max_concurrent: Maximum concurrent exhibit extractions (default 5)
            allow_lazy_init: Allow lazy LLMManager init (for backward compat)
        """
        # Prefer new llm parameter, fall back to deprecated llm_manager
        self._llm_port = llm or llm_manager
        self._allow_lazy_init = allow_lazy_init

        self._text_extractor: Optional[TextExtractor] = None
        self._vision_extractor: Optional[VisionExtractor] = None
        self._recovery_handler: Optional[RecoveryHandler] = None
        self._parallel_extractor: Optional[ParallelExtractor] = None
        self._citation_resolver: Optional[CitationResolver] = None
        self._enable_recovery = enable_recovery
        self._enable_parallel = enable_parallel
        self._max_concurrent = max_concurrent

    @property
    def llm(self):
        """Get LLM port, with optional lazy initialization."""
        if self._llm_port is None:
            if not self._allow_lazy_init:
                raise ValueError("LLM port required when allow_lazy_init=False")
            # Lazy init for backward compatibility
            try:
                from app.services.llm.llm_manager import LLMManager, LLMConfig, LLMProvider
                self._llm_port = LLMManager()
                config = LLMConfig(
                    provider=LLMProvider.BEDROCK,
                    model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
                    max_tokens=65000,
                    temperature=0.05,
                )
                self._llm_port.add_provider("haiku", config)
                logger.info("ChronologyEngine: LLM manager initialized with Haiku")
            except Exception as e:
                logger.error(f"Failed to initialize LLM manager: {e}")
                raise
        return self._llm_port

    # Backward compatibility alias
    @property
    def llm_manager(self):
        """Deprecated: Use llm property instead."""
        return self.llm

    @property
    def text_extractor(self) -> TextExtractor:
        """Lazy initialization of text extractor."""
        if self._text_extractor is None:
            self._text_extractor = TextExtractor(self.llm)
        return self._text_extractor

    @property
    def vision_extractor(self) -> VisionExtractor:
        """Lazy initialization of vision extractor."""
        if self._vision_extractor is None:
            self._vision_extractor = VisionExtractor(self.llm)
        return self._vision_extractor

    # ... rest of class unchanged
```

### Step 4: Run test to verify it passes

```bash
PYTHONPATH=. pytest tests/unit/core/extraction/test_engine_injection.py -v
```

Expected: PASS

### Step 5: Run all engine tests

```bash
PYTHONPATH=. pytest tests/unit/core/ -v
```

Expected: All PASS

---

## Task 6.5: Apply Same Changes to app/domain/medical/engine/

**Goal:** Keep `app/domain/` in sync with `app/core/` during migration.

**Files:**
- Modify: `app/domain/medical/engine/chronology_engine.py` - Same changes as Task 6.4

### Step 1: Apply ChronologyEngine changes

Copy the same `__init__`, `llm`, `llm_manager`, `text_extractor`, `vision_extractor` changes from Task 6.4.

### Step 2: Run domain tests

```bash
PYTHONPATH=. pytest tests/unit/domain/ -v
```

Expected: All PASS

---

## Task 6.6: Update API Layer to Inject Adapter

**Goal:** Create composition root that wires `BedrockAdapter` to `ChronologyEngine`.

**Files:**
- Modify: `app/api/job_processors.py:236-242, 462-477`

### Step 1: Update job_processors.py to inject BedrockAdapter

```python
# app/api/job_processors.py - around line 236

# BEFORE:
from app.domain.medical.engine import ChronologyEngine
...
engine = ChronologyEngine()

# AFTER:
from app.domain.medical.engine import ChronologyEngine
from app.adapters.llm import BedrockAdapter
...
llm = BedrockAdapter()
engine = ChronologyEngine(llm=llm)
```

Apply same change around line 477.

### Step 2: Verify API still works

```bash
PYTHONPATH=. python -c "
from app.api.job_processors import process_chartvision_job
print('API imports OK')
"
```

Expected: `API imports OK`

---

## Task 6.7: Run Full Test Suite

**Goal:** Verify all changes work together.

### Step 1: Run all unit tests

```bash
PYTHONPATH=. pytest tests/unit/ -v --tb=short
```

Expected: All tests pass (should be 116+ tests)

### Step 2: Verify adapter integration

```bash
PYTHONPATH=. python3 -c "
from app.adapters.llm import BedrockAdapter
from app.core.extraction.engine import ChronologyEngine
from app.core.ports.llm import LLMPort

# Create adapter and engine
llm = BedrockAdapter()
engine = ChronologyEngine(llm=llm, allow_lazy_init=False)

# Verify injection
assert isinstance(engine.llm, LLMPort)
assert engine.text_extractor._llm is llm
print('✓ Adapter injection working')
"
```

Expected: `✓ Adapter injection working`

---

## Success Criteria

- [ ] TextExtractor uses `model=` instead of `provider=`
- [ ] VisionExtractor uses `model=` instead of `provider=`
- [ ] ChronologyEngine accepts `LLMPort` via constructor
- [ ] Backward compatibility maintained (lazy init still works)
- [ ] API layer injects BedrockAdapter
- [ ] All 116+ tests pass
- [ ] No direct `LLMManager` imports in domain layer (except lazy init fallback)

---

## Future Work (Phase 7+)

After Phase 6 completes:

1. **Remove lazy init fallback** - Once all callers inject adapters
2. **Delete duplicate code** - Remove `app/domain/medical/engine/` (keep only `app/core/extraction/`)
3. **Extract prompt loading** - Move YAML loading to adapter layer
4. **Remove Bedrock error types from retry_utils** - Use domain exceptions
