"""LLM port interface.

Defines the contract for LLM providers. Core code depends only on this
abstraction, not on specific implementations like Bedrock.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ModelConfig:
    """Configuration for a specific model.

    Loaded from config/models.json -> models.{model_key}
    """
    name: str           # e.g., "us.anthropic.claude-haiku-4-5-..."
    role: str           # e.g., "medical_data_extraction"
    max_tokens: int
    temperature: float
    timeout: float
    context_window: int
    system_prompt: str


class LLMPort(ABC):
    """Abstract interface for LLM providers.

    Implementations: BedrockAdapter
    """

    @abstractmethod
    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a model.

        Args:
            model: Model key ("haiku" or "sonnet")

        Returns:
            ModelConfig with all settings
        """
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate text completion.

        Args:
            prompt: User prompt
            model: Model key ("haiku" or "sonnet")
            max_tokens: Override config max_tokens
            temperature: Override config temperature
            system: Override config system_prompt

        Returns:
            Generated text response
        """
        pass

    @abstractmethod
    async def generate_with_vision(
        self,
        prompt: str,
        images: List[bytes],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate completion from text and images.

        Args:
            prompt: User prompt
            images: List of image bytes (PNG)
            model: Model key
            max_tokens: Override config max_tokens
            temperature: Override config temperature
            system: Override config system_prompt

        Returns:
            Generated text response
        """
        pass
