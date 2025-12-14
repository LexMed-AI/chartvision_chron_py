"""Tests for ChronologyEngine port injection."""
import pytest
from unittest.mock import MagicMock
from app.core.extraction.engine import ChronologyEngine
from app.core.ports.llm import LLMPort


class TestChronologyEngineInjection:
    def test_accepts_llm_port(self):
        """Engine should accept LLMPort via constructor."""
        mock_llm = MagicMock(spec=LLMPort)
        engine = ChronologyEngine(llm=mock_llm)

        assert engine._llm_port is mock_llm

    def test_extractors_receive_injected_port(self):
        """Extractors should use the injected LLMPort."""
        mock_llm = MagicMock(spec=LLMPort)
        engine = ChronologyEngine(llm=mock_llm)

        # Access text_extractor property
        text_ext = engine.text_extractor
        assert text_ext is not None
        assert text_ext._llm is mock_llm

    def test_raises_without_llm(self):
        """Engine should raise if no LLM provided and lazy init disabled."""
        engine = ChronologyEngine(llm=None, allow_lazy_init=False)

        with pytest.raises(ValueError, match="LLM port required"):
            _ = engine.text_extractor

    def test_backward_compat_lazy_init(self):
        """For backward compatibility, allow lazy init if not disabled."""
        # This test verifies old code still works during migration
        engine = ChronologyEngine()  # No llm provided
        # Should not raise yet - lazy init is default
        assert engine._llm_port is None
