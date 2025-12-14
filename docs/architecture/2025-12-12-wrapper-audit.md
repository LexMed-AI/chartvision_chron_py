# Architecture Audit: Wrapper Anti-Patterns

**Date:** 2025-12-12
**Status:** Audit complete, plan revised

---

## Executive Summary

The codebase has **well-designed port interfaces** but suffers from **wrapper anti-patterns** that add unnecessary abstraction layers. The original Phase 5 plan would have made this worse by adding MORE wrappers.

### Key Finding

```
WRONG (what was planned):
  Core → LLMPort → BedrockAdapter → LLMManager → BedrockProvider → boto3
                        ↑                ↑
                   wrapper          wrapper (4 layers total!)

CORRECT (revised plan):
  Core → LLMPort → BedrockAdapter → boto3
                        ↑
                 direct implementation (2 layers)
```

---

## Audit Results by Layer

### 1. Services Layer (`app/services/`)

| File | External Dep | Layers | Severity | Issue |
|------|-------------|--------|----------|-------|
| `llm_manager.py` | boto3, httpx | **4** | CRITICAL | Manager wraps Provider wraps Client |
| `markdown_converter.py` | weasyprint, Gotenberg | **4-5** | SEVERE | Too many concerns, bad organization |
| `report_exporter.py` | Gotenberg, requests | 3 | MODERATE | Thin wrapper adds little value |
| `gotenberg_client.py` | requests | 2 | ✅ OK | Acceptable API client |
| `preprocessing.py` | fitz | 2 | ✅ GOOD | Adds domain logic on top of PyMuPDF |
| `bookmark_extractor.py` | fitz | 2 | ✅ EXCELLENT | Good abstraction |
| `citation_resolver.py` | None | 1 | ✅ EXCELLENT | Pure domain logic |
| `dde_parser.py` | fitz, LLMManager | 3-4 | MODERATE | Unnecessary LLM wrapping |

### 2. Adapters Layer (`app/adapters/`)

**CRITICAL: ALL EMPTY**

- `app/adapters/llm/__init__.py` - Empty
- `app/adapters/pdf/__init__.py` - Empty
- `app/adapters/storage/__init__.py` - Empty
- `app/adapters/export/__init__.py` - Empty

Ports exist but adapters were never implemented!

### 3. Domain Layer (`app/domain/`)

| Issue | File | Severity |
|-------|------|----------|
| Imports LLMManager directly | `chronology_engine.py:69-86` | CRITICAL |
| YAML file loading in domain | `text_extractor.py:24-31` | MODERATE |
| YAML file loading in domain | `vision_extractor.py:22-29` | MODERATE |
| Bedrock error types hardcoded | `retry_utils.py:18-27` | MODERATE |
| Model IDs in domain config | `llm_config.py` | LOW |

### 4. Ports Layer (`app/core/ports/`)

**✅ WELL-DESIGNED**

- `LLMPort` - Clean interface with `generate()`, `generate_with_vision()`
- `PDFPort` - Clean interface with `extract_text()`, `extract_bookmarks()`, etc.
- `JobStoragePort` - Clean async interface

---

## Anti-Pattern Details

### Anti-Pattern 1: LLMManager Abstraction Stack

```python
# 4 layers to make one API call:

LLMManager.generate()           # Layer 1: Manager (unnecessary)
    ↓
BaseLLMProvider                 # Layer 2: ABC (adds nothing)
    ↓
BedrockProvider.generate()      # Layer 3: Provider
    ↓
boto3.client.invoke_model()     # Layer 4: Actual call
```

**Fix:** BedrockAdapter calls boto3 directly. Delete middle layers.

### Anti-Pattern 2: Domain Imports Infrastructure

```python
# chronology_engine.py - WRONG
@property
def llm_manager(self):
    if self._llm_manager is None:
        from app.services.llm.llm_manager import LLMManager  # ← VIOLATION
        self._llm_manager = LLMManager()
```

**Fix:** Inject `LLMPort` via constructor:

```python
# CORRECT
class ChronologyEngine:
    def __init__(self, llm: LLMPort, pdf: PDFPort):
        self._llm = llm
        self._pdf = pdf
```

### Anti-Pattern 3: File I/O in Domain

```python
# text_extractor.py - WRONG
def _load_prompt_template() -> Dict[str, Any]:
    template_path = Path(__file__).parent / "prompts" / "text_extraction.yaml"
    with open(template_path, "r") as f:
        return yaml.safe_load(f)  # ← I/O in business logic
```

**Fix:** Create TemplatePort, implement FileTemplateAdapter.

---

## What's Good

1. **Port interfaces** - Well-designed, clear contracts
2. **PDF preprocessing** - Good domain logic on top of fitz
3. **BookmarkExtractor** - Excellent single-responsibility wrapper
4. **TextChunker** - Pure domain logic, no infrastructure
5. **ResponseParser** - Self-contained JSON recovery
6. **ParallelExtractor** - Good orchestration with dependency injection

---

## Priority Fixes

### High Priority (Phase 5 - revised)
1. ~~Create BedrockAdapter wrapping LLMManager~~ → Create BedrockAdapter using boto3 directly
2. ~~Create PyMuPDFAdapter wrapping preprocessing~~ → Create PyMuPDFAdapter using fitz directly

### Medium Priority (Phase 6)
3. Update ChronologyEngine to inject LLMPort, not import LLMManager
4. Move prompt YAML loading to adapter layer

### Low Priority (Phase 7+)
5. Create domain exception types for LLM errors
6. Move Bedrock error mapping to adapter
7. Simplify or remove LLMManager (adapter replaces it)

---

## Revised Phase 5 Plan

See: `docs/plans/2025-12-12-phase5-adapters-revised.md`

Key change: Adapters implement ports by **directly using external libraries**, not by wrapping existing service classes.
