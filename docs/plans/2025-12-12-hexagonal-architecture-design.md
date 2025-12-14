# Hexagonal Architecture Restructure

**Date:** 2025-12-12
**Status:** Approved
**Goal:** Platform-scale architecture supporting throughput, feature, provider, and team scaling

---

## Overview

Restructure ChartVision from nested domain structure to hexagonal architecture (ports & adapters) with centralized configuration. This is a **reorganization only** - all existing logic preserved.

### Key Principles

1. **Core has no external dependencies** - Pure domain logic, only uses abstract ports
2. **Config-driven** - Document types, prompts, and model settings all in YAML
3. **Adapters are swappable** - Bedrock today, other providers tomorrow
4. **Flat structure** - No more `domain.medical.engine.*` deep nesting

---

## Final Directory Structure

```
app/
├── api/                              # HTTP Layer
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chartvision.py
│   │   ├── ere.py
│   │   └── health.py
│   ├── schemas.py
│   └── middleware.py
│
├── core/                             # Domain Logic (NO external deps)
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── exhibit.py
│   │   ├── entry.py
│   │   └── job.py
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── engine.py                 # Unified - handles F-section + DDE
│   │   ├── text_extractor.py
│   │   ├── vision_extractor.py
│   │   ├── parallel_extractor.py
│   │   ├── response_parser.py
│   │   ├── recovery_handler.py
│   │   ├── text_chunker.py
│   │   ├── chunk_retry_handler.py
│   │   ├── retry_utils.py
│   │   ├── prompt_loader.py          # NEW: loads YAML by document type
│   │   └── constants.py
│   ├── builders/
│   │   ├── __init__.py
│   │   ├── chartvision_builder.py
│   │   └── occurrence_formatter.py
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── llm.py
│   │   ├── pdf.py
│   │   └── storage.py
│   └── exceptions.py
│
├── adapters/                         # External Integrations
│   ├── __init__.py
│   ├── llm/
│   │   ├── __init__.py
│   │   └── bedrock.py
│   ├── pdf/
│   │   ├── __init__.py
│   │   └── pymupdf.py
│   ├── storage/
│   │   ├── __init__.py
│   │   └── redis.py
│   └── export/
│       ├── __init__.py
│       ├── html.py
│       ├── markdown.py
│       └── pdf.py
│
├── config/                           # All Configuration
│   ├── __init__.py
│   ├── settings.py
│   ├── models.json
│   └── prompts/
│       ├── _base/
│       │   ├── visit_types.yaml
│       │   └── occurrence_schemas.yaml
│       ├── extraction/
│       │   ├── text_extraction.yaml
│       │   ├── vision_extraction.yaml
│       │   ├── f_section.yaml
│       │   └── dde_section_a.yaml
│       └── schemas/
│           └── chartvision_chronology.yaml
│
├── workers/
│   ├── __init__.py
│   └── job_handlers.py
│
└── ui/
    ├── index.html
    └── styles.css
```

---

## Migration Mapping

### File Moves (Logic Unchanged)

| Current Path | New Path |
|--------------|----------|
| `domain/medical/engine/chronology_engine.py` | `core/extraction/engine.py` |
| `domain/medical/engine/text_extractor.py` | `core/extraction/text_extractor.py` |
| `domain/medical/engine/vision_extractor.py` | `core/extraction/vision_extractor.py` |
| `domain/medical/engine/parallel_extractor.py` | `core/extraction/parallel_extractor.py` |
| `domain/medical/engine/response_parser.py` | `core/extraction/response_parser.py` |
| `domain/medical/engine/recovery_handler.py` | `core/extraction/recovery_handler.py` |
| `domain/medical/engine/text_chunker.py` | `core/extraction/text_chunker.py` |
| `domain/medical/engine/chunk_retry_handler.py` | `core/extraction/chunk_retry_handler.py` |
| `domain/medical/engine/retry_utils.py` | `core/extraction/retry_utils.py` |
| `domain/medical/engine/constants.py` | `core/extraction/constants.py` |
| `domain/medical/engine/llm_config.py` | `core/extraction/llm_config.py` |
| `domain/medical/chartvision_builder.py` | `core/builders/chartvision_builder.py` |
| `domain/medical/chartvision_models.py` | `core/models/chartvision.py` |
| `domain/medical/chartvision_report_generator.py` | `core/builders/report_generator.py` |
| `domain/medical/chronology_utils.py` | `core/extraction/utils.py` |
| `domain/medical/models.py` | `core/models/entry.py` |
| `domain/medical/builders/occurrence_formatter.py` | `core/builders/occurrence_formatter.py` |
| `services/llm/llm_manager.py` | `adapters/llm/bedrock.py` |
| `services/pdf/bookmarks/bookmark_extractor.py` | `adapters/pdf/pymupdf.py` |
| `services/pdf/preprocessing.py` | `adapters/pdf/pymupdf.py` |
| `services/generators/html_report_generator.py` | `adapters/export/html.py` |
| `services/generators/markdown_converter.py` | `adapters/export/markdown.py` |
| `services/generators/report_exporter.py` | `adapters/export/pdf.py` |
| `services/citation_resolver.py` | `core/extraction/citation_resolver.py` |
| `api/ere_api.py` | `api/routes/` (split into modules) |
| `api/job_processors.py` | `workers/job_handlers.py` |
| `api/schemas.py` | `api/schemas.py` |

### Prompt/Template Moves

| Current Path | New Path |
|--------------|----------|
| `domain/medical/engine/prompts/_base/visit_types.yaml` | `config/prompts/_base/visit_types.yaml` |
| `domain/medical/engine/prompts/_base/occurrence_schemas.yaml` | `config/prompts/_base/occurrence_schemas.yaml` |
| `domain/medical/engine/prompts/text_extraction.yaml` | `config/prompts/extraction/text_extraction.yaml` |
| `domain/medical/engine/prompts/vision_extraction.yaml` | `config/prompts/extraction/vision_extraction.yaml` |
| `templates/dde_assessment.yaml` | `config/prompts/extraction/dde_section_a.yaml` |
| `templates/f_medical_parsing_template.yaml` | `config/prompts/extraction/f_section.yaml` |
| `templates/chartvision_chronology_template.yaml` | `config/prompts/schemas/chartvision_chronology.yaml` |
| `config/two_model_config.json` | `config/models.json` |

### Deletions

| File | Reason |
|------|--------|
| `services/pdf/parsers/dde_parser.py` | Logic merged into engine, prompts to YAML |
| `services/llm/prompts/*.py` | Prompt building simplified, YAML-driven |
| `domain/` directory | Flattened to `core/` |
| `templates/` directory | Moved to `config/prompts/` |

---

## Port Interfaces

### LLMPort

```python
# core/ports/llm.py
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class ModelConfig:
    name: str
    role: str
    max_tokens: int
    temperature: float
    timeout: float
    context_window: int
    system_prompt: str

class LLMPort(ABC):
    """Bedrock LLM interface - config-driven."""

    @abstractmethod
    def get_model_config(self, model: str) -> ModelConfig:
        """Get config for 'haiku' or 'sonnet'."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        pass

    @abstractmethod
    async def generate_with_vision(
        self,
        prompt: str,
        images: List[bytes],
        model: str,
        **kwargs,
    ) -> str:
        pass
```

### PDFPort

```python
# core/ports/pdf.py
from abc import ABC, abstractmethod
from typing import List
from core.models.exhibit import Bookmark

class PDFPort(ABC):
    """Abstract interface for PDF operations."""

    @abstractmethod
    def extract_text(self, path: str, start_page: int, end_page: int) -> str:
        pass

    @abstractmethod
    def extract_bookmarks(self, path: str) -> List[Bookmark]:
        pass

    @abstractmethod
    def render_page_image(self, path: str, page: int, dpi: int = 150) -> bytes:
        pass

    @abstractmethod
    def is_scanned_page(self, path: str, page: int) -> bool:
        pass
```

### JobStoragePort

```python
# core/ports/storage.py
from abc import ABC, abstractmethod
from typing import Optional

class JobStoragePort(ABC):
    """Abstract interface for job state persistence."""

    @abstractmethod
    async def save_job(self, job_id: str, data: dict) -> None:
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def update_job(self, job_id: str, updates: dict) -> None:
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> None:
        pass
```

---

## Core Exceptions

```python
# core/exceptions.py
class CoreError(Exception):
    """Base for all core errors."""
    pass

class LLMError(CoreError):
    """LLM operation failed after retries."""
    pass

class PDFError(CoreError):
    """PDF operation failed."""
    pass

class ExtractionError(CoreError):
    """Extraction logic failed."""
    pass

class ValidationError(CoreError):
    """Data validation failed."""
    pass

class StorageError(CoreError):
    """Storage operation failed."""
    pass
```

---

## Data Flow

```
1. API Layer (api/routes/)
   │
   │  POST /api/v1/chartvision/process
   │
   ▼
2. Job Creation (api/routes/chartvision.py)
   │
   │  → Validate request (schemas/)
   │  → Create job ID
   │  → Store job via JobStoragePort
   │  → Queue background task
   │
   ▼
3. Worker (workers/job_handlers.py)
   │
   │  → Load job from storage
   │  → Instantiate adapters:
   │      llm = BedrockAdapter(config)
   │      pdf = PyMuPDFAdapter()
   │  → Instantiate core with ports:
   │      engine = ChronologyEngine(llm, pdf, prompt_loader)
   │
   ▼
4. Core Processing (core/extraction/engine.py)
   │
   │  → Extract bookmarks via PDFPort
   │  → Filter exhibits by section type
   │  → Load prompts based on document type (F-section or DDE)
   │  → For each exhibit:
   │      → Extract text via PDFPort
   │      → Extract entries via TextExtractor (uses LLMPort)
   │      → Recovery via VisionExtractor if sparse (uses LLMPort)
   │  → Build chronology via ChartVisionBuilder
   │
   ▼
5. Response (back up through layers)
   │
   │  → Store results via JobStoragePort
   │  → Return job status to API
   │  → Client polls for completion
```

---

## Error Handling

| Layer | Handles | Propagates |
|-------|---------|------------|
| Adapters | Provider-specific errors (throttling, timeouts) | Core exceptions (LLMError, PDFError) |
| Core | Domain logic errors (parse failures, sparse entries) | ProcessingError, ExtractionError |
| Workers | Job-level errors | Job status update (failed + message) |
| API | HTTP errors | JSON error response |

---

## Testing Strategy

```
tests/
├── unit/
│   ├── core/                    # Test core with mock ports
│   │   ├── extraction/
│   │   │   ├── test_engine.py
│   │   │   ├── test_text_extractor.py
│   │   │   ├── test_vision_extractor.py
│   │   │   └── ...
│   │   └── builders/
│   └── adapters/                # Test adapters in isolation
│       ├── test_bedrock.py
│       └── test_pymupdf.py
├── integration/
│   └── test_full_pipeline.py
└── fixtures/
    ├── mock_llm.py
    ├── mock_pdf.py
    └── sample_responses/
```

Existing 82 tests move to `tests/unit/core/extraction/` with import updates only.

---

## Implementation Plan

### Phase 1: Create Structure (No Breaking Changes)
1. Create `app/core/` directory structure
2. Create `app/adapters/` directory structure
3. Create `app/config/prompts/` and move YAML files
4. Create port interfaces (`core/ports/`)
5. Create `core/exceptions.py`

### Phase 2: Move Core Logic
1. Move extraction modules to `core/extraction/`
2. Move builders to `core/builders/`
3. Move models to `core/models/`
4. Update internal imports

### Phase 3: Create Adapters
1. Create `BedrockAdapter` implementing `LLMPort` (wraps existing LLMManager)
2. Create `PyMuPDFAdapter` implementing `PDFPort` (wraps existing code)
3. Create `RedisAdapter` implementing `JobStoragePort`

### Phase 4: Wire Together
1. Update extractors to receive ports via constructor
2. Update engine to use prompt_loader for document types
3. Merge DDE logic into engine (config-driven)
4. Update workers to instantiate adapters and inject into core

### Phase 5: Cleanup
1. Delete old `domain/` directory
2. Delete old `templates/` directory
3. Delete `dde_parser.py`
4. Update all external imports (API, tests)
5. Run full test suite

### Phase 6: Verify
1. Run all 82+ tests
2. Manual smoke test with sample PDF
3. Verify API endpoints work

---

## Success Criteria

- [ ] All 82 existing tests pass
- [ ] API endpoints unchanged (`/api/v1/chartvision/*`, `/api/v1/ere/*`)
- [ ] No logic changes - pure reorganization
- [ ] Core has zero imports from adapters or external libraries
- [ ] All YAML prompts in `config/prompts/`
- [ ] DDE parsing works via config, not separate parser
