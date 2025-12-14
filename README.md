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

## Architecture

```
ChronologyEngine (~300 lines)
├── TextExtractor     # LLM text extraction with chunking
├── VisionExtractor   # Vision extraction for scanned pages
├── ResponseParser    # JSON parsing with recovery
├── ParallelExtractor # Concurrent exhibit processing
├── RecoveryHandler   # Vision retry for sparse entries
└── RetryUtils        # Exponential backoff
```

## Test Results

- **126 chronology entries** from test PDF
- **168% parity** vs legacy engine
- **293s processing** (32% faster)
- **91 tests passing**

## API Endpoints

- `POST /api/v1/chartvision/process` - Process PDF
- `GET /api/v1/chartvision/reports/{job_id}` - Get results
- `GET /api/v1/ere/health` - Health check
