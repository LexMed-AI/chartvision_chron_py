"""Abstract interfaces for external dependencies."""
from app.core.ports.llm import LLMPort, ModelConfig
from app.core.ports.pdf import PDFPort, Bookmark
from app.core.ports.storage import JobStoragePort

__all__ = [
    "LLMPort",
    "ModelConfig",
    "PDFPort",
    "Bookmark",
    "JobStoragePort",
]
