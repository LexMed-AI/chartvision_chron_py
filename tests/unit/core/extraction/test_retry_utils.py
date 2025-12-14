"""Tests for retry_utils module."""
import asyncio
import pytest
from app.core.extraction.retry_utils import (
    is_retryable_error,
    retry_with_backoff,
    RetryConfig,
    BEDROCK_RETRYABLE_ERRORS,
)


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_throttling_exception_is_retryable(self):
        """Test that ThrottlingException is retryable."""
        class ThrottlingException(Exception):
            pass

        error = ThrottlingException("Rate exceeded")
        assert is_retryable_error(error) is True

    def test_service_unavailable_is_retryable(self):
        """Test that ServiceUnavailableException is retryable."""
        class ServiceUnavailableException(Exception):
            pass

        error = ServiceUnavailableException("Service down")
        assert is_retryable_error(error) is True

    def test_throttle_message_is_retryable(self):
        """Test that errors with throttle in message are retryable."""
        error = Exception("Request throttled due to high load")
        assert is_retryable_error(error) is True

    def test_rate_limit_message_is_retryable(self):
        """Test that errors with rate limit in message are retryable."""
        error = Exception("Rate limit exceeded")
        assert is_retryable_error(error) is True

    def test_generic_error_not_retryable(self):
        """Test that generic errors are not retryable."""
        error = ValueError("Invalid input")
        assert is_retryable_error(error) is False

    def test_custom_retryable_types(self):
        """Test custom retryable types."""
        class CustomError(Exception):
            pass

        error = CustomError("Custom error")
        assert is_retryable_error(error, {"CustomError"}) is True
        assert is_retryable_error(error, {"OtherError"}) is False


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_succeeds_without_retry(self):
        """Test successful execution without needing retry."""
        call_count = 0

        async def success_fn():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(success_fn, max_retries=3, base_delay=0.01)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable_error(self):
        """Test that retryable errors trigger retry."""
        call_count = 0

        async def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Rate limit exceeded")
            return "success"

        result = await retry_with_backoff(
            failing_fn, max_retries=5, base_delay=0.01
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        """Test that max retries exhaustion raises exception."""
        async def always_fail():
            raise Exception("Throttling error")

        with pytest.raises(Exception, match="Throttling"):
            await retry_with_backoff(
                always_fail, max_retries=2, base_delay=0.01
            )

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Test that non-retryable errors raise immediately."""
        call_count = 0

        async def non_retryable_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")

        with pytest.raises(ValueError, match="Invalid input"):
            await retry_with_backoff(
                non_retryable_fail, max_retries=5, base_delay=0.01
            )

        assert call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_custom_retryable_check(self):
        """Test custom retryable check function."""
        call_count = 0

        async def custom_fail():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Custom retryable")
            return "success"

        # Custom check that retries ValueError
        def custom_check(e):
            return isinstance(e, ValueError)

        result = await retry_with_backoff(
            custom_fail,
            max_retries=5,
            base_delay=0.01,
            retryable_check=custom_check,
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self):
        """Test that args and kwargs are passed correctly."""
        async def fn_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = await retry_with_backoff(
            fn_with_args, "x", "y", c="z", max_retries=1, base_delay=0.01
        )

        assert result == "x-y-z"


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True

    def test_bedrock_config(self):
        """Test Bedrock-specific configuration."""
        config = RetryConfig.for_bedrock()
        assert config.max_retries == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0

    def test_aggressive_config(self):
        """Test aggressive retry configuration."""
        config = RetryConfig.aggressive()
        assert config.max_retries == 10
        assert config.base_delay == 0.5
        assert config.max_delay == 120.0

    def test_conservative_config(self):
        """Test conservative retry configuration."""
        config = RetryConfig.conservative()
        assert config.max_retries == 2
        assert config.base_delay == 2.0
        assert config.max_delay == 30.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetryConfig(
            max_retries=7,
            base_delay=0.5,
            max_delay=45.0,
            exponential_base=1.5,
            jitter=False,
        )
        assert config.max_retries == 7
        assert config.base_delay == 0.5
        assert config.max_delay == 45.0
        assert config.exponential_base == 1.5
        assert config.jitter is False
