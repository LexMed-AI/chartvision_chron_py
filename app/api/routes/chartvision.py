"""ChartVision chronology processing routes"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form,
                     HTTPException, Request, UploadFile)
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.job_processors import process_chartvision_job

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


def create_chartvision_router(
    active_jobs,
    job_queue,
    chronology_engine,
    pdf_adapter,
    verify_token_func
) -> APIRouter:
    """Create ChartVision processing router with dependency injection.

    Args:
        active_jobs: JobStore instance for tracking active jobs
        job_queue: asyncio.Queue for job queuing
        chronology_engine: ChronologyEngine instance
        pdf_adapter: PDF processing adapter
        verify_token_func: Token verification function

    Returns:
        APIRouter configured with ChartVision processing endpoints
    """
    router = APIRouter(tags=["ChartVision"])
    security = HTTPBearer()

    async def get_current_token(credentials=Depends(security)) -> str:
        """Dependency wrapper for verify_token"""
        return await verify_token_func(credentials)

    @router.post("/api/v1/chartvision/process")
    @limiter.limit("10/minute")
    async def process_chartvision(
        request: Request,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        priority: int = Form(1),
        options: Optional[str] = Form("{}"),
        token: str = Depends(get_current_token),
    ):
        """Process medical PDF with ChartVision chronology extraction"""
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

        active_jobs[job_id] = {
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

        background_tasks.add_task(process_chartvision_job, job_id, active_jobs)

        return {
            "job_id": job_id,
            "status": "queued",
            "message": "ChartVision processing started",
            "report_url": f"/api/v1/chartvision/reports/{job_id}",
            "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat(),
        }

    @router.get("/api/v1/chartvision/reports/{job_id}")
    @limiter.limit("30/minute")
    async def get_chartvision_report(
        request: Request,
        job_id: str,
        token: str = Depends(get_current_token),
    ):
        """Get ChartVision chronology report for completed job"""
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job = active_jobs[job_id]
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

    @router.get("/api/v1/chartvision/reports/{job_id}/pdf")
    @limiter.limit("10/minute")
    async def get_chartvision_pdf(
        request: Request,
        job_id: str,
        token: str = Depends(get_current_token),
    ):
        """Download PDF report for ChartVision job"""
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job = active_jobs[job_id]
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

    return router
