"""Bedrock LLM adapter.

Implements LLMPort interface by directly using boto3.
Includes rate limiting and usage tracking.
"""
import asyncio
import base64
import json
import logging
import time
from datetime import datetime
from typing import List, Optional

import boto3
from botocore.config import Config

from app.core.ports.llm import LLMPort, ModelConfig
from app.core.exceptions import LLMError
from app.adapters.llm.rate_limiter import RateLimiter
from app.adapters.llm.usage_tracker import CostTracker, UsageStats

logger = logging.getLogger(__name__)


class BedrockAdapter(LLMPort):
    """AWS Bedrock implementation of LLMPort.

    Directly uses boto3 bedrock-runtime client.
    Code extracted from BedrockProvider in llm_manager.py.
    """

    # Model configurations
    _MODEL_CONFIGS = {
        "haiku": ModelConfig(
            name="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            role="medical_data_extraction",
            max_tokens=65536,
            temperature=0.1,
            timeout=120.0,
            context_window=200000,
            system_prompt="You are an expert medical record analyst.",
        ),
        "sonnet": ModelConfig(
            name="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            role="complex_reasoning",
            max_tokens=65536,
            temperature=0.1,
            timeout=180.0,
            context_window=200000,
            system_prompt="You are an expert medical record analyst.",
        ),
    }

    def __init__(self, region: str = "us-east-1", requests_per_minute: int = 50):
        """Initialize adapter with boto3 client.

        Args:
            region: AWS region for Bedrock service
            requests_per_minute: Rate limit for API calls
        """
        session = boto3.Session()
        # Increase read timeout for large text chunks (default 60s is too short)
        boto_config = Config(read_timeout=180, connect_timeout=10)
        self._client = session.client("bedrock-runtime", region_name=region, config=boto_config)
        self._rate_limiter = RateLimiter(requests_per_minute=requests_per_minute)
        self._cost_tracker = CostTracker()

    @property
    def cost_tracker(self) -> CostTracker:
        """Access the cost tracker for usage statistics."""
        return self._cost_tracker

    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a model."""
        if model not in self._MODEL_CONFIGS:
            raise LLMError(f"Unknown model: {model}. Available: {list(self._MODEL_CONFIGS.keys())}")
        return self._MODEL_CONFIGS[model]

    async def generate(
        self,
        prompt: str,
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate text completion via Bedrock.

        Includes rate limiting and usage tracking.
        """
        # Apply rate limiting
        await self._rate_limiter.acquire()

        config = self.get_model_config(model)
        start_time = time.time()

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": temperature or config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system or config.system_prompt:
            request_body["system"] = system or config.system_prompt

        try:
            # Bedrock is sync, run in executor for async compatibility
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.invoke_model(
                    modelId=config.name,
                    body=json.dumps(request_body)
                ),
            )

            response_body = json.loads(response["body"].read())
            content = response_body["content"][0]["text"]

            # Track usage
            usage = response_body.get("usage", {})
            prompt_tokens = usage.get("input_tokens", 0)
            completion_tokens = usage.get("output_tokens", 0)

            stats = UsageStats(
                model=config.name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_estimate=self._cost_tracker.estimate_cost(
                    model, prompt_tokens, completion_tokens
                ),
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
            )
            self._cost_tracker.track(stats)

            return content

        except Exception as e:
            logger.error(f"Bedrock generate failed: {e}")
            raise LLMError(f"Bedrock generate failed: {e}") from e

    async def generate_with_vision(
        self,
        prompt: str,
        images: List[bytes],
        model: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> str:
        """Generate completion from text and images via Bedrock.

        Includes rate limiting and usage tracking.
        """
        # Apply rate limiting
        await self._rate_limiter.acquire()

        config = self.get_model_config(model)
        start_time = time.time()

        # Build content with images + text
        content = []
        for img_bytes in images:
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_base64
                }
            })
        content.append({"type": "text", "text": prompt})

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": temperature or config.temperature,
            "messages": [{"role": "user", "content": content}],
        }

        if system or config.system_prompt:
            request_body["system"] = system or config.system_prompt

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.invoke_model(
                    modelId=config.name,
                    body=json.dumps(request_body)
                ),
            )

            response_body = json.loads(response["body"].read())
            result = response_body["content"][0]["text"]

            # Track usage
            usage = response_body.get("usage", {})
            prompt_tokens = usage.get("input_tokens", 0)
            completion_tokens = usage.get("output_tokens", 0)

            stats = UsageStats(
                model=config.name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost_estimate=self._cost_tracker.estimate_cost(
                    model, prompt_tokens, completion_tokens
                ),
                response_time=time.time() - start_time,
                timestamp=datetime.now(),
            )
            self._cost_tracker.track(stats)

            return result

        except Exception as e:
            logger.error(f"Bedrock vision failed: {e}")
            raise LLMError(f"Bedrock vision failed: {e}") from e
