"""
API Pydantic models for ERE PDF Processing Pipeline.

Request/response models used by the ERE API endpoints.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class EREProcessRequest(BaseModel):
    """Request model for ERE PDF processing"""

    file_path: Optional[str] = None
    file_data: Optional[str] = None  # Base64 encoded file data
    filename: str = Field(..., description="Original filename")
    document_type: Optional[str] = Field(
        None, description="ERE document type (auto-detected if not provided)"
    )
    priority: int = Field(
        1, ge=1, le=5, description="Processing priority (1=lowest, 5=highest)"
    )
    sections: Optional[List[str]] = Field(
        None, description="Specific sections to process"
    )
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional processing options"
    )

    @validator("filename")
    def validate_filename(cls, v):
        if not v.endswith(".pdf"):
            raise ValueError("Only PDF files are supported")
        return v


class EREProcessResponse(BaseModel):
    """Response model for ERE PDF processing"""

    job_id: str
    status: str
    message: str
    estimated_completion: Optional[datetime] = None


class EREStatusResponse(BaseModel):
    """Response model for job status"""

    job_id: str
    status: str
    progress: float = Field(ge=0, le=100)
    current_step: Optional[str] = None
    steps_completed: List[str] = Field(default_factory=list)
    estimated_remaining: Optional[int] = None  # seconds
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class DDEExtractionResult(BaseModel):
    """DDE (Disability Determination Explanation) extraction result."""

    claimant_name: Optional[str] = Field(None, description="Claimant full name")
    date_of_birth: Optional[str] = Field(None, description="Date of birth (MM/DD/YYYY)")
    claim_type: Optional[str] = Field(None, description="Claim type (Title II, XVI, Concurrent)")
    alleged_onset_date: Optional[str] = Field(None, description="Alleged onset date")
    date_last_insured: Optional[str] = Field(None, description="Date last insured (Title II)")
    assessment_type: Optional[str] = Field(None, description="Physical RFC, Mental RFC/PRTF, or Combined")
    determination_level: Optional[str] = Field(None, description="Initial or Reconsideration")
    exertional_capacity: Optional[str] = Field(None, description="Sedentary, Light, Medium, Heavy")
    primary_diagnoses: Optional[List[Dict[str, Any]]] = Field(None, description="List of diagnoses with ICD codes")
    paragraph_b_criteria: Optional[Dict[str, str]] = Field(None, description="PRTF Paragraph B ratings")
    consultant_narrative: Optional[str] = Field(None, description="Consultant RFC narrative")
    evidence_cited: Optional[List[Dict[str, Any]]] = Field(None, description="Medical evidence exhibits cited")


class EREResultData(BaseModel):
    """Structured ERE processing result data."""

    segments: int = Field(0, description="Number of PDF segments/exhibits found")
    chronology_entries: int = Field(0, description="Number of chronology entries extracted")
    entries: List[Dict[str, Any]] = Field(default_factory=list, description="Chronology entry details")
    sections_found: List[str] = Field(default_factory=list, description="ERE sections found (A, B, D, E, F)")
    dde_extraction: Optional[Dict[str, Any]] = Field(None, description="DDE extraction result from Section A")
    dde_extracted: bool = Field(False, description="Whether DDE was successfully extracted")


class EREResultResponse(BaseModel):
    """Response model for processing results"""

    job_id: str
    status: str
    processing_time: Optional[float] = None
    results: Optional[EREResultData] = Field(None, description="Structured processing results")
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    class Config:
        # Allow dict assignment for backwards compatibility
        extra = "allow"


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    timestamp: datetime
    version: str
    uptime: float
    system_info: Dict[str, Any]
    pipeline_status: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime


__all__ = [
    "EREProcessRequest",
    "EREProcessResponse",
    "EREStatusResponse",
    "EREResultResponse",
    "EREResultData",
    "DDEExtractionResult",
    "HealthResponse",
    "ErrorResponse",
]
