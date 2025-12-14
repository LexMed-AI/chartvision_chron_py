"""
Retry utilities for handling API throttling and transient failures.

Provides exponential backoff retry decorators and helpers for use
with AWS Bedrock and other LLM providers.
"""
import asyncio
import functools
import logging
import random
from typing import Any, Callable, Optional, Set, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Default retryable exceptions for AWS Bedrock
BEDROCK_RETRYABLE_ERRORS = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelTimeoutException",
    "ProvisionedThroughputExceededException",
    "ReadTimeoutError",  # botocore timeout
    "ConnectTimeoutError",  # botocore timeout
}


def is_retryable_error(error: Exception, retryable_types: Optional[Set[str]] = None) -> bool:
    """
    Check if an error is retryable.

    Args:
        error: The exception to check
        retryable_types: Set of error type names to retry (defaults to BEDROCK_RETRYABLE_ERRORS)

    Returns:
        True if error should be retried
    """
    if retryable_types is None:
        retryable_types = BEDROCK_RETRYABLE_ERRORS

    error_name = type(error).__name__
    error_str = str(error).lower()

    # Check by exception class name
    if error_name in retryable_types:
        return True

    # Check for common throttling indicators in error message
    throttle_indicators = ["throttl", "rate limit", "too many requests", "capacity"]
    if any(indicator in error_str for indicator in throttle_indicators):
        return True

    # Check for ClientError with specific error codes (boto3)
    if hasattr(error, "response"):
        error_code = error.response.get("Error", {}).get("Code", "")
        if error_code in retryable_types:
            return True

    return False


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_check: Optional[Callable[[Exception], bool]] = None,
    **kwargs
) -> T:
    """
    Execute function with exponential backoff retry.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Add random jitter to prevent thundering herd
        retryable_check: Custom function to check if error is retryable
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        Last exception if all retries exhausted
    """
    if retryable_check is None:
        retryable_check = is_retryable_error

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, functools.partial(func, *args, **kwargs)
                )

        except Exception as e:
            last_error = e

            if attempt >= max_retries or not retryable_check(e):
                logger.error(
                    f"Retry exhausted after {attempt + 1} attempts: {e}"
                )
                raise

            # Calculate delay with exponential backoff
            delay = min(base_delay * (exponential_base ** attempt), max_delay)

            # Add jitter (0-50% of delay)
            if jitter:
                delay = delay * (1 + random.random() * 0.5)

            logger.warning(
                f"Retry attempt {attempt + 1}/{max_retries} after {delay:.1f}s: {e}"
            )
            await asyncio.sleep(delay)

    raise last_error


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: Optional[tuple] = None,
):
    """
    Decorator for adding exponential backoff retry to async functions.

    Usage:
        @with_retry(max_retries=3)
        async def call_api():
            ...

    Args:
        max_retries: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        retryable_exceptions: Tuple of exception types to retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            def check_retryable(e: Exception) -> bool:
                if retryable_exceptions:
                    return isinstance(e, retryable_exceptions)
                return is_retryable_error(e)

            return await retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_check=check_retryable,
                **kwargs
            )
        return wrapper
    return decorator


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    @classmethod
    def for_bedrock(cls) -> "RetryConfig":
        """Standard retry config for AWS Bedrock API calls."""
        return cls(
            max_retries=5,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True,
        )

    @classmethod
    def aggressive(cls) -> "RetryConfig":
        """Aggressive retry config for critical operations."""
        return cls(
            max_retries=10,
            base_delay=0.5,
            max_delay=120.0,
            exponential_base=1.5,
            jitter=True,
        )

    @classmethod
    def conservative(cls) -> "RetryConfig":
        """Conservative retry config to minimize API calls."""
        return cls(
            max_retries=2,
            base_delay=2.0,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=True,
        )
