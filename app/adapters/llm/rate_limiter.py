"""Rate limiting for LLM API calls.

Sliding window rate limiter to prevent hitting API rate limits.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List


class RateLimiter:
    """Sliding window rate limiter for API calls.

    Tracks requests in a sliding time window and delays new requests
    when the limit is reached.
    """

    def __init__(self, requests_per_minute: int = 50):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self._requests: List[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire rate limit token, waiting if necessary.

        Blocks until a request slot is available within the rate limit.
        """
        async with self._lock:
            now = datetime.now()
            window_start = now - timedelta(minutes=1)

            # Remove requests outside the sliding window
            self._requests = [r for r in self._requests if r > window_start]

            # If at limit, wait for oldest request to expire
            if len(self._requests) >= self.requests_per_minute:
                oldest = self._requests[0]
                sleep_time = (oldest + timedelta(minutes=1) - now).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                # Clean up again after waiting
                now = datetime.now()
                window_start = now - timedelta(minutes=1)
                self._requests = [r for r in self._requests if r > window_start]

            # Record this request
            self._requests.append(datetime.now())

    def current_usage(self) -> int:
        """Get current number of requests in the window."""
        now = datetime.now()
        window_start = now - timedelta(minutes=1)
        return len([r for r in self._requests if r > window_start])

    def reset(self) -> None:
        """Reset the rate limiter (for testing)."""
        self._requests = []
