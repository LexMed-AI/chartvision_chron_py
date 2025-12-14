# Phase 5: Adapters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create adapter classes that implement port interfaces by wrapping existing service code.

**Architecture:** Thin wrappers around `app/services/` code that implement `app/core/ports/` interfaces. Services remain unchanged; adapters translate between port contracts and service implementations.

**Tech Stack:** Python 3.11, AWS Bedrock (boto3), PyMuPDF (fitz), pytest

**Reference:** `docs/plans/2025-12-12-hexagonal-architecture-design.md`

---

## Task 5.1: Create Bedrock Adapter

**Files:**
- Create: `app/adapters/llm/bedrock.py`
- Create: `tests/unit/adapters/llm/__init__.py`
- Create: `tests/unit/adapters/llm/test_bedrock.py`

**Step 1: Create test directory**

```bash
mkdir -p tests/unit/adapters/llm
touch tests/unit/adapters/llm/__init__.py
```

**Step 2: Write the failing test**

```python
# tests/unit/adapters/llm/test_bedrock.py
"""Tests for Bedrock adapter."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.adapters.llm.bedrock import BedrockAdapter
from app.core.ports.llm import LLMPort, ModelConfig


class TestBedrockAdapter:
    def test_implements_llm_port(self):
        """Adapter must implement LLMPort interface."""
        with patch("app.adapters.llm.bedrock.LLMManager"):
            adapter = BedrockAdapter()
            assert isinstance(adapter, LLMPort)

    def test_get_model_config_haiku(self):
        """Should return ModelConfig for haiku model."""
        with patch("app.adapters.llm.bedrock.LLMManager"):
            adapter = BedrockAdapter()
            config = adapter.get_model_config("haiku")

            assert isinstance(config, ModelConfig)
            assert config.name == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
            assert config.role == "medical_data_extraction"
            assert config.max_tokens == 65536

    def test_get_model_config_sonnet(self):
        """Should return ModelConfig for sonnet model."""
        with patch("app.adapters.llm.bedrock.LLMManager"):
            adapter = BedrockAdapter()
            config = adapter.get_model_config("sonnet")

            assert isinstance(config, ModelConfig)
            assert "sonnet" in config.name.lower()

    def test_get_model_config_unknown_raises(self):
        """Should raise for unknown model."""
        from app.core.exceptions import LLMError

        with patch("app.adapters.llm.bedrock.LLMManager"):
            adapter = BedrockAdapter()
            with pytest.raises(LLMError, match="Unknown model"):
                adapter.get_model_config("gpt-4")


class TestBedrockAdapterGenerate:
    @pytest.mark.asyncio
    async def test_generate_delegates_to_manager(self):
        """Generate should delegate to LLMManager."""
        mock_manager = MagicMock()
        mock_manager.generate = AsyncMock(return_value="test response")

        with patch("app.adapters.llm.bedrock.LLMManager", return_value=mock_manager):
            adapter = BedrockAdapter()
            result = await adapter.generate("test prompt", "haiku")

            assert result == "test response"
            mock_manager.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_vision_delegates_to_manager(self):
        """Generate with vision should delegate to LLMManager."""
        mock_manager = MagicMock()
        mock_manager.generate_with_vision = AsyncMock(return_value="vision response")

        with patch("app.adapters.llm.bedrock.LLMManager", return_value=mock_manager):
            adapter = BedrockAdapter()
            result = await adapter.generate_with_vision(
                "describe image", [b"fake_png"], "haiku"
            )

            assert result == "vision response"
            mock_manager.generate_with_vision.assert_called_once()
```

**Step 3: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/adapters/llm/test_bedrock.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.adapters.llm.bedrock'"

**Step 4: Create the Bedrock adapter**

```python
# app/adapters/llm/bedrock.py
"""Bedrock LLM adapter.

Implements LLMPort interface by wrapping existing LLMManager.
"""
from typing import List, Optional

from app.core.ports.llm import LLMPort, ModelConfig
from app.core.exceptions import LLMError
from app.services.llm.llm_manager import LLMManager, LLMProvider


class BedrockAdapter(LLMPort):
    """AWS Bedrock implementation of LLMPort.

    Wraps existing LLMManager for backward compatibility.
    """

    # Model configurations from app/config/models.json
    _MODEL_CONFIGS = {
        "haiku": ModelConfig(
            name="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            role="medical_data_extraction",
            max_tokens=65536,
            temperature=0.1,
            timeout=120.0,
            context_window=200000,
            system_prompt="You are an expert medical record analyst.",
        ),
        "sonnet": ModelConfig(
            name="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            role="complex_reasoning",
            max_tokens=65536,
            temperature=0.1,
            timeout=180.0,
            context_window=200000,
            system_prompt="You are an expert medical record analyst.",
        ),
    }

    def __init__(self):
        """Initialize adapter with lazy-loaded LLMManager."""
        self._manager: Optional[LLMManager] = None

    @property
    def manager(self) -> LLMManager:
        """Lazy-initialize LLM manager."""
        if self._manager is None:
            self._manager = LLMManager()
        return self._manager

    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a model."""
        if model not in self._MODEL_CONFIGS:
            raise LLMError(f"Unknown model: {model}")
        return self._MODEL_CONFIGS[model]

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
                provider=LLMProvider.BEDROCK,
                model=config.name,
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
                provider=LLMProvider.BEDROCK,
                model=config.name,
                max_tokens=max_tokens or config.max_tokens,
                temperature=temperature or config.temperature,
                system=system or config.system_prompt,
            )
        except Exception as e:
            raise LLMError(f"Bedrock vision failed: {e}") from e
```

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/unit/adapters/llm/test_bedrock.py -v`
Expected: PASS (6 tests)

**Step 6: Update adapters/llm/__init__.py**

```python
# app/adapters/llm/__init__.py
"""LLM provider adapters."""
from app.adapters.llm.bedrock import BedrockAdapter

__all__ = ["BedrockAdapter"]
```

**Step 7: Commit**

```bash
git add app/adapters/llm/ tests/unit/adapters/llm/
git commit -m "feat(adapters): add BedrockAdapter implementing LLMPort"
```

---

## Task 5.2: Create PyMuPDF Adapter

**Files:**
- Create: `app/adapters/pdf/pymupdf_adapter.py`
- Create: `tests/unit/adapters/pdf/__init__.py`
- Create: `tests/unit/adapters/pdf/test_pymupdf_adapter.py`

**Step 1: Create test directory**

```bash
mkdir -p tests/unit/adapters/pdf
touch tests/unit/adapters/pdf/__init__.py
```

**Step 2: Write the failing test**

```python
# tests/unit/adapters/pdf/test_pymupdf_adapter.py
"""Tests for PyMuPDF adapter."""
import pytest
from unittest.mock import MagicMock, patch
from app.adapters.pdf.pymupdf_adapter import PyMuPDFAdapter
from app.core.ports.pdf import PDFPort, Bookmark


class TestPyMuPDFAdapter:
    def test_implements_pdf_port(self):
        """Adapter must implement PDFPort interface."""
        adapter = PyMuPDFAdapter()
        assert isinstance(adapter, PDFPort)


class TestPyMuPDFAdapterExtractText:
    def test_extract_text_single_page(self):
        """Should extract text from single page."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page 1 text"

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=10)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.extract_text("test.pdf", 1, 1)

            assert result == "Page 1 text"
            mock_doc.__getitem__.assert_called_with(0)  # 0-indexed

    def test_extract_text_page_range(self):
        """Should extract text from page range."""
        pages = ["Page 1", "Page 2", "Page 3"]
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=10)

        def get_page(idx):
            page = MagicMock()
            page.get_text.return_value = pages[idx]
            return page

        mock_doc.__getitem__ = get_page

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.extract_text("test.pdf", 1, 3)

            assert "Page 1" in result
            assert "Page 2" in result
            assert "Page 3" in result


class TestPyMuPDFAdapterBookmarks:
    def test_extract_bookmarks_returns_list(self):
        """Should return list of Bookmark objects."""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=100)
        mock_doc.get_toc.return_value = [
            [1, "Section A", 1],
            [2, "1F - Medical Records", 10],
            [2, "2F - Lab Results", 25],
        ]

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            bookmarks = adapter.extract_bookmarks("test.pdf")

            assert len(bookmarks) == 3
            assert all(isinstance(bm, Bookmark) for bm in bookmarks)
            assert bookmarks[0].title == "Section A"
            assert bookmarks[1].page_start == 10


class TestPyMuPDFAdapterRenderPage:
    def test_render_page_returns_png_bytes(self):
        """Should render page as PNG bytes."""
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"\x89PNG\r\n\x1a\n..."

        mock_page = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix

        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.render_page_image("test.pdf", 1)

            assert isinstance(result, bytes)
            assert result.startswith(b"\x89PNG")


class TestPyMuPDFAdapterIsScanned:
    def test_is_scanned_page_low_text(self):
        """Page with low text should be detected as scanned."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Case No. 123"  # Just header
        mock_page.get_images.return_value = [(0, 0, 2000, 2000)]  # Large image

        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.is_scanned_page("test.pdf", 1)

            assert result is True

    def test_is_scanned_page_high_text(self):
        """Page with substantial text should not be scanned."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 500  # Lots of text

        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.is_scanned_page("test.pdf", 1)

            assert result is False


class TestPyMuPDFAdapterPageCount:
    def test_get_page_count(self):
        """Should return page count."""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=42)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.get_page_count("test.pdf")

            assert result == 42
```

**Step 3: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/unit/adapters/pdf/test_pymupdf_adapter.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Create the PyMuPDF adapter**

```python
# app/adapters/pdf/pymupdf_adapter.py
"""PyMuPDF adapter.

Implements PDFPort interface using PyMuPDF (fitz).
Wraps existing preprocessing utilities.
"""
from typing import List

import fitz

from app.core.ports.pdf import PDFPort, Bookmark
from app.core.exceptions import PDFError


class PyMuPDFAdapter(PDFPort):
    """PyMuPDF implementation of PDFPort."""

    # Threshold for detecting scanned pages
    SCANNED_TEXT_THRESHOLD = 100
    LARGE_IMAGE_SIZE = 1000

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
            page_count = len(doc)
            doc.close()

            bookmarks = []
            for i, (level, title, page) in enumerate(toc):
                # Calculate end page from next bookmark or doc end
                if i + 1 < len(toc):
                    end_page = toc[i + 1][2] - 1
                else:
                    end_page = page_count

                bookmarks.append(Bookmark(
                    title=title,
                    page_start=page,
                    page_end=max(end_page, page),  # Ensure end >= start
                    level=level,
                ))
            return bookmarks
        except Exception as e:
            raise PDFError(f"Failed to extract bookmarks: {e}") from e

    def render_page_image(self, path: str, page: int, dpi: int = 150) -> bytes:
        """Render page as PNG image."""
        try:
            doc = fitz.open(path)
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = doc[page - 1].get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            doc.close()
            return img_bytes
        except Exception as e:
            raise PDFError(f"Failed to render page: {e}") from e

    def is_scanned_page(self, path: str, page: int) -> bool:
        """Check if page is scanned (minimal text + large image)."""
        try:
            doc = fitz.open(path)
            p = doc[page - 1]
            text = p.get_text() or ""
            text_len = len(text.strip())

            # Quick check: substantial text means not scanned
            if text_len > self.SCANNED_TEXT_THRESHOLD:
                doc.close()
                return False

            # Check for large images (scanned content)
            for img in p.get_images():
                width, height = img[2], img[3]
                if width > self.LARGE_IMAGE_SIZE and height > self.LARGE_IMAGE_SIZE:
                    doc.close()
                    return True

            doc.close()
            return False
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

Run: `PYTHONPATH=. pytest tests/unit/adapters/pdf/test_pymupdf_adapter.py -v`
Expected: PASS (8 tests)

**Step 6: Update adapters/pdf/__init__.py**

```python
# app/adapters/pdf/__init__.py
"""PDF processing adapters."""
from app.adapters.pdf.pymupdf_adapter import PyMuPDFAdapter

__all__ = ["PyMuPDFAdapter"]
```

**Step 7: Commit**

```bash
git add app/adapters/pdf/ tests/unit/adapters/pdf/
git commit -m "feat(adapters): add PyMuPDFAdapter implementing PDFPort"
```

---

## Task 5.3: Verify All Adapters

**Step 1: Run all adapter tests**

Run: `PYTHONPATH=. pytest tests/unit/adapters/ -v`
Expected: All 14 tests pass

**Step 2: Verify imports work**

```bash
PYTHONPATH=. python3 -c "
from app.adapters.llm import BedrockAdapter
from app.adapters.pdf import PyMuPDFAdapter
from app.core.ports import LLMPort, PDFPort

adapter = BedrockAdapter()
assert isinstance(adapter, LLMPort)

pdf = PyMuPDFAdapter()
assert isinstance(pdf, PDFPort)

print('All adapter imports OK')
"
```
Expected: `All adapter imports OK`

**Step 3: Run full test suite**

Run: `PYTHONPATH=. pytest tests/unit/ -v --tb=short`
Expected: All tests pass (20 core + 14 adapters = 34+ tests)

---

## Success Criteria

- [ ] BedrockAdapter implements LLMPort (6 tests)
- [ ] PyMuPDFAdapter implements PDFPort (8 tests)
- [ ] All adapter imports work
- [ ] Full test suite passes
- [ ] Adapters wrap existing services (no duplication)
