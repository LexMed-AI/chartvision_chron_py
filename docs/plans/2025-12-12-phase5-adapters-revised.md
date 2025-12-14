# Phase 5: Adapters Implementation (REVISED)

> **For Claude:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create adapters that implement port interfaces by directly using external libraries (boto3, fitz). NO wrapping of existing service classes.

**Key Change from Original Plan:** Adapters talk directly to external libs, not wrap existing services.

---

## Architecture Principle

```
WRONG (wrapper on wrapper):
  Core → Port → Adapter → Service → Provider → External Lib

CORRECT (direct implementation):
  Core → Port → Adapter → External Lib
```

---

## Task 5.1: Create BedrockAdapter (Direct Implementation)

**Goal:** Implement LLMPort using boto3 directly. Extract working code from `BedrockProvider` class in `llm_manager.py`.

**Files:**
- Create: `app/adapters/llm/bedrock.py`
- Create: `tests/unit/adapters/llm/__init__.py`
- Create: `tests/unit/adapters/llm/test_bedrock.py`

### Step 1: Create test directory

```bash
mkdir -p tests/unit/adapters/llm
touch tests/unit/adapters/llm/__init__.py
```

### Step 2: Write the failing test

```python
# tests/unit/adapters/llm/test_bedrock.py
"""Tests for Bedrock adapter - direct boto3 implementation."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.adapters.llm.bedrock import BedrockAdapter
from app.core.ports.llm import LLMPort, ModelConfig


class TestBedrockAdapterInterface:
    def test_implements_llm_port(self):
        """Adapter must implement LLMPort interface."""
        with patch("boto3.Session"):
            adapter = BedrockAdapter()
            assert isinstance(adapter, LLMPort)

    def test_get_model_config_haiku(self):
        """Should return ModelConfig for haiku model."""
        with patch("boto3.Session"):
            adapter = BedrockAdapter()
            config = adapter.get_model_config("haiku")

            assert isinstance(config, ModelConfig)
            assert "haiku" in config.name.lower()
            assert config.max_tokens == 65536

    def test_get_model_config_sonnet(self):
        """Should return ModelConfig for sonnet model."""
        with patch("boto3.Session"):
            adapter = BedrockAdapter()
            config = adapter.get_model_config("sonnet")

            assert isinstance(config, ModelConfig)
            assert "sonnet" in config.name.lower()

    def test_get_model_config_unknown_raises(self):
        """Should raise for unknown model."""
        from app.core.exceptions import LLMError

        with patch("boto3.Session"):
            adapter = BedrockAdapter()
            with pytest.raises(LLMError, match="Unknown model"):
                adapter.get_model_config("gpt-4")


class TestBedrockAdapterGenerate:
    @pytest.mark.asyncio
    async def test_generate_calls_bedrock(self):
        """Generate should call Bedrock invoke_model directly."""
        mock_response = {
            "body": MagicMock(
                read=MagicMock(return_value=b'{"content": [{"text": "response"}], "usage": {"input_tokens": 10, "output_tokens": 5}}')
            )
        }

        mock_client = MagicMock()
        mock_client.invoke_model = MagicMock(return_value=mock_response)

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("boto3.Session", return_value=mock_session):
            adapter = BedrockAdapter()
            result = await adapter.generate("test prompt", "haiku")

            assert result == "response"
            mock_client.invoke_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_vision_includes_images(self):
        """Generate with vision should include base64 images in request."""
        mock_response = {
            "body": MagicMock(
                read=MagicMock(return_value=b'{"content": [{"text": "vision response"}], "usage": {"input_tokens": 100, "output_tokens": 20}}')
            )
        }

        mock_client = MagicMock()
        mock_client.invoke_model = MagicMock(return_value=mock_response)

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("boto3.Session", return_value=mock_session):
            adapter = BedrockAdapter()
            result = await adapter.generate_with_vision(
                "describe image", [b"\x89PNG\r\n\x1a\n..."], "haiku"
            )

            assert result == "vision response"
            # Verify invoke_model was called with image content
            call_args = mock_client.invoke_model.call_args
            assert call_args is not None
```

### Step 3: Run test to verify it fails

```bash
PYTHONPATH=. pytest tests/unit/adapters/llm/test_bedrock.py -v
```

Expected: FAIL with "ModuleNotFoundError"

### Step 4: Create the Bedrock adapter (DIRECT implementation)

Extract and adapt code from `BedrockProvider` in `llm_manager.py` (lines 417-656).

```python
# app/adapters/llm/bedrock.py
"""Bedrock LLM adapter.

Implements LLMPort interface by directly using boto3.
This is NOT a wrapper around LLMManager - it talks to AWS directly.
"""
import asyncio
import base64
import json
import logging
from typing import List, Optional

import boto3

from app.core.ports.llm import LLMPort, ModelConfig
from app.core.exceptions import LLMError

logger = logging.getLogger(__name__)


class BedrockAdapter(LLMPort):
    """AWS Bedrock implementation of LLMPort.

    Directly uses boto3 bedrock-runtime client.
    Code extracted from BedrockProvider in llm_manager.py.
    """

    # Model configurations
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

    def __init__(self, region: str = "us-east-1"):
        """Initialize adapter with boto3 client.

        Args:
            region: AWS region for Bedrock service
        """
        session = boto3.Session()
        self._client = session.client("bedrock-runtime", region_name=region)

    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a model."""
        if model not in self._MODEL_CONFIGS:
            raise LLMError(f"Unknown model: {model}. Available: {list(self._MODEL_CONFIGS.keys())}")
        return self._MODEL_CONFIGS[model]

    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate text completion via Bedrock.

        Directly calls boto3 invoke_model.
        """
        config = self.get_model_config(model)

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": temperature or config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system or config.system_prompt:
            request_body["system"] = system or config.system_prompt

        try:
            # Bedrock is sync, run in executor for async compatibility
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.invoke_model(
                    modelId=config.name,
                    body=json.dumps(request_body)
                ),
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except Exception as e:
            logger.error(f"Bedrock generate failed: {e}")
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
        """Generate completion from text and images via Bedrock.

        Directly calls boto3 invoke_model with image content.
        """
        config = self.get_model_config(model)

        # Build content with images + text
        content = []
        for img_bytes in images:
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_base64
                }
            })
        content.append({"type": "text", "text": prompt})

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": temperature or config.temperature,
            "messages": [{"role": "user", "content": content}],
        }

        if system or config.system_prompt:
            request_body["system"] = system or config.system_prompt

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.invoke_model(
                    modelId=config.name,
                    body=json.dumps(request_body)
                ),
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except Exception as e:
            logger.error(f"Bedrock vision failed: {e}")
            raise LLMError(f"Bedrock vision failed: {e}") from e
```

### Step 5: Run test to verify it passes

```bash
PYTHONPATH=. pytest tests/unit/adapters/llm/test_bedrock.py -v
```

Expected: PASS (6 tests)

### Step 6: Update adapters/llm/__init__.py

```python
# app/adapters/llm/__init__.py
"""LLM provider adapters."""
from app.adapters.llm.bedrock import BedrockAdapter

__all__ = ["BedrockAdapter"]
```

---

## Task 5.2: Create PyMuPDFAdapter (Direct Implementation)

**Goal:** Implement PDFPort using fitz (PyMuPDF) directly. Extract working code from `preprocessing.py`.

**Files:**
- Create: `app/adapters/pdf/pymupdf.py`
- Create: `tests/unit/adapters/pdf/__init__.py`
- Create: `tests/unit/adapters/pdf/test_pymupdf.py`

### Step 1: Create test directory

```bash
mkdir -p tests/unit/adapters/pdf
touch tests/unit/adapters/pdf/__init__.py
```

### Step 2: Write the failing test

```python
# tests/unit/adapters/pdf/test_pymupdf.py
"""Tests for PyMuPDF adapter - direct fitz implementation."""
import pytest
from unittest.mock import MagicMock, patch
from app.adapters.pdf.pymupdf import PyMuPDFAdapter
from app.core.ports.pdf import PDFPort, Bookmark


class TestPyMuPDFAdapterInterface:
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
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.extract_text("test.pdf", 1, 1)

            assert result == "Page 1 text"

    def test_extract_text_page_range(self):
        """Should extract text from page range."""
        pages = ["Page 1", "Page 2", "Page 3"]

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=10)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

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
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
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
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.render_page_image("test.pdf", 1)

            assert isinstance(result, bytes)
            assert result.startswith(b"\x89PNG")


class TestPyMuPDFAdapterIsScanned:
    def test_is_scanned_page_low_text(self):
        """Page with low text and large image should be detected as scanned."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Case No. 123"  # Just header
        mock_page.get_images.return_value = [(0, 0, 2000, 2000, 0, 0, 0)]  # Large image

        mock_doc = MagicMock()
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

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
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.is_scanned_page("test.pdf", 1)

            assert result is False


class TestPyMuPDFAdapterPageCount:
    def test_get_page_count(self):
        """Should return page count."""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=42)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("fitz.open", return_value=mock_doc):
            adapter = PyMuPDFAdapter()
            result = adapter.get_page_count("test.pdf")

            assert result == 42
```

### Step 3: Run test to verify it fails

```bash
PYTHONPATH=. pytest tests/unit/adapters/pdf/test_pymupdf.py -v
```

Expected: FAIL with "ModuleNotFoundError"

### Step 4: Create the PyMuPDF adapter (DIRECT implementation)

```python
# app/adapters/pdf/pymupdf.py
"""PyMuPDF adapter.

Implements PDFPort interface by directly using fitz (PyMuPDF).
This is NOT a wrapper around preprocessing.py - it uses fitz directly.
"""
import logging
from typing import List

import fitz

from app.core.ports.pdf import PDFPort, Bookmark
from app.core.exceptions import PDFError

logger = logging.getLogger(__name__)


class PyMuPDFAdapter(PDFPort):
    """PyMuPDF implementation of PDFPort.

    Directly uses fitz library for PDF operations.
    """

    # Thresholds for scanned page detection
    SCANNED_TEXT_THRESHOLD = 100  # Characters
    LARGE_IMAGE_SIZE = 1000  # Pixels

    def extract_text(self, path: str, start_page: int, end_page: int) -> str:
        """Extract text from page range.

        Args:
            path: Path to PDF file
            start_page: Starting page (1-indexed)
            end_page: Ending page (inclusive)

        Returns:
            Extracted text from all pages joined with newlines
        """
        try:
            with fitz.open(path) as doc:
                parts = []
                # Convert to 0-indexed
                for i in range(start_page - 1, min(end_page, len(doc))):
                    text = doc[i].get_text() or ""
                    parts.append(text)
                return "\n".join(parts)
        except Exception as e:
            raise PDFError(f"Failed to extract text from {path}: {e}") from e

    def extract_bookmarks(self, path: str) -> List[Bookmark]:
        """Extract bookmarks from PDF.

        Args:
            path: Path to PDF file

        Returns:
            List of Bookmark objects with title, pages, and level
        """
        try:
            with fitz.open(path) as doc:
                toc = doc.get_toc()
                page_count = len(doc)

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
            raise PDFError(f"Failed to extract bookmarks from {path}: {e}") from e

    def render_page_image(self, path: str, page: int, dpi: int = 150) -> bytes:
        """Render page as PNG image.

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)
            dpi: Resolution for rendering

        Returns:
            PNG image bytes
        """
        try:
            with fitz.open(path) as doc:
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = doc[page - 1].get_pixmap(matrix=mat)
                return pix.tobytes("png")
        except Exception as e:
            raise PDFError(f"Failed to render page {page} from {path}: {e}") from e

    def is_scanned_page(self, path: str, page: int) -> bool:
        """Check if page is scanned (minimal text + large image).

        Args:
            path: Path to PDF file
            page: Page number (1-indexed)

        Returns:
            True if page appears to be a scanned image
        """
        try:
            with fitz.open(path) as doc:
                p = doc[page - 1]
                text = p.get_text() or ""
                text_len = len(text.strip())

                # Quick check: substantial text means not scanned
                if text_len > self.SCANNED_TEXT_THRESHOLD:
                    return False

                # Check for large images (scanned content)
                for img in p.get_images():
                    # img tuple: (xref, smask, width, height, bpc, colorspace, alt_colorspace)
                    width, height = img[2], img[3]
                    if width > self.LARGE_IMAGE_SIZE and height > self.LARGE_IMAGE_SIZE:
                        return True

                return False
        except Exception as e:
            raise PDFError(f"Failed to check page {page} from {path}: {e}") from e

    def get_page_count(self, path: str) -> int:
        """Get total page count.

        Args:
            path: Path to PDF file

        Returns:
            Number of pages in the PDF
        """
        try:
            with fitz.open(path) as doc:
                return len(doc)
        except Exception as e:
            raise PDFError(f"Failed to get page count from {path}: {e}") from e
```

### Step 5: Run test to verify it passes

```bash
PYTHONPATH=. pytest tests/unit/adapters/pdf/test_pymupdf.py -v
```

Expected: PASS (8 tests)

### Step 6: Update adapters/pdf/__init__.py

```python
# app/adapters/pdf/__init__.py
"""PDF processing adapters."""
from app.adapters.pdf.pymupdf import PyMuPDFAdapter

__all__ = ["PyMuPDFAdapter"]
```

---

## Task 5.3: Verify All Adapters

### Step 1: Run all adapter tests

```bash
PYTHONPATH=. pytest tests/unit/adapters/ -v
```

Expected: All 14 tests pass

### Step 2: Verify imports work

```bash
PYTHONPATH=. python3 -c "
from app.adapters.llm import BedrockAdapter
from app.adapters.pdf import PyMuPDFAdapter
from app.core.ports import LLMPort, PDFPort

# Verify interface implementation
adapter = BedrockAdapter()
assert isinstance(adapter, LLMPort)
print('✓ BedrockAdapter implements LLMPort')

pdf = PyMuPDFAdapter()
assert isinstance(pdf, PDFPort)
print('✓ PyMuPDFAdapter implements PDFPort')

print('All adapter imports OK')
"
```

### Step 3: Run full test suite

```bash
PYTHONPATH=. pytest tests/unit/ -v --tb=short
```

Expected: All tests pass (20 core + 14 adapters = 34+ tests)

---

## Success Criteria

- [ ] BedrockAdapter implements LLMPort using boto3 directly (6 tests)
- [ ] PyMuPDFAdapter implements PDFPort using fitz directly (8 tests)
- [ ] All adapter imports work
- [ ] Full test suite passes
- [ ] **NO wrappers around existing services** - adapters use external libs directly

---

## Future Work (Phase 6+)

After Phase 5 completes, these tasks remain:

1. **Update domain to inject ports** - Remove direct LLMManager imports from ChronologyEngine
2. **Deprecate LLMManager** - The adapter replaces its functionality
3. **Move prompt loading to adapter** - Extract YAML loading from extractors
4. **Move Bedrock error types to adapter** - Domain should use domain exceptions
