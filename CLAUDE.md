# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

ChartVision Chronology Engine - Medical chronology extraction from SSA disability case files using Claude Haiku 4.5 vision on AWS Bedrock.

## Modularization Rules

### File Size Limits
- **Target**: 100-300 lines per file
- **Maximum**: 350 lines (hard limit)
- **Split signals**: Multiple classes, large imports, scrolling to find things

### Clean Architecture Principles

**1. Dependency Rule - Inward Only**
```
Adapters → Core → Ports
   ↓         ↓       ↓
External   Domain   Interfaces
```
- Core **never** imports from adapters or services
- Adapters implement port interfaces
- Dependencies point toward the center (domain)

**2. Single Responsibility**
- One reason to change per file
- Test: "If X changes, does this file need to change?" Multiple X's → split

**3. Domain vs Infrastructure**
| Domain (core/) | Infrastructure (adapters/) |
|----------------|---------------------------|
| Business rules, validation | External system integration |
| `is_content_sparse()` | `is_scanned_page()` |
| Entry models, constants | HTTP clients, file I/O |

**Test**: "Would this exist if we changed our PDF library?"
- No → Domain (core/)
- Yes → Infrastructure (adapters/)

**4. Naming = Intent**
```
❌ utils.py, helpers.py, misc.py, common.py
✅ rate_limiter.py, content_analyzer.py, court_patterns.py
```

**5. The 7±2 Rule**
- A module should have 5-9 public functions/classes
- More than that → split into focused modules

**6. High Cohesion**
- Functions that change together live together
- If you often edit files A and B together → same module

### Quick Decision Framework
```
1. Does this belong with existing code? (cohesion)
2. Is this domain or infrastructure?
3. Will this file exceed 300 lines?
4. Can I name it specifically?
```

## Key Commands

### Start API Server
```bash
PYTHONPATH=. python -m uvicorn app.api.ere_api:create_app --factory --host 0.0.0.0 --port 8811
```

### Start UI (separate terminal)
```bash
cd app/ui && python -m http.server 8812
```

### Run Tests
```bash
PYTHONPATH=. pytest tests/ -v
```

## Architecture (Hexagonal / Ports & Adapters)

```
app/
├── api/                    # HTTP Layer (FastAPI)
├── core/                   # Domain Logic (NO external deps)
│   ├── ports/              # Abstract interfaces (LLMPort, PDFPort, StoragePort)
│   ├── models/             # Domain models (Entry, ChartVision)
│   ├── extraction/         # Extraction engine + components
│   └── builders/           # Report builders
├── adapters/               # External Integrations
│   ├── llm/bedrock.py      # AWS Bedrock (implements LLMPort)
│   ├── pdf/pymupdf.py      # PyMuPDF (implements PDFPort)
│   └── storage/redis.py    # Redis (implements StoragePort)
├── config/                 # YAML prompts + settings
└── workers/                # Background job handlers
```

## Key Files

### Ports (Interfaces)
- `app/core/ports/llm.py` - LLM abstraction (generate, vision)
- `app/core/ports/pdf.py` - PDF operations (text, bookmarks, render)
- `app/core/ports/storage.py` - Job persistence

### Core Extraction
- `app/core/extraction/engine.py` - ChronologyEngine orchestrator (~300 lines)
- `app/core/extraction/text_extractor.py` - LLM text extraction with chunking
- `app/core/extraction/vision_extractor.py` - Vision extraction for scanned pages
- `app/core/extraction/parallel_extractor.py` - Concurrent exhibit processing (5 workers)
- `app/core/extraction/recovery_handler.py` - Vision retry for sparse entries
- `app/core/extraction/response_parser.py` - JSON parsing with truncation recovery
- `app/core/extraction/text_chunker.py` - Paragraph-aware text splitting

### Core Builders
- `app/core/builders/chartvision_builder.py` - Report data assembly
- `app/core/builders/report_generator.py` - Markdown report generation
- `app/core/builders/occurrence_formatter.py` - Clinical event formatting

### Adapters
- `app/adapters/llm/bedrock.py` - AWS Bedrock integration (Haiku 4.5)
- `app/adapters/pdf/pymupdf.py` - PyMuPDF bookmark/text extraction
- `app/adapters/storage/redis_adapter.py` - Redis job storage

### API Layer
- `app/api/ere_api.py` - FastAPI endpoints (`/api/v1/chartvision/process`, `/api/v1/ere/health`)
- `app/api/job_processors.py` - Background job processing
- `app/api/schemas.py` - Pydantic request/response models

### Configuration
- `app/config/prompts/extraction/text_extraction.yaml` - Text extraction prompts
- `app/config/prompts/extraction/vision_extraction.yaml` - Vision extraction prompts
- `app/config/models.json` - Model settings and pipeline config

## Environment Variables

```bash
# AWS (required for Bedrock)
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_DEFAULT_REGION=us-east-1

# Optional
API_KEY=ere-api-key-2024  # Default API key
```

## Processing Flow

1. **Upload** → PDF received via `/api/v1/chartvision/process`
2. **Bookmark Extraction** → PyMuPDF extracts exhibit bookmarks (A-F sections)
3. **F-Section Filtering** → Identifies medical exhibits (1F, 2F, etc.)
4. **Parallel Extraction** → Processes exhibits concurrently (5 workers)
   - Text exhibits → TextExtractor with chunking
   - Scanned exhibits → VisionExtractor
5. **Recovery** → RecoveryHandler retries sparse entries with vision
6. **Report Building** → ChartVisionBuilder generates chronology
7. **Output** → JSON/Markdown report

## Test Summary

- **229 tests passing**
- Coverage: core/extraction/*, core/builders/*, core/ports/*, adapters/llm/*, adapters/pdf/*, adapters/storage/*

## Performance

- **126 chronology entries** from test PDF (Tull)
- **168% parity** vs legacy engine
- **293s processing** (32% faster than legacy)
- **40K char chunking** prevents Bedrock timeouts
