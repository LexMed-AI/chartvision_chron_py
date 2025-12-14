"""Health check and monitoring routes"""
import time
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import Response
from prometheus_client import generate_latest

from app.api.schemas import HealthResponse


def create_health_router(
    start_time: float,
    active_jobs_getter=None,
    job_queue_getter=None,
) -> APIRouter:
    """Create health check router.

    Args:
        start_time: Server start time for uptime calculation
        active_jobs_getter: Callable that returns active jobs count
        job_queue_getter: Callable that returns job queue size

    Returns:
        FastAPI router with health endpoints
    """
    router = APIRouter()

    @router.get("/api/v1/ere/health", response_model=HealthResponse)
    async def health_check(request: Request):
        """Health check endpoint"""
        active_count = active_jobs_getter() if active_jobs_getter else 0
        queue_size = job_queue_getter() if job_queue_getter else 0

        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(),
            version="1.0.0",
            uptime=time.time() - start_time,
            system_info={
                "active_jobs": active_count,
                "queue_size": queue_size,
                "memory_usage": 0,
                "cpu_usage": 0,
            },
            pipeline_status={
                "components": 3,
                "status": "running",
            },
        )

    @router.get("/metrics")
    async def get_metrics():
        """Prometheus metrics endpoint"""
        return Response(generate_latest(), media_type="text/plain")

    @router.get("/api/v1/ere/supported-types")
    async def get_supported_types():
        """Get supported document types"""
        return {
            "document_types": [
                {"type": "DDE", "description": "Detailed Earnings Query", "section": "A", "priority": "critical"},
                {"type": "SSA-831", "description": "Disability Report", "section": "A", "priority": "high"},
                {"type": "SSA-1696", "description": "Appointment of Representative", "section": "B", "priority": "medium"},
                {"type": "HA-507", "description": "Request for Hearing", "section": "B", "priority": "high"},
                {"type": "SSA-3368", "description": "Disability Report - Adult", "section": "E", "priority": "critical"},
                {"type": "SSA-3369", "description": "Work History Report", "section": "E", "priority": "high"},
                {"type": "SSA-3373", "description": "Function Report - Adult", "section": "E", "priority": "high"},
                {"type": "MEDICAL_RECORD", "description": "Medical Records", "section": "F", "priority": "critical"},
            ]
        }

    return router
