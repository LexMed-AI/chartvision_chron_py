"""Tests for LLM port interface."""
import pytest
from dataclasses import dataclass
from app.core.ports.llm import LLMPort, ModelConfig


class TestModelConfig:
    def test_model_config_fields(self):
        config = ModelConfig(
            name="test-model",
            role="extraction",
            max_tokens=4000,
            temperature=0.1,
            timeout=120.0,
            context_window=200000,
            system_prompt="You are a test assistant.",
        )
        assert config.name == "test-model"
        assert config.max_tokens == 4000


class TestLLMPortInterface:
    def test_cannot_instantiate_abstract_port(self):
        with pytest.raises(TypeError):
            LLMPort()

    def test_concrete_implementation_works(self):
        class MockLLM(LLMPort):
            def get_model_config(self, model: str) -> ModelConfig:
                return ModelConfig(
                    name="mock", role="test", max_tokens=100,
                    temperature=0.0, timeout=10.0, context_window=1000,
                    system_prompt="test"
                )

            async def generate(self, prompt, model, **kwargs) -> str:
                return "mock response"

            async def generate_with_vision(self, prompt, images, model, **kwargs) -> str:
                return "mock vision response"

        mock = MockLLM()
        assert mock.get_model_config("test").name == "mock"
