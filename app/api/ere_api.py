#!/usr/bin/env python3
"""
ERE-specific REST API for PDF Processing Pipeline
Refactored with modular components following Clean Architecture
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import redis
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from app.api.routes.ere import create_ere_router
from app.api.routes.chartvision import create_chartvision_router
from app.api.middleware.authentication import verify_token

# Local API modules - schemas imported by route modules
from app.api.schemas import ErrorResponse

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

        # ERE routes
        ere_router = create_ere_router(
            active_jobs=self.active_jobs,
            job_queue=self.job_queue,
            chronology_engine=self.chronology_engine,
            pdf_adapter=self.pdf_adapter,
            verify_token_func=verify_token,
            active_jobs_gauge=ACTIVE_JOBS
        )
        self.app.include_router(ere_router)

        # ChartVision routes
        chartvision_router = create_chartvision_router(
            active_jobs=self.active_jobs,
            job_queue=self.job_queue,
            chronology_engine=self.chronology_engine,
            pdf_adapter=self.pdf_adapter,
            verify_token_func=verify_token
        )
        self.app.include_router(chartvision_router)

        self._setup_error_handlers()

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
