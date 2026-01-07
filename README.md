# ChartVision Chronology Engine

Medical chronology extraction from SSA disability case files using Claude Haiku 4.5 vision.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start API server
PYTHONPATH=. python -m uvicorn app.api.ere_api:create_app --factory --host 0.0.0.0 --port 8811

# Start UI (separate terminal)
cd app/ui && python -m http.server 8812
```

## Features

### Page-Specific Citation Tracking

Every chronology entry includes precise source citations linking back to the original document:

- **ERE Format**: `10F@12 (p.1196)` - Exhibit 10F, page 12 of exhibit, absolute page 1196
- **Multi-page Ranges**: `5F@3-5 (pp.245-247)` - Spans multiple pages
- **Automatic Resolution**: Citations auto-resolve from exhibit metadata during extraction

Citations appear in both markdown and PDF exports, enabling quick verification of extracted data against source documents.

## Architecture

```
ChronologyEngine (~300 lines)
├── TextExtractor       # LLM text extraction with chunking
├── VisionExtractor     # Vision extraction for scanned pages
├── CitationMatcher     # Page-specific citation resolution
├── ResponseParser      # JSON parsing with recovery
├── ParallelExtractor   # Concurrent exhibit processing (5 workers)
├── RecoveryHandler     # Vision retry for sparse entries
└── RetryUtils          # Exponential backoff
```

### Citation Pipeline

```
PDF Extraction
      ↓
Exhibit Segmentation (bookmark-based)
      ↓
TextExtractor/VisionExtractor (preserves page context)
      ↓
CitationMatcher.match_entry() → Citation dataclass
      ↓
Entry with citation: {exhibit_id, relative_page, absolute_page}
      ↓
Export (Markdown/PDF) → "10F@12 (p.1196)"
```

## Test Results

- **140 chronology entries** from test PDF
- **250+ tests passing** (unit + integration)
- **~3 min processing** with parallel extraction
- **DDE extraction**: 100% confidence

## API Endpoints

- `POST /api/v1/ere/process` - Process PDF (returns job_id)
- `GET /api/v1/ere/status/{job_id}` - Job status
- `GET /api/v1/ere/results/{job_id}` - Get results (JSON)
- `GET /api/v1/ere/health` - Health check

## Export Formats

| Format | File | Citation Example |
|--------|------|------------------|
| Markdown | `{job_id}_report.md` | `10F@12 (p.1196)` |
| PDF | `{job_id}_report.pdf` | `10F@12 (p.1196)` |
| JSON | API response | `{"citation": {"exhibit_id": "10F", "relative_page": 12, "absolute_page": 1196}}` |

## Environment Variables

```bash
# AWS (required for Bedrock)
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
AWS_DEFAULT_REGION=us-east-1

# Optional
API_KEY=ere-api-key-2024  # Default API key for Bearer auth
```

## Dependencies

- **PDF Processing**: Gotenberg (Docker) for HTML→PDF conversion
- **LLM**: AWS Bedrock with Claude Haiku 4.5
- **Framework**: FastAPI + Uvicorn
