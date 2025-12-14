"""
Medical Chronology Models
Shared data structures for medical chronology engine components.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class MedicalEvent:
    """Represents a medical event with temporal and source information."""

    event_type: str
    date: datetime
    provider: str
    description: str
    diagnosis: Optional[str] = None
    procedure: Optional[str] = None
    medications: List[str] = field(default_factory=list)
    severity: Optional[str] = None
    location: Optional[str] = None
    confidence: float = 1.0
    source_page: Optional[int] = None
    source_text: Optional[str] = None
    
    # Additional metadata
    follow_up_required: bool = False
    critical_finding: bool = False
    exhibit_reference: Optional[str] = None
    exhibit_source: Optional[str] = None  # Added for compatibility
    page_number: Optional[int] = None     # Added for compatibility
    metadata: Dict[str, Any] = field(default_factory=dict)  # Added for extensibility


class DiagnosisType(Enum):
    """Types of diagnoses."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    COMORBIDITY = "comorbidity"
    PROVISIONAL = "provisional"
    DIFFERENTIAL = "differential"
    RULED_OUT = "ruled_out"


class ProcessingMode(Enum):
    """Processing modes for chronology generation."""
    SYNC = "sync"
    ASYNC = "async"
    BATCH = "batch"


class AnalysisLevel(Enum):
    """Analysis depth levels."""
    BASIC = "basic"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


@dataclass
class DiagnosisInfo:
    """Information about a diagnosis."""

    diagnosis: str
    icd_code: Optional[str] = None
    diagnosis_type: DiagnosisType = DiagnosisType.PRIMARY
    first_diagnosed: Optional[datetime] = None
    last_mentioned: Optional[datetime] = None
    provider: Optional[str] = None
    confidence: float = 1.0
    related_diagnoses: List[str] = field(default_factory=list)
    treatments: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    severity_notes: Optional[str] = None
    status: str = "active"  # active, resolved, chronic, etc.

    # Additional fields for diagnosis tracking
    severity: Optional[str] = None
    related_symptoms: set = field(default_factory=set)
    related_procedures: set = field(default_factory=set)
    evolution: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MedicalTimeline:
    """Complete medical timeline for a patient."""

    events: List[MedicalEvent] = field(default_factory=list)
    diagnoses: Dict[str, DiagnosisInfo] = field(default_factory=dict)
    providers: List[str] = field(default_factory=list)
    date_range: Optional[tuple] = None

    # Summary statistics
    total_events: int = 0
    total_providers: int = 0
    primary_diagnoses: List[str] = field(default_factory=list)

    # Analysis results
    gaps_identified: List[Dict[str, Any]] = field(default_factory=list)
    key_events: List[MedicalEvent] = field(default_factory=list)
    treatment_patterns: Dict[str, Any] = field(default_factory=dict)

    # Enhanced features from other implementations
    attorney_insights: List[Dict[str, str]] = field(default_factory=list)
    case_valuation: Dict[str, Any] = field(default_factory=dict)
    legal_significance: str = "MODERATE"
    medical_complexity: str = "MODERATE"


@dataclass
class ChronologyEvent:
    """
    Universal event representation for all chronology types.

    Consolidates features from AIChronologyEngine for:
    - Multi-type events (medical, procedural, work, disability)
    - Precise page-level citations
    - Exhibit hyperlinking
    - Related event tracking
    """
    event_id: str
    event_type: str  # medical, procedural, work, disability
    date: datetime
    end_date: Optional[datetime] = None
    title: str = ""
    description: str = ""
    source_exhibit: str = ""
    source_pages: List[int] = field(default_factory=list)
    provider: Optional[str] = None
    location: Optional[str] = None
    significance: str = "normal"  # critical, high, normal, low
    category: str = ""
    subcategory: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    hyperlinks: List[str] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)


@dataclass
class ChronologyConfig:
    """Configuration for unified chronology engine."""

    # Processing configuration
    processing_mode: ProcessingMode = ProcessingMode.SYNC
    analysis_level: AnalysisLevel = AnalysisLevel.STANDARD

    # Template path (uses default if not specified)
    template_path: Optional[str] = None

    # LLM configuration
    use_haiku: bool = True
    haiku_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

    # Processing limits
    max_concurrent_workers: int = 5
    batch_size: int = 10
    timeout_seconds: int = 180

    # Analysis configuration
    include_gap_analysis: bool = True

    # Output configuration
    generate_html: bool = True
    generate_markdown: bool = True

    # Quality thresholds
    min_confidence: float = 0.3
    gap_threshold_days: int = 30
    critical_gap_days: int = 180

    # Enhanced features
    enable_bookmarks: bool = False
    bookmark_metadata_path: Optional[str] = None
    include_hyperlinks: bool = False


@dataclass
class ConsolidatedData:
    """Consolidated medical data from all sources."""

    patient_name: str = "Unknown Patient"
    case_id: str = "Unknown Case"
    processed_exhibits: int = 0
    total_exhibits: int = 0
    data_completeness: float = 0.0
    confidence_score: float = 0.0

    # Medical data from template extraction
    all_diagnoses: List[Dict[str, Any]] = field(default_factory=list)
    all_treatments: List[Dict[str, Any]] = field(default_factory=list)
    all_medications: List[str] = field(default_factory=list)
    all_providers: List[Dict[str, Any]] = field(default_factory=list)
    medical_timeline: List[Dict[str, Any]] = field(default_factory=list)
    critical_dates: Dict[str, str] = field(default_factory=dict)

    # Section-specific data
    f_section_exhibits: List[Dict[str, Any]] = field(default_factory=list)
    section_summaries: Dict[str, Any] = field(default_factory=dict)

    # Treatment analysis
    treatment_gaps: List[Dict[str, Any]] = field(default_factory=list)

    # ChartVision section data
    all_procedures: List[Dict[str, Any]] = field(default_factory=list)
    all_diagnostic_tests: List[Dict[str, Any]] = field(default_factory=list)
    all_functional_limitations: List[Dict[str, Any]] = field(default_factory=list)
    occupational_history: List[Dict[str, Any]] = field(default_factory=list)
    medical_source_opinions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class UnifiedChronologyResult:
    """Comprehensive result from unified chronology analysis."""

    success: bool
    processing_time: float
    processing_mode: ProcessingMode
    analysis_level: AnalysisLevel

    # Core chronology data
    timeline: MedicalTimeline
    events: List[MedicalEvent]
    providers: List[Dict[str, Any]]
    diagnoses: List[Dict[str, Any]]
    treatment_gaps: List[Dict[str, Any]]

    # Advanced analysis
    gap_analysis: Dict[str, Any] = field(default_factory=dict)

    # Quality metrics
    statistics: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Dict[str, Any] = field(default_factory=dict)

    # Output formats
    html_timeline: str = ""
    markdown_report: str = ""
    json_export: Dict[str, Any] = field(default_factory=dict)

    # Error handling
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    # Metrics
    cost_estimate: float = 0.0
    confidence_score: float = 0.0