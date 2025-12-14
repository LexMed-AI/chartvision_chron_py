"""ERE document processing routes"""
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

from app.api.job_processors import process_ere_job
from app.api.schemas import (EREProcessResponse, EREResultResponse,
                             EREStatusResponse)

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


def create_ere_router(
    active_jobs,
    job_queue,
    chronology_engine,
    pdf_adapter,
    verify_token_func,
    active_jobs_gauge
) -> APIRouter:
    """Create ERE processing router with dependency injection.

    Args:
        active_jobs: JobStore instance for tracking active jobs
        job_queue: asyncio.Queue for job queuing
        chronology_engine: ChronologyEngine instance
        pdf_adapter: PDF processing adapter
        verify_token_func: Token verification function
        active_jobs_gauge: Prometheus Gauge for active jobs metric

    Returns:
        APIRouter configured with ERE processing endpoints
    """
    router = APIRouter(tags=["ERE Processing"])
    security = HTTPBearer()

    async def get_current_token(credentials=Depends(security)) -> str:
        """Dependency wrapper for verify_token"""
        return await verify_token_func(credentials)

    @router.post("/api/v1/ere/process", response_model=EREProcessResponse)
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
        """Process ERE PDF document with chronology extraction"""
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

            active_jobs[job_id] = job_data
            active_jobs_gauge.set(len(active_jobs))

            background_tasks.add_task(
                process_ere_job, job_id, active_jobs, chronology_engine
            )

            return EREProcessResponse(
                job_id=job_id,
                status="queued",
                message="Document processing started",
                estimated_completion=datetime.now() + timedelta(seconds=85),
            )

        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            if job_id in active_jobs:
                del active_jobs[job_id]
                active_jobs_gauge.set(len(active_jobs))
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    @router.get("/api/v1/ere/status/{job_id}", response_model=EREStatusResponse)
    @limiter.limit("60/minute")
    async def get_job_status(
        request: Request, job_id: str, token: str = Depends(get_current_token)
    ):
        """Get status of ERE processing job"""
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job_data = active_jobs[job_id]
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

    @router.get("/api/v1/ere/results/{job_id}", response_model=EREResultResponse)
    @limiter.limit("30/minute")
    async def get_job_results(
        request: Request, job_id: str, token: str = Depends(get_current_token)
    ):
        """Get results of completed ERE processing job"""
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job_data = active_jobs[job_id]
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

    @router.delete("/api/v1/ere/jobs/{job_id}")
    @limiter.limit("10/minute")
    async def cancel_job(request: Request, job_id: str, token: str = Depends(get_current_token)):
        """Cancel a running ERE processing job"""
        if job_id not in active_jobs:
            raise HTTPException(status_code=404, detail="Job not found")

        job_data = active_jobs[job_id]
        if job_data["status"] in ["completed", "failed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job with status: {job_data['status']}",
            )

        job_data["status"] = "cancelled"
        job_data["completed_at"] = datetime.now()
        return {"message": "Job cancelled successfully"}

    @router.get("/api/v1/ere/jobs")
    @limiter.limit("20/minute")
    async def list_jobs(
        request: Request,
        status: Optional[str] = None,
        limit: int = 50,
        token: str = Depends(get_current_token),
    ):
        """List all ERE processing jobs with optional status filter"""
        jobs = []
        for job_id, job_data in active_jobs.items():
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

        return {"jobs": jobs, "total": len(active_jobs)}

    @router.get("/api/v1/ere/pdf/{job_id}")
    @limiter.limit("10/minute")
    async def get_ere_pdf(
        request: Request,
        job_id: str,
        token: str = Depends(get_current_token),
    ):
        """Download PDF report for ERE job (generated via Gotenberg)."""
        # Load job from persisted JSON file
        project_root = Path(__file__).parent.parent.parent.parent
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

    return router
