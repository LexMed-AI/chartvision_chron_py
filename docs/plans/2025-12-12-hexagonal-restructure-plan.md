# Hexagonal Architecture Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure ChartVision from nested domain structure to hexagonal architecture with centralized prompts.

**Architecture:** Ports & Adapters pattern with `core/` (domain logic, no external deps), `adapters/` (Bedrock, PyMuPDF, Redis), and `config/prompts/` (all YAML).

**Tech Stack:** Python 3.11, FastAPI, AWS Bedrock, PyMuPDF, Redis, pytest

**Reference Design:** `docs/plans/2025-12-12-hexagonal-architecture-design.md`

---

## Phase 1: Create Directory Structure

### Task 1.1: Create Core Directory Structure

**Files:**
- Create: `app/core/__init__.py`
- Create: `app/core/models/__init__.py`
- Create: `app/core/extraction/__init__.py`
- Create: `app/core/builders/__init__.py`
- Create: `app/core/ports/__init__.py`

**Step 1: Create directories and init files**

```bash
mkdir -p app/core/models app/core/extraction app/core/builders app/core/ports
```

**Step 2: Create __init__.py files**

```python
# app/core/__init__.py
"""Core domain logic - no external dependencies."""
```

```python
# app/core/models/__init__.py
"""Domain models and entities."""
```

```python
# app/core/extraction/__init__.py
"""Extraction engine and processors."""
```

```python
# app/core/builders/__init__.py
"""Report builders and formatters."""
```

```python
# app/core/ports/__init__.py
"""Abstract interfaces for external dependencies."""
```

**Step 3: Verify structure**

Run: `ls -la app/core/*/`
Expected: Each directory contains `__init__.py`

---

### Task 1.2: Create Adapters Directory Structure

**Files:**
- Create: `app/adapters/__init__.py`
- Create: `app/adapters/llm/__init__.py`
- Create: `app/adapters/pdf/__init__.py`
- Create: `app/adapters/storage/__init__.py`
- Create: `app/adapters/export/__init__.py`

**Step 1: Create directories**

```bash
mkdir -p app/adapters/llm app/adapters/pdf app/adapters/storage app/adapters/export
```

**Step 2: Create __init__.py files**

```python
# app/adapters/__init__.py
"""External integration adapters."""
```

```python
# app/adapters/llm/__init__.py
"""LLM provider adapters."""
```

```python
# app/adapters/pdf/__init__.py
"""PDF processing adapters."""
```

```python
# app/adapters/storage/__init__.py
"""Storage adapters (Redis, filesystem)."""
```

```python
# app/adapters/export/__init__.py
"""Export format adapters (HTML, PDF, Markdown)."""
```

**Step 3: Verify structure**

Run: `ls -la app/adapters/*/`
Expected: Each directory contains `__init__.py`

---

### Task 1.3: Create Config Prompts Directory Structure

**Files:**
- Create: `app/config/prompts/_base/`
- Create: `app/config/prompts/extraction/`
- Create: `app/config/prompts/schemas/`

**Step 1: Create directories**

```bash
mkdir -p app/config/prompts/_base app/config/prompts/extraction app/config/prompts/schemas
```

**Step 2: Verify structure**

Run: `ls -la app/config/prompts/`
Expected: `_base/`, `extraction/`, `schemas/` directories

---

### Task 1.4: Create Workers Directory

**Files:**
- Create: `app/workers/__init__.py`

**Step 1: Create directory and init**

```bash
mkdir -p app/workers
```

```python
# app/workers/__init__.py
"""Background job workers."""
```

---

### Task 1.5: Create API Routes Directory

**Files:**
- Create: `app/api/routes/__init__.py`

**Step 1: Create directory and init**

```bash
mkdir -p app/api/routes
```

```python
# app/api/routes/__init__.py
"""API route modules."""
```

---

## Phase 2: Create Port Interfaces

### Task 2.1: Create Core Exceptions

**Files:**
- Create: `app/core/exceptions.py`
- Create: `tests/unit/core/test_exceptions.py`

**Step 1: Write the test**

```python
# tests/unit/core/test_exceptions.py
"""Tests for core exceptions."""
import pytest
from app.core.exceptions import (
    CoreError,
    LLMError,
    PDFError,
    ExtractionError,
    ValidationError,
    StorageError,
)


class TestExceptionHierarchy:
    def test_llm_error_is_core_error(self):
        error = LLMError("test")
        assert isinstance(error, CoreError)

    def test_pdf_error_is_core_error(self):
        error = PDFError("test")
        assert isinstance(error, CoreError)

    def test_extraction_error_is_core_error(self):
        error = ExtractionError("test")
        assert isinstance(error, CoreError)

    def test_validation_error_is_core_error(self):
        error = ValidationError("test")
        assert isinstance(error, CoreError)

    def test_storage_error_is_core_error(self):
        error = StorageError("test")
        assert isinstance(error, CoreError)

    def test_error_message_preserved(self):
        error = LLMError("specific message")
        assert str(error) == "specific message"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/test_exceptions.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create the exceptions module**

```python
# app/core/exceptions.py
"""Core domain exceptions.

All exceptions raised by core logic inherit from CoreError.
Adapters catch provider-specific errors and re-raise as these.
"""


class CoreError(Exception):
    """Base for all core domain errors."""
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

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/test_exceptions.py -v`
Expected: PASS (6 tests)

---

### Task 2.2: Create LLM Port Interface

**Files:**
- Create: `app/core/ports/llm.py`
- Create: `tests/unit/core/ports/test_llm_port.py`

**Step 1: Create test directory**

```bash
mkdir -p tests/unit/core/ports
touch tests/unit/core/ports/__init__.py
```

**Step 2: Write the test**

```python
# tests/unit/core/ports/test_llm_port.py
"""Tests for LLM port interface."""
import pytest
from dataclasses import dataclass
from app.core.ports.llm import LLMPort, ModelConfig


class TestModelConfig:
    def test_model_config_fields(self):
        config = ModelConfig(
            name="test-model",
            role="extraction",
            max_tokens=4000,
            temperature=0.1,
            timeout=120.0,
            context_window=200000,
            system_prompt="You are a test assistant.",
        )
        assert config.name == "test-model"
        assert config.max_tokens == 4000


class TestLLMPortInterface:
    def test_cannot_instantiate_abstract_port(self):
        with pytest.raises(TypeError):
            LLMPort()

    def test_concrete_implementation_works(self):
        class MockLLM(LLMPort):
            def get_model_config(self, model: str) -> ModelConfig:
                return ModelConfig(
                    name="mock", role="test", max_tokens=100,
                    temperature=0.0, timeout=10.0, context_window=1000,
                    system_prompt="test"
                )

            async def generate(self, prompt, model, **kwargs) -> str:
                return "mock response"

            async def generate_with_vision(self, prompt, images, model, **kwargs) -> str:
                return "mock vision response"

        mock = MockLLM()
        assert mock.get_model_config("test").name == "mock"
```

**Step 3: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/ports/test_llm_port.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Create the LLM port**

```python
# app/core/ports/llm.py
"""LLM port interface.

Defines the contract for LLM providers. Core code depends only on this
abstraction, not on specific implementations like Bedrock.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ModelConfig:
    """Configuration for a specific model.

    Loaded from config/models.json -> models.{model_key}
    """
    name: str           # e.g., "us.anthropic.claude-haiku-4-5-..."
    role: str           # e.g., "medical_data_extraction"
    max_tokens: int
    temperature: float
    timeout: float
    context_window: int
    system_prompt: str


class LLMPort(ABC):
    """Abstract interface for LLM providers.

    Implementations: BedrockAdapter
    """

    @abstractmethod
    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a model.

        Args:
            model: Model key ("haiku" or "sonnet")

        Returns:
            ModelConfig with all settings
        """
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
        """Generate text completion.

        Args:
            prompt: User prompt
            model: Model key ("haiku" or "sonnet")
            max_tokens: Override config max_tokens
            temperature: Override config temperature
            system: Override config system_prompt

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def generate_with_vision(
        self,
        prompt: str,
        images: List[bytes],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate completion from text and images.

        Args:
            prompt: User prompt
            images: List of image bytes (PNG)
            model: Model key
            max_tokens: Override config max_tokens
            temperature: Override config temperature
            system: Override config system_prompt

        Returns:
            Generated text response
        """
        pass
```

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/ports/test_llm_port.py -v`
Expected: PASS (3 tests)

---

### Task 2.3: Create PDF Port Interface

**Files:**
- Create: `app/core/ports/pdf.py`
- Create: `tests/unit/core/ports/test_pdf_port.py`

**Step 1: Write the test**

```python
# tests/unit/core/ports/test_pdf_port.py
"""Tests for PDF port interface."""
import pytest
from app.core.ports.pdf import PDFPort, Bookmark


class TestBookmark:
    def test_bookmark_fields(self):
        bm = Bookmark(
            title="1F",
            page_start=10,
            page_end=25,
            level=1,
        )
        assert bm.title == "1F"
        assert bm.page_start == 10
        assert bm.page_end == 25


class TestPDFPortInterface:
    def test_cannot_instantiate_abstract_port(self):
        with pytest.raises(TypeError):
            PDFPort()

    def test_concrete_implementation_works(self):
        class MockPDF(PDFPort):
            def extract_text(self, path, start_page, end_page) -> str:
                return "mock text"

            def extract_bookmarks(self, path):
                return [Bookmark("1F", 1, 10, 1)]

            def render_page_image(self, path, page, dpi=150) -> bytes:
                return b"mock image"

            def is_scanned_page(self, path, page) -> bool:
                return False

            def get_page_count(self, path) -> int:
                return 100

        mock = MockPDF()
        assert mock.extract_text("test.pdf", 1, 10) == "mock text"
        assert len(mock.extract_bookmarks("test.pdf")) == 1
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/ports/test_pdf_port.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create the PDF port**

```python
# app/core/ports/pdf.py
"""PDF port interface.

Defines the contract for PDF operations. Core code depends only on this
abstraction, not on specific implementations like PyMuPDF.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class Bookmark:
    """PDF bookmark/outline entry."""
    title: str
    page_start: int
    page_end: int
    level: int


class PDFPort(ABC):
    """Abstract interface for PDF operations.

    Implementations: PyMuPDFAdapter
    """

    @abstractmethod
    def extract_text(self, path: str, start_page: int, end_page: int) -> str:
        """Extract text from page range.

        Args:
            path: Path to PDF file
            start_page: Starting page (1-indexed)
            end_page: Ending page (inclusive)

        Returns:
            Extracted text
        """
        pass

    @abstractmethod
    def extract_bookmarks(self, path: str) -> List[Bookmark]:
        """Extract bookmarks/outline from PDF.

        Args:
            path: Path to PDF file

        Returns:
            List of Bookmark objects
        """
        pass

    @abstractmethod
    def render_page_image(self, path: str, page: int, dpi: int = 150) -> bytes:
        """Render page as PNG image.

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)
            dpi: Resolution for rendering

        Returns:
            PNG image bytes
        """
        pass

    @abstractmethod
    def is_scanned_page(self, path: str, page: int) -> bool:
        """Check if page is scanned (minimal text).

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)

        Returns:
            True if page appears to be scanned
        """
        pass

    @abstractmethod
    def get_page_count(self, path: str) -> int:
        """Get total page count.

        Args:
            path: Path to PDF file

        Returns:
            Number of pages
        """
        pass
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/ports/test_pdf_port.py -v`
Expected: PASS (3 tests)

---

### Task 2.4: Create Storage Port Interface

**Files:**
- Create: `app/core/ports/storage.py`
- Create: `tests/unit/core/ports/test_storage_port.py`

**Step 1: Write the test**

```python
# tests/unit/core/ports/test_storage_port.py
"""Tests for storage port interface."""
import pytest
from app.core.ports.storage import JobStoragePort


class TestStoragePortInterface:
    def test_cannot_instantiate_abstract_port(self):
        with pytest.raises(TypeError):
            JobStoragePort()

    def test_concrete_implementation_works(self):
        class MockStorage(JobStoragePort):
            def __init__(self):
                self._data = {}

            async def save_job(self, job_id, data):
                self._data[job_id] = data

            async def get_job(self, job_id):
                return self._data.get(job_id)

            async def update_job(self, job_id, updates):
                if job_id in self._data:
                    self._data[job_id].update(updates)

            async def delete_job(self, job_id):
                self._data.pop(job_id, None)

        mock = MockStorage()
        assert mock._data == {}
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/ports/test_storage_port.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create the storage port**

```python
# app/core/ports/storage.py
"""Storage port interface.

Defines the contract for job state persistence. Core code depends only on this
abstraction, not on specific implementations like Redis.
"""
from abc import ABC, abstractmethod
from typing import Optional


class JobStoragePort(ABC):
    """Abstract interface for job state persistence.

    Implementations: RedisAdapter
    """

    @abstractmethod
    async def save_job(self, job_id: str, data: dict) -> None:
        """Save job data.

        Args:
            job_id: Unique job identifier
            data: Job data dictionary
        """
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[dict]:
        """Retrieve job data.

        Args:
            job_id: Unique job identifier

        Returns:
            Job data or None if not found
        """
        pass

    @abstractmethod
    async def update_job(self, job_id: str, updates: dict) -> None:
        """Update job data.

        Args:
            job_id: Unique job identifier
            updates: Fields to update
        """
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> None:
        """Delete job data.

        Args:
            job_id: Unique job identifier
        """
        pass
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/ports/test_storage_port.py -v`
Expected: PASS (2 tests)

---

### Task 2.5: Update Ports __init__.py

**Files:**
- Modify: `app/core/ports/__init__.py`

**Step 1: Update exports**

```python
# app/core/ports/__init__.py
"""Abstract interfaces for external dependencies."""
from app.core.ports.llm import LLMPort, ModelConfig
from app.core.ports.pdf import PDFPort, Bookmark
from app.core.ports.storage import JobStoragePort

__all__ = [
    "LLMPort",
    "ModelConfig",
    "PDFPort",
    "Bookmark",
    "JobStoragePort",
]
```

**Step 2: Verify imports work**

Run: `PYTHONPATH=. python -c "from app.core.ports import LLMPort, PDFPort, JobStoragePort; print('OK')"`
Expected: `OK`

---

## Phase 3: Move YAML Prompts

### Task 3.1: Move Base Prompts

**Files:**
- Move: `app/domain/medical/engine/prompts/_base/*` → `app/config/prompts/_base/`

**Step 1: Copy files**

```bash
cp app/domain/medical/engine/prompts/_base/visit_types.yaml app/config/prompts/_base/
cp app/domain/medical/engine/prompts/_base/occurrence_schemas.yaml app/config/prompts/_base/
```

**Step 2: Verify files exist**

Run: `ls app/config/prompts/_base/`
Expected: `visit_types.yaml  occurrence_schemas.yaml`

---

### Task 3.2: Move Extraction Prompts

**Files:**
- Move: `app/domain/medical/engine/prompts/text_extraction.yaml` → `app/config/prompts/extraction/`
- Move: `app/domain/medical/engine/prompts/vision_extraction.yaml` → `app/config/prompts/extraction/`
- Move: `app/templates/dde_assessment.yaml` → `app/config/prompts/extraction/dde_section_a.yaml`

**Step 1: Copy files**

```bash
cp app/domain/medical/engine/prompts/text_extraction.yaml app/config/prompts/extraction/
cp app/domain/medical/engine/prompts/vision_extraction.yaml app/config/prompts/extraction/
cp app/templates/dde_assessment.yaml app/config/prompts/extraction/dde_section_a.yaml
```

**Step 2: Verify files exist**

Run: `ls app/config/prompts/extraction/`
Expected: `text_extraction.yaml  vision_extraction.yaml  dde_section_a.yaml`

---

### Task 3.3: Move Schema Templates

**Files:**
- Move: `app/templates/chartvision_chronology_template.yaml` → `app/config/prompts/schemas/`
- Move: `app/templates/f_medical_parsing_template.yaml` → `app/config/prompts/schemas/`

**Step 1: Copy files**

```bash
cp app/templates/chartvision_chronology_template.yaml app/config/prompts/schemas/
cp app/templates/f_medical_parsing_template.yaml app/config/prompts/schemas/
```

**Step 2: Verify files exist**

Run: `ls app/config/prompts/schemas/`
Expected: `chartvision_chronology_template.yaml  f_medical_parsing_template.yaml`

---

### Task 3.4: Rename Model Config

**Files:**
- Move: `app/config/two_model_config.json` → `app/config/models.json`

**Step 1: Copy file**

```bash
cp app/config/two_model_config.json app/config/models.json
```

**Step 2: Remove Google/Gemini from models.json**

Edit `app/config/models.json` and remove the `"gemini"` entry from the `"models"` section.

**Step 3: Verify file exists**

Run: `ls app/config/models.json`
Expected: `app/config/models.json`

---

## Phase 4: Move Core Logic

### Import Mapping Reference

After copying files, update imports in each module using this mapping:

| Old Import Path | New Import Path |
|-----------------|-----------------|
| `app.services.citation_resolver` | `app.core.extraction.citation_resolver` |
| `app.domain.medical.engine.*` | `app.core.extraction.*` |
| `app.domain.medical.chartvision_models` | `app.core.models.chartvision` |
| `app.domain.medical.models` | `app.core.models.entry` |
| `app.domain.medical.chartvision_builder` | `app.core.builders.chartvision_builder` |
| `app.domain.medical.builders.*` | `app.core.builders.*` |
| `app.domain.medical.chronology_utils` | `app.core.extraction.utils` |

**Execution Order:**
1. Copy models first (no internal deps)
2. Copy extraction modules (deps on models)
3. Copy builders (deps on models + extraction)
4. Update all imports in copied files
5. Create prompt loader
6. Verify all imports work

---

### Task 4.1: Move Extraction Modules

**Files:**
- Copy: `app/domain/medical/engine/*.py` → `app/core/extraction/`

**Step 1: Copy all extraction files**

```bash
cp app/domain/medical/engine/chronology_engine.py app/core/extraction/engine.py
cp app/domain/medical/engine/text_extractor.py app/core/extraction/
cp app/domain/medical/engine/vision_extractor.py app/core/extraction/
cp app/domain/medical/engine/parallel_extractor.py app/core/extraction/
cp app/domain/medical/engine/response_parser.py app/core/extraction/
cp app/domain/medical/engine/recovery_handler.py app/core/extraction/
cp app/domain/medical/engine/text_chunker.py app/core/extraction/
cp app/domain/medical/engine/chunk_retry_handler.py app/core/extraction/
cp app/domain/medical/engine/retry_utils.py app/core/extraction/
cp app/domain/medical/engine/constants.py app/core/extraction/
cp app/domain/medical/engine/llm_config.py app/core/extraction/
cp app/domain/medical/chronology_utils.py app/core/extraction/utils.py
cp app/services/citation_resolver.py app/core/extraction/
```

**Step 2: Verify files copied**

Run: `ls app/core/extraction/`
Expected: All extraction module files

**Step 3: Update imports in copied files**

Update these imports in `app/core/extraction/engine.py`:
```python
# OLD: from app.services.citation_resolver import CitationResolver
# NEW:
from app.core.extraction.citation_resolver import CitationResolver
```

Relative imports (`.text_extractor`, `.vision_extractor`, etc.) remain unchanged since files are in same directory.

---

### Task 4.2: Move Builder Modules

**Files:**
- Copy: `app/domain/medical/chartvision_builder.py` → `app/core/builders/`
- Copy: `app/domain/medical/builders/occurrence_formatter.py` → `app/core/builders/`

**Step 1: Copy builder files**

```bash
cp app/domain/medical/chartvision_builder.py app/core/builders/
cp app/domain/medical/chartvision_report_generator.py app/core/builders/report_generator.py
cp app/domain/medical/builders/occurrence_formatter.py app/core/builders/
```

**Step 2: Verify files copied**

Run: `ls app/core/builders/`
Expected: `chartvision_builder.py  report_generator.py  occurrence_formatter.py  __init__.py`

**Step 3: Update imports in copied files**

Update `app/core/builders/chartvision_builder.py`:
```python
# OLD: from .chartvision_models import (...)
# NEW:
from app.core.models.chartvision import (...)

# OLD: from .builders import OccurrenceFormatter
# NEW:
from app.core.builders.occurrence_formatter import OccurrenceFormatter
```

---

### Task 4.3: Move Model Modules

**Files:**
- Copy: `app/domain/medical/models.py` → `app/core/models/entry.py`
- Copy: `app/domain/medical/chartvision_models.py` → `app/core/models/chartvision.py`

**Step 1: Copy model files**

```bash
cp app/domain/medical/models.py app/core/models/entry.py
cp app/domain/medical/chartvision_models.py app/core/models/chartvision.py
```

**Step 2: Verify files copied**

Run: `ls app/core/models/`
Expected: `entry.py  chartvision.py  __init__.py`

---

### Task 4.4: Create Prompt Loader

**Files:**
- Create: `app/core/extraction/prompt_loader.py`
- Create: `tests/unit/core/extraction/test_prompt_loader.py`

**Step 1: Write the test**

```python
# tests/unit/core/extraction/test_prompt_loader.py
"""Tests for prompt loader."""
import pytest
from pathlib import Path
from app.core.extraction.prompt_loader import PromptLoader


class TestPromptLoader:
    def test_load_text_extraction_config(self, tmp_path):
        # Create test YAML
        prompts_dir = tmp_path / "prompts" / "extraction"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "text_extraction.yaml").write_text("""
system_prompt: "Test system prompt"
user_prompt: "Test user prompt"
""")
        loader = PromptLoader(tmp_path / "prompts")
        config = loader.load("text_extraction")

        assert config["system_prompt"] == "Test system prompt"
        assert config["user_prompt"] == "Test user prompt"

    def test_load_missing_config_raises(self, tmp_path):
        loader = PromptLoader(tmp_path / "prompts")

        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent")
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_prompt_loader.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create the prompt loader**

```python
# app/core/extraction/prompt_loader.py
"""Prompt configuration loader.

Loads YAML prompt configurations from config/prompts/ directory.
"""
from pathlib import Path
from typing import Any, Dict
import yaml


class PromptLoader:
    """Load prompt configurations from YAML files."""

    def __init__(self, prompts_dir: Path = None):
        """Initialize loader.

        Args:
            prompts_dir: Path to prompts directory.
                         Defaults to app/config/prompts/
        """
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent.parent.parent / "config" / "prompts"
        self._prompts_dir = prompts_dir
        self._cache: Dict[str, Dict[str, Any]] = {}

    def load(self, name: str) -> Dict[str, Any]:
        """Load a prompt configuration by name.

        Args:
            name: Config name (e.g., "text_extraction", "dde_section_a")

        Returns:
            Dictionary with prompt configuration

        Raises:
            FileNotFoundError: If config file not found
        """
        if name in self._cache:
            return self._cache[name]

        # Try extraction/ subdirectory first
        path = self._prompts_dir / "extraction" / f"{name}.yaml"
        if not path.exists():
            # Try schemas/ subdirectory
            path = self._prompts_dir / "schemas" / f"{name}.yaml"
        if not path.exists():
            # Try root prompts directory
            path = self._prompts_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt config not found: {name}")

        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self._cache[name] = config
        return config

    def load_base(self, name: str) -> Dict[str, Any]:
        """Load a base configuration.

        Args:
            name: Base config name (e.g., "visit_types")

        Returns:
            Dictionary with base configuration
        """
        path = self._prompts_dir / "_base" / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Base config not found: {name}")

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/core/extraction/test_prompt_loader.py -v`
Expected: PASS (2 tests)

---

### Task 4.5: Verify All Core Module Imports

**Step 1: Test that all new core modules can be imported**

```bash
PYTHONPATH=. python3 -c "
from app.core.extraction.engine import ChronologyEngine
from app.core.extraction.text_extractor import TextExtractor
from app.core.extraction.response_parser import ResponseParser
from app.core.builders.chartvision_builder import ChartVisionBuilder
from app.core.models.chartvision import ChartVisionReport
print('All core imports OK')
"
```

Expected: `All core imports OK`

**Step 2: If imports fail, fix remaining import issues before proceeding**

---

## Phase 5: Create Adapters

### Task 5.1: Create Bedrock Adapter

**Files:**
- Create: `app/adapters/llm/bedrock.py`
- Create: `tests/unit/adapters/llm/test_bedrock.py`

**Step 1: Create test directory**

```bash
mkdir -p tests/unit/adapters/llm
touch tests/unit/adapters/llm/__init__.py
```

**Step 2: Write the test**

```python
# tests/unit/adapters/llm/test_bedrock.py
"""Tests for Bedrock adapter."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.adapters.llm.bedrock import BedrockAdapter
from app.core.ports.llm import LLMPort


class TestBedrockAdapter:
    def test_implements_llm_port(self):
        with patch("app.adapters.llm.bedrock.LLMManager"):
            adapter = BedrockAdapter()
            assert isinstance(adapter, LLMPort)

    def test_get_model_config_haiku(self):
        with patch("app.adapters.llm.bedrock.LLMManager"):
            adapter = BedrockAdapter()
            # Mock the config loading
            adapter._config = {
                "models": {
                    "haiku": {
                        "name": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                        "role": "medical_data_extraction",
                        "max_tokens": 65536,
                        "temperature": 0.1,
                        "timeout": 120.0,
                        "context_window": 200000,
                        "system_prompt": "Test prompt"
                    }
                }
            }
            config = adapter.get_model_config("haiku")
            assert config.name == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
            assert config.role == "medical_data_extraction"
```

**Step 3: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/adapters/llm/test_bedrock.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Create the Bedrock adapter**

```python
# app/adapters/llm/bedrock.py
"""Bedrock LLM adapter.

Implements LLMPort interface using AWS Bedrock.
Wraps existing LLMManager to maintain compatibility.
"""
import json
from pathlib import Path
from typing import List, Optional

from app.core.ports.llm import LLMPort, ModelConfig
from app.core.exceptions import LLMError


class BedrockAdapter(LLMPort):
    """AWS Bedrock implementation of LLMPort.

    Wraps existing LLMManager for backward compatibility.
    """

    def __init__(self, config_path: Path = None):
        """Initialize adapter.

        Args:
            config_path: Path to models.json config file.
                         Defaults to app/config/models.json
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "models.json"

        self._config = self._load_config(config_path)
        self._manager = None  # Lazy init

    def _load_config(self, path: Path) -> dict:
        """Load model configuration."""
        if not path.exists():
            return {"models": {}}
        with open(path, "r") as f:
            return json.load(f)

    @property
    def manager(self):
        """Lazy-initialize LLM manager."""
        if self._manager is None:
            try:
                from app.services.llm.llm_manager import LLMManager
                self._manager = LLMManager()
            except ImportError:
                raise LLMError("LLMManager not available")
        return self._manager

    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a model."""
        models = self._config.get("models", {})
        if model not in models:
            raise LLMError(f"Unknown model: {model}")

        cfg = models[model]
        return ModelConfig(
            name=cfg["name"],
            role=cfg["role"],
            max_tokens=cfg["max_tokens"],
            temperature=cfg["temperature"],
            timeout=cfg["timeout"],
            context_window=cfg["context_window"],
            system_prompt=cfg["system_prompt"],
        )

    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate text completion via Bedrock."""
        try:
            config = self.get_model_config(model)
            return await self.manager.generate(
                prompt=prompt,
                provider=model,
                max_tokens=max_tokens or config.max_tokens,
                temperature=temperature or config.temperature,
                system=system or config.system_prompt,
            )
        except Exception as e:
            raise LLMError(f"Bedrock generate failed: {e}") from e

    async def generate_with_vision(
        self,
        prompt: str,
        images: List[bytes],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate completion from text and images via Bedrock."""
        try:
            config = self.get_model_config(model)
            return await self.manager.generate_with_vision(
                prompt=prompt,
                images=images,
                provider=model,
                max_tokens=max_tokens or config.max_tokens,
                temperature=temperature or config.temperature,
                system=system or config.system_prompt,
            )
        except Exception as e:
            raise LLMError(f"Bedrock vision failed: {e}") from e
```

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/adapters/llm/test_bedrock.py -v`
Expected: PASS (2 tests)

---

### Task 5.2: Create PyMuPDF Adapter

**Files:**
- Create: `app/adapters/pdf/pymupdf.py`
- Create: `tests/unit/adapters/pdf/test_pymupdf.py`

**Step 1: Create test directory**

```bash
mkdir -p tests/unit/adapters/pdf
touch tests/unit/adapters/pdf/__init__.py
```

**Step 2: Write the test**

```python
# tests/unit/adapters/pdf/test_pymupdf.py
"""Tests for PyMuPDF adapter."""
import pytest
from unittest.mock import MagicMock, patch
from app.adapters.pdf.pymupdf import PyMuPDFAdapter
from app.core.ports.pdf import PDFPort


class TestPyMuPDFAdapter:
    def test_implements_pdf_port(self):
        adapter = PyMuPDFAdapter()
        assert isinstance(adapter, PDFPort)
```

**Step 3: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/adapters/pdf/test_pymupdf.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Create the PyMuPDF adapter**

```python
# app/adapters/pdf/pymupdf.py
"""PyMuPDF adapter.

Implements PDFPort interface using PyMuPDF (fitz).
Wraps existing bookmark_extractor and preprocessing modules.
"""
from typing import List

import fitz  # PyMuPDF

from app.core.ports.pdf import PDFPort, Bookmark
from app.core.exceptions import PDFError


class PyMuPDFAdapter(PDFPort):
    """PyMuPDF implementation of PDFPort."""

    def extract_text(self, path: str, start_page: int, end_page: int) -> str:
        """Extract text from page range."""
        try:
            doc = fitz.open(path)
            parts = []
            # Convert to 0-indexed
            for i in range(start_page - 1, min(end_page, len(doc))):
                text = doc[i].get_text() or ""
                parts.append(text)
            doc.close()
            return "\n".join(parts)
        except Exception as e:
            raise PDFError(f"Failed to extract text: {e}") from e

    def extract_bookmarks(self, path: str) -> List[Bookmark]:
        """Extract bookmarks from PDF."""
        try:
            doc = fitz.open(path)
            toc = doc.get_toc()
            doc.close()

            bookmarks = []
            for i, (level, title, page) in enumerate(toc):
                # Calculate end page from next bookmark or doc end
                if i + 1 < len(toc):
                    end_page = toc[i + 1][2] - 1
                else:
                    end_page = len(doc)

                bookmarks.append(Bookmark(
                    title=title,
                    page_start=page,
                    page_end=end_page,
                    level=level,
                ))
            return bookmarks
        except Exception as e:
            raise PDFError(f"Failed to extract bookmarks: {e}") from e

    def render_page_image(self, path: str, page: int, dpi: int = 150) -> bytes:
        """Render page as PNG image."""
        try:
            doc = fitz.open(path)
            pix = doc[page - 1].get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            doc.close()
            return img_bytes
        except Exception as e:
            raise PDFError(f"Failed to render page: {e}") from e

    def is_scanned_page(self, path: str, page: int) -> bool:
        """Check if page is scanned (minimal text)."""
        try:
            doc = fitz.open(path)
            text = doc[page - 1].get_text() or ""
            doc.close()
            # Consider scanned if less than 100 chars
            return len(text.strip()) < 100
        except Exception as e:
            raise PDFError(f"Failed to check page: {e}") from e

    def get_page_count(self, path: str) -> int:
        """Get total page count."""
        try:
            doc = fitz.open(path)
            count = len(doc)
            doc.close()
            return count
        except Exception as e:
            raise PDFError(f"Failed to get page count: {e}") from e
```

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/adapters/pdf/test_pymupdf.py -v`
Expected: PASS (1 test)

---

## Phase 6: Update Imports and Wire Together

### Task 6.1: Update Core Extraction __init__.py

**Files:**
- Modify: `app/core/extraction/__init__.py`

**Step 1: Update exports**

```python
# app/core/extraction/__init__.py
"""Extraction engine and processors."""
from app.core.extraction.engine import ChronologyEngine
from app.core.extraction.text_extractor import TextExtractor
from app.core.extraction.vision_extractor import VisionExtractor
from app.core.extraction.parallel_extractor import ParallelExtractor
from app.core.extraction.response_parser import ResponseParser
from app.core.extraction.prompt_loader import PromptLoader

__all__ = [
    "ChronologyEngine",
    "TextExtractor",
    "VisionExtractor",
    "ParallelExtractor",
    "ResponseParser",
    "PromptLoader",
]
```

---

### Task 6.2: Update Core Builders __init__.py

**Files:**
- Modify: `app/core/builders/__init__.py`

**Step 1: Update exports**

```python
# app/core/builders/__init__.py
"""Report builders and formatters."""
from app.core.builders.chartvision_builder import ChartVisionBuilder
from app.core.builders.occurrence_formatter import OccurrenceFormatter

__all__ = [
    "ChartVisionBuilder",
    "OccurrenceFormatter",
]
```

---

### Task 6.3: Update Adapters __init__.py Files

**Files:**
- Modify: `app/adapters/llm/__init__.py`
- Modify: `app/adapters/pdf/__init__.py`

**Step 1: Update LLM adapter exports**

```python
# app/adapters/llm/__init__.py
"""LLM provider adapters."""
from app.adapters.llm.bedrock import BedrockAdapter

__all__ = ["BedrockAdapter"]
```

**Step 2: Update PDF adapter exports**

```python
# app/adapters/pdf/__init__.py
"""PDF processing adapters."""
from app.adapters.pdf.pymupdf import PyMuPDFAdapter

__all__ = ["PyMuPDFAdapter"]
```

---

### Task 6.4: Move Tests to New Structure

**Files:**
- Move: `tests/unit/domain/medical/engine/*` → `tests/unit/core/extraction/`

**Step 1: Create test directories**

```bash
mkdir -p tests/unit/core/extraction tests/unit/core/builders tests/unit/core/models
```

**Step 2: Copy test files**

```bash
cp tests/unit/domain/medical/engine/*.py tests/unit/core/extraction/
```

**Step 3: Update test imports**

Each test file needs imports updated from:
```python
from app.domain.medical.engine.X import Y
```
to:
```python
from app.core.extraction.X import Y
```

---

### Task 6.5: Run Full Test Suite

**Step 1: Run all tests**

Run: `PYTHONPATH=. pytest tests/ -v --tb=short`
Expected: All tests pass

---

## Phase 7: Cleanup

### Task 7.1: Verify New Structure Works

**Step 1: Run application**

```bash
PYTHONPATH=. python -m uvicorn app.api.ere_api:create_app --factory --host 0.0.0.0 --port 8811
```

Expected: Server starts without import errors

**Step 2: Hit health endpoint**

```bash
curl http://localhost:8811/api/v1/ere/health
```

Expected: `{"status": "healthy"}`

---

### Task 7.2: Delete Old Directories (AFTER VERIFICATION)

**Files:**
- Delete: `app/domain/` (entire directory)
- Delete: `app/templates/` (entire directory)
- Delete: `app/services/pdf/parsers/dde_parser.py`
- Delete: `app/services/llm/prompts/` (entire directory)
- Delete: `tests/unit/domain/` (entire directory)

**Step 1: Delete only after all tests pass**

```bash
rm -rf app/domain/
rm -rf app/templates/
rm -rf app/services/pdf/parsers/dde_parser.py
rm -rf app/services/llm/prompts/
rm -rf tests/unit/domain/
```

**Step 2: Run tests again**

Run: `PYTHONPATH=. pytest tests/ -v`
Expected: All tests pass

---

## Success Criteria Checklist

- [ ] All port interfaces created (`core/ports/`)
- [ ] All core logic moved (`core/extraction/`, `core/builders/`, `core/models/`)
- [ ] All adapters created (`adapters/llm/`, `adapters/pdf/`)
- [ ] All YAML prompts in `config/prompts/`
- [ ] All tests pass
- [ ] API endpoints work
- [ ] Old directories deleted
