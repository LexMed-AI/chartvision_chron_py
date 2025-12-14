"""Core domain exceptions.

All exceptions raised by core logic inherit from CoreError.
Adapters catch provider-specific errors and re-raise as these.
"""


class CoreError(Exception):
    """Base for all core domain errors."""
    pass


class LLMError(CoreError):
    """LLM operation failed after retries."""
    pass


class PDFError(CoreError):
    """PDF operation failed."""
    pass


class ExtractionError(CoreError):
    """Extraction logic failed."""
    pass


class ValidationError(CoreError):
    """Data validation failed."""
    pass


class StorageError(CoreError):
    """Storage operation failed."""
    pass
