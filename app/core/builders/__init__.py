"""Report builders and formatters."""
from app.core.builders.chartvision_builder import ChartVisionBuilder
from app.core.builders.occurrence_formatter import OccurrenceFormatter
from app.core.builders.report_generator import ChartVisionReportGenerator
from app.core.builders.date_utils import parse_date, to_datetime
from app.core.builders.source_formatter import format_source, combine_sources
from app.core.builders.chronology_processor import (
    process_chronology,
    deduplicate_chronology,
    group_lab_panels,
)
from app.core.builders.schema_loader import (
    load_formatter_config,
    get_visit_type_schema,
    render_occurrence,
)

__all__ = [
    "ChartVisionBuilder",
    "OccurrenceFormatter",
    "ChartVisionReportGenerator",
    # Date utilities
    "parse_date",
    "to_datetime",
    # Source formatting
    "format_source",
    "combine_sources",
    # Chronology processing
    "process_chronology",
    "deduplicate_chronology",
    "group_lab_panels",
    # Schema loading
    "load_formatter_config",
    "get_visit_type_schema",
    "render_occurrence",
]
