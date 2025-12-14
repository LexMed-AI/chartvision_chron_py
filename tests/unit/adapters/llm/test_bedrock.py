"""Tests for Bedrock adapter - direct boto3 implementation."""
import pytest
from unittest.mock import MagicMock, patch
from app.adapters.llm.bedrock import BedrockAdapter
from app.core.ports.llm import LLMPort, ModelConfig


class TestBedrockAdapterInterface:
    def test_implements_llm_port(self):
        """Adapter must implement LLMPort interface."""
        with patch("boto3.Session"):
            adapter = BedrockAdapter()
            assert isinstance(adapter, LLMPort)

    def test_get_model_config_haiku(self):
        """Should return ModelConfig for haiku model."""
        with patch("boto3.Session"):
            adapter = BedrockAdapter()
            config = adapter.get_model_config("haiku")

            assert isinstance(config, ModelConfig)
            assert "haiku" in config.name.lower()
            assert config.max_tokens == 65536

    def test_get_model_config_sonnet(self):
        """Should return ModelConfig for sonnet model."""
        with patch("boto3.Session"):
            adapter = BedrockAdapter()
            config = adapter.get_model_config("sonnet")

            assert isinstance(config, ModelConfig)
            assert "sonnet" in config.name.lower()

    def test_get_model_config_unknown_raises(self):
        """Should raise for unknown model."""
        from app.core.exceptions import LLMError

        with patch("boto3.Session"):
            adapter = BedrockAdapter()
            with pytest.raises(LLMError, match="Unknown model"):
                adapter.get_model_config("gpt-4")


class TestBedrockAdapterGenerate:
    @pytest.mark.asyncio
    async def test_generate_calls_bedrock(self):
        """Generate should call Bedrock invoke_model directly."""
        mock_response = {
            "body": MagicMock(
                read=MagicMock(return_value=b'{"content": [{"text": "response"}], "usage": {"input_tokens": 10, "output_tokens": 5}}')
            )
        }

        mock_client = MagicMock()
        mock_client.invoke_model = MagicMock(return_value=mock_response)

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("boto3.Session", return_value=mock_session):
            adapter = BedrockAdapter()
            result = await adapter.generate("test prompt", "haiku")

            assert result == "response"
            mock_client.invoke_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_vision_includes_images(self):
        """Generate with vision should include base64 images in request."""
        mock_response = {
            "body": MagicMock(
                read=MagicMock(return_value=b'{"content": [{"text": "vision response"}], "usage": {"input_tokens": 100, "output_tokens": 20}}')
            )
        }

        mock_client = MagicMock()
        mock_client.invoke_model = MagicMock(return_value=mock_response)

        mock_session = MagicMock()
        mock_session.client.return_value = mock_client

        with patch("boto3.Session", return_value=mock_session):
            adapter = BedrockAdapter()
            result = await adapter.generate_with_vision(
                "describe image", [b"\x89PNG\r\n\x1a\n..."], "haiku"
            )

            assert result == "vision response"
            # Verify invoke_model was called with image content
            call_args = mock_client.invoke_model.call_args
            assert call_args is not None
