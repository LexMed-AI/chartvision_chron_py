"""Tests for core exceptions."""
import pytest
from app.core.exceptions import (
    CoreError,
    LLMError,
    PDFError,
    ExtractionError,
    ValidationError,
    StorageError,
)


class TestExceptionHierarchy:
    def test_llm_error_is_core_error(self):
        error = LLMError("test")
        assert isinstance(error, CoreError)

    def test_pdf_error_is_core_error(self):
        error = PDFError("test")
        assert isinstance(error, CoreError)

    def test_extraction_error_is_core_error(self):
        error = ExtractionError("test")
        assert isinstance(error, CoreError)

    def test_validation_error_is_core_error(self):
        error = ValidationError("test")
        assert isinstance(error, CoreError)

    def test_storage_error_is_core_error(self):
        error = StorageError("test")
        assert isinstance(error, CoreError)

    def test_error_message_preserved(self):
        error = LLMError("specific message")
        assert str(error) == "specific message"
