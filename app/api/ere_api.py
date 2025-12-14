#!/usr/bin/env python3
"""
ERE-specific REST API for PDF Processing Pipeline
Refactored with modular components following Clean Architecture
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiofiles
import redis
import uvicorn
from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form,
                     HTTPException, Request, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import Counter, Gauge, Histogram
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Core engine imports
from app.core.extraction import ChronologyEngine
from app.adapters.llm import BedrockAdapter
from app.adapters.pdf import PyMuPDFAdapter
from app.adapters.storage import RedisAdapter
from app.core.ports.storage import JobStoragePort

# Refactored API modules
from app.api.storage import JobStore
from app.api.routes.health import create_health_router
from app.api.middleware.authentication import verify_token

# Local API modules
from app.api.schemas import (
    EREProcessRequest,
    EREProcessResponse,
    EREStatusResponse,
    EREResultResponse,
    ErrorResponse,
)
from app.api.job_processors import process_ere_job, process_chartvision_job

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "ere_api_requests_total", "Total API requests", [
        "method", "endpoint", "status"])
REQUEST_DURATION = Histogram(
    "ere_api_request_duration_seconds",
    "Request duration")
ACTIVE_JOBS = Gauge("ere_active_jobs", "Number of active processing jobs")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Authentication
security = HTTPBearer()


async def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Dependency wrapper for verify_token that chains security and verification.

    This allows routes to use Depends(get_current_token) instead of manually
    chaining Depends(security) and verify_token.
    """
    return await verify_token(credentials)


class EREPipelineAPI:
    """ERE-specific API using core engine with dependency injection"""

    def __init__(
        self,
        pdf_adapter=None,
        llm_adapter=None,
        job_storage: Optional[JobStoragePort] = None,
        config_path: Optional[str] = None
    ):
        """Initialize API with dependency injection.

        Args:
            pdf_adapter: PDF processing adapter (default: PyMuPDFAdapter)
            llm_adapter: LLM adapter (default: BedrockAdapter)
            job_storage: Job storage implementation (default: RedisAdapter)
            config_path: Optional config file path
        """
        # Use dependency injection with sensible defaults
        self.pdf_adapter = pdf_adapter or PyMuPDFAdapter()
        llm = llm_adapter or BedrockAdapter()
        self.chronology_engine = ChronologyEngine(llm=llm)

        # Job storage
        if job_storage is None:
            _redis_client = redis.Redis(
                host="localhost", port=6379, db=0, decode_responses=False
            )
            job_storage = RedisAdapter(_redis_client)
            self.redis_client = _redis_client  # Backward compat
        else:
            self.redis_client = None

        self.job_storage = job_storage
        self.active_jobs = JobStore()
        self.job_queue = asyncio.Queue()

        # Start time for uptime
        self.start_time = time.time()

        # Create FastAPI app
        self.app = FastAPI(
            title="ERE PDF Processing API",
            description="Production API for processing ERE PDF documents",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # Setup
        self._setup_middleware()
        self._setup_routes()
        self.background_tasks = set()

    def _setup_middleware(self):
        """Setup API middleware"""
        # CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Rate limiting
        self.app.state.limiter = limiter
        self.app.add_exception_handler(
            RateLimitExceeded, _rate_limit_exceeded_handler)
        self.app.add_middleware(SlowAPIMiddleware)

        # Request logging middleware
        @self.app.middleware("http")
        async def log_requests(request, call_next):
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time

            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
            ).inc()

            REQUEST_DURATION.observe(process_time)

            logger.info(
                f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s"
            )

            return response

    def _setup_routes(self):
        """Setup API routes using extracted modules"""
        # Root endpoint
        @self.app.get("/")
        async def root():
            return {
                "service": "ERE PDF Processing API",
                "version": "1.0.0",
                "status": "operational",
                "docs": "/docs",
            }

        # Include health router
        health_router = create_health_router(
            start_time=self.start_time,
            active_jobs_getter=lambda: len(self.active_jobs),
            job_queue_getter=lambda: self.job_queue.qsize(),
        )
        self.app.include_router(health_router)

        # ERE and ChartVision routes
        self._setup_ere_routes()
        self._setup_chartvision_routes()
        self._setup_error_handlers()

    def _setup_ere_routes(self):
        """Setup ERE processing routes"""
        @self.app.post("/api/v1/ere/process", response_model=EREProcessResponse)
        @limiter.limit("10/minute")
        async def process_ere_document(
            request: Request,
            background_tasks: BackgroundTasks,
            file: UploadFile = File(...),
            document_type: Optional[str] = Form(None),
            priority: int = Form(1),
            sections: Optional[str] = Form(None),
            options: Optional[str] = Form("{}"),
            token: str = Depends(get_current_token),
        ):
            if file.content_type != "application/pdf":
                raise HTTPException(status_code=400, detail="Only PDF files are supported")

            job_id = str(uuid.uuid4())

            try:
                upload_dir = Path("/tmp/ere_uploads")
                upload_dir.mkdir(exist_ok=True)
                file_path = upload_dir / f"{job_id}_{file.filename}"

                async with aiofiles.open(file_path, "wb") as f:
                    content = await file.read()
                    await f.write(content)

                processing_options = json.loads(options) if options else {}
                sections_list = sections.split(",") if sections else None

                job_data = {
                    "job_id": job_id,
                    "file_path": str(file_path),
                    "filename": file.filename,
                    "document_type": document_type,
                    "priority": priority,
                    "sections": sections_list,
                    "options": processing_options,
                    "created_at": datetime.now(),
                    "status": "queued",
                }

                self.active_jobs[job_id] = job_data
                ACTIVE_JOBS.set(len(self.active_jobs))

                background_tasks.add_task(
                    process_ere_job, job_id, self.active_jobs, self.chronology_engine
                )

                return EREProcessResponse(
                    job_id=job_id,
                    status="queued",
                    message="Document processing started",
                    estimated_completion=datetime.now() + timedelta(seconds=85),
                )

            except Exception as e:
                logger.error(f"Error processing document: {str(e)}")
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]
                    ACTIVE_JOBS.set(len(self.active_jobs))
                raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

        @self.app.get("/api/v1/ere/status/{job_id}", response_model=EREStatusResponse)
        @limiter.limit("60/minute")
        async def get_job_status(
            request: Request, job_id: str, token: str = Depends(get_current_token)
        ):
            if job_id not in self.active_jobs:
                raise HTTPException(status_code=404, detail="Job not found")

            job_data = self.active_jobs[job_id]
            estimated_remaining = None
            if job_data["status"] == "processing":
                elapsed = (datetime.now() - job_data.get("started_at", datetime.now())).total_seconds()
                estimated_remaining = int(max(0, 85 - elapsed))

            return EREStatusResponse(
                job_id=job_id,
                status=job_data["status"],
                progress=job_data.get("progress", 0),
                current_step=job_data.get("current_step"),
                steps_completed=job_data.get("steps_completed", []),
                estimated_remaining=estimated_remaining,
                created_at=job_data["created_at"],
                started_at=job_data.get("started_at"),
                completed_at=job_data.get("completed_at"),
                error=job_data.get("error"),
            )

        @self.app.get("/api/v1/ere/results/{job_id}", response_model=EREResultResponse)
        @limiter.limit("30/minute")
        async def get_job_results(
            request: Request, job_id: str, token: str = Depends(get_current_token)
        ):
            if job_id not in self.active_jobs:
                raise HTTPException(status_code=404, detail="Job not found")

            job_data = self.active_jobs[job_id]
            if job_data["status"] != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Job not completed. Current status: {job_data['status']}",
                )

            processing_time = None
            if job_data.get("started_at") and job_data.get("completed_at"):
                processing_time = (job_data["completed_at"] - job_data["started_at"]).total_seconds()

            return EREResultResponse(
                job_id=job_id,
                status=job_data["status"],
                processing_time=processing_time,
                results=job_data.get("results"),
                metadata=job_data.get("metadata"),
                error=job_data.get("error"),
            )

        @self.app.delete("/api/v1/ere/jobs/{job_id}")
        @limiter.limit("10/minute")
        async def cancel_job(request: Request, job_id: str, token: str = Depends(get_current_token)):
            if job_id not in self.active_jobs:
                raise HTTPException(status_code=404, detail="Job not found")

            job_data = self.active_jobs[job_id]
            if job_data["status"] in ["completed", "failed", "cancelled"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel job with status: {job_data['status']}",
                )

            job_data["status"] = "cancelled"
            job_data["completed_at"] = datetime.now()
            return {"message": "Job cancelled successfully"}

        @self.app.get("/api/v1/ere/jobs")
        @limiter.limit("20/minute")
        async def list_jobs(
            request: Request,
            status: Optional[str] = None,
            limit: int = 50,
            token: str = Depends(get_current_token),
        ):
            jobs = []
            for job_id, job_data in self.active_jobs.items():
                if status and job_data.get("status") != status:
                    continue

                jobs.append({
                    "job_id": job_id,
                    "filename": job_data.get("filename", "unknown"),
                    "status": job_data.get("status", "unknown"),
                    "created_at": job_data.get("created_at"),
                    "document_type": job_data.get("document_type"),
                    "priority": job_data.get("priority", 1),
                })

                if len(jobs) >= limit:
                    break

            return {"jobs": jobs, "total": len(self.active_jobs)}

    def _setup_chartvision_routes(self):
        """Setup ChartVision processing routes"""
        @self.app.post("/api/v1/chartvision/process")
        @limiter.limit("10/minute")
        async def process_chartvision(
            request: Request,
            background_tasks: BackgroundTasks,
            file: UploadFile = File(...),
            priority: int = Form(1),
            options: Optional[str] = Form("{}"),
            token: str = Depends(get_current_token),
        ):
            if not file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Only PDF files are accepted")

            content_type = file.content_type or ""
            if "pdf" not in content_type.lower() and not file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Only PDF files are accepted")

            job_id = str(uuid.uuid4())

            upload_dir = Path("/tmp/chartvision_uploads")
            upload_dir.mkdir(exist_ok=True)
            file_path = upload_dir / f"{job_id}_{file.filename}"

            content = await file.read()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)

            try:
                opts = json.loads(options) if options else {}
            except json.JSONDecodeError:
                opts = {}

            self.active_jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "type": "chartvision",
                "file_path": str(file_path),
                "filename": file.filename,
                "priority": priority,
                "options": opts,
                "created_at": datetime.now(),
                "progress": 0.0,
                "current_step": "Queued for processing",
            }

            background_tasks.add_task(process_chartvision_job, job_id, self.active_jobs)

            return {
                "job_id": job_id,
                "status": "queued",
                "message": "ChartVision processing started",
                "report_url": f"/api/v1/chartvision/reports/{job_id}",
                "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat(),
            }

        @self.app.get("/api/v1/chartvision/reports/{job_id}")
        @limiter.limit("30/minute")
        async def get_chartvision_report(
            request: Request,
            job_id: str,
            token: str = Depends(get_current_token),
        ):
            if job_id not in self.active_jobs:
                raise HTTPException(status_code=404, detail="Job not found")

            job = self.active_jobs[job_id]
            if job.get("type") != "chartvision":
                raise HTTPException(status_code=404, detail="Job not found")

            if job["status"] != "completed":
                return {
                    "job_id": job_id,
                    "status": job["status"],
                    "progress": job.get("progress", 0),
                    "current_step": job.get("current_step"),
                }

            result = job.get("result", {"error": "No result available"})
            return {
                "status": "completed",
                "job_id": job_id,
                **result,
            }

        @self.app.get("/api/v1/chartvision/reports/{job_id}/pdf")
        @limiter.limit("10/minute")
        async def get_chartvision_pdf(
            request: Request,
            job_id: str,
            token: str = Depends(get_current_token),
        ):
            from fastapi.responses import FileResponse

            if job_id not in self.active_jobs:
                raise HTTPException(status_code=404, detail="Job not found")

            job = self.active_jobs[job_id]
            if job.get("type") != "chartvision":
                raise HTTPException(status_code=404, detail="Job not found")

            if job["status"] != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Job not completed. Status: {job['status']}"
                )

            pdf_path = job.get("pdf_path")
            if pdf_path and Path(pdf_path).exists():
                return FileResponse(
                    path=pdf_path,
                    media_type="application/pdf",
                    filename=f"chartvision_report_{job_id[:8]}.pdf",
                )

            raise HTTPException(
                status_code=501,
                detail="PDF not available. Enable pdf_output in job options."
            )

        @self.app.get("/api/v1/ere/pdf/{job_id}")
        @limiter.limit("10/minute")
        async def get_ere_pdf(
            request: Request,
            job_id: str,
            token: str = Depends(get_current_token),
        ):
            """Download PDF report for ERE job (generated via Gotenberg)."""
            from fastapi.responses import FileResponse
            import json

            # Load job from persisted JSON file
            project_root = Path(__file__).parent.parent.parent
            job_file = project_root / "results" / f"job_{job_id}.json"

            if not job_file.exists():
                raise HTTPException(status_code=404, detail="Job not found")

            with open(job_file) as f:
                job = json.load(f)

            if job.get("status") != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Job not completed. Status: {job.get('status')}"
                )

            # Check results for pdf_path
            results = job.get("results", {})
            pdf_path = results.get("pdf_path")

            if pdf_path:
                # Handle both relative and absolute paths
                pdf_file = Path(pdf_path)
                if not pdf_file.is_absolute():
                    # Relative paths are relative to project root
                    pdf_file = project_root / pdf_path

                if pdf_file.exists():
                    return FileResponse(
                        path=str(pdf_file),
                        media_type="application/pdf",
                        filename=f"chronology_{job_id[:8]}.pdf",
                    )

            raise HTTPException(
                status_code=501,
                detail="PDF not available. Gotenberg may not be running."
            )

    def _setup_error_handlers(self):
        """Setup error handlers"""
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request, exc):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        @self.app.exception_handler(Exception)
        async def global_exception_handler(request, exc):
            logger.error(f"Unhandled exception: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred",
                    "details": {"exception": str(exc)},
                    "timestamp": datetime.now().isoformat(),
                },
            )

    async def start(self):
        """Start the API server"""
        logger.info("Starting ERE Pipeline API...")
        self.background_tasks.add(asyncio.create_task(self._cleanup_old_jobs()))
        logger.info("ERE Pipeline API started successfully")

    async def stop(self):
        """Stop the API server"""
        logger.info("Stopping ERE Pipeline API...")
        for task in self.background_tasks:
            task.cancel()
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        logger.info("ERE Pipeline API stopped")

    async def _cleanup_old_jobs(self):
        """Background task to cleanup old jobs"""
        while True:
            try:
                cutoff_time = datetime.now() - timedelta(hours=24)
                jobs_to_remove = [
                    job_id for job_id, job_data in self.active_jobs.items()
                    if job_data["status"] in ["completed", "failed", "cancelled"]
                    and job_data.get("completed_at", datetime.now()) < cutoff_time
                ]

                for job_id in jobs_to_remove:
                    del self.active_jobs[job_id]
                    logger.info(f"Cleaned up old job: {job_id}")

                ACTIVE_JOBS.set(len(self.active_jobs))
                await asyncio.sleep(3600)

            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
                await asyncio.sleep(3600)


# FastAPI app factory
def create_app(config_path: Optional[str] = None) -> FastAPI:
    """Create FastAPI application"""
    api = EREPipelineAPI(config_path)
    return api.app


def create_ere_api(config_path: Optional[str] = None) -> EREPipelineAPI:
    """Create ERE API instance for testing."""
    return EREPipelineAPI(config_path)


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ERE PDF Processing API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()
    app = create_app(args.config)
    uvicorn.run(app, host=args.host, port=args.port, workers=args.workers, reload=args.reload)
