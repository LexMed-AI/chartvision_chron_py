"""
Extraction processing limits and constants.

Centralized configuration for memory limits, processing caps,
and chunking sizes used across the extraction pipeline.
"""

# Exhibit processing limits
MAX_EXHIBITS_PER_JOB = 50
"""Maximum number of exhibits to process per job (prevents timeout)"""

MAX_PAGES_PER_EXHIBIT = 50
"""Maximum pages to extract per exhibit (chunked if exceeded)"""

MAX_IMAGES_PER_EXHIBIT = 20
"""Maximum scanned page images per exhibit (prevents OOM errors)"""

# Text chunking limits
DEFAULT_CHUNK_SIZE = 40_000
"""Default character chunk size for LLM text extraction (Bedrock timeout prevention)"""
