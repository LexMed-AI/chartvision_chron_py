"""Usage and cost tracking for LLM calls.

Tracks token usage, costs, and performance metrics for LLM API calls.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class UsageStats:
    """Single LLM call statistics."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_estimate: float
    response_time: float
    timestamp: datetime = field(default_factory=datetime.now)


class CostTracker:
    """Track and analyze LLM costs and usage.

    Maintains a history of API calls with token counts and cost estimates.
    """

    # Pricing per 1K tokens (as of late 2024)
    PRICING = {
        "haiku": {"input": 0.001, "output": 0.005},
        "sonnet": {"input": 0.003, "output": 0.015},
        "opus": {"input": 0.015, "output": 0.075},
    }

    def __init__(self, max_history: int = 10000):
        """Initialize cost tracker.

        Args:
            max_history: Maximum number of stats entries to retain
        """
        self._stats: List[UsageStats] = []
        self._max_history = max_history

    def track(self, stats: UsageStats) -> None:
        """Record usage statistics.

        Args:
            stats: UsageStats for a single API call
        """
        self._stats.append(stats)

        # Trim old entries if over limit
        if len(self._stats) > self._max_history:
            self._stats = self._stats[-self._max_history:]

    def estimate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Estimate cost for token counts.

        Args:
            model: Model name (or model ID containing model name)
            prompt_tokens: Input token count
            completion_tokens: Output token count

        Returns:
            Estimated cost in USD
        """
        # Find matching pricing tier
        pricing = self.PRICING.get("haiku")  # Default to cheapest
        for key, prices in self.PRICING.items():
            if key in model.lower():
                pricing = prices
                break

        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return input_cost + output_cost

    def get_summary(self, hours: int = 24) -> Dict:
        """Get cost summary for time window.

        Args:
            hours: Number of hours to include in summary

        Returns:
            Dict with total_cost, total_tokens, request_count, avg_response_time
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [s for s in self._stats if s.timestamp >= cutoff]

        if not recent:
            return {
                "total_cost": 0.0,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "request_count": 0,
                "avg_response_time": 0.0,
            }

        return {
            "total_cost": sum(s.cost_estimate for s in recent),
            "total_tokens": sum(s.total_tokens for s in recent),
            "prompt_tokens": sum(s.prompt_tokens for s in recent),
            "completion_tokens": sum(s.completion_tokens for s in recent),
            "request_count": len(recent),
            "avg_response_time": sum(s.response_time for s in recent) / len(recent),
        }

    def get_model_breakdown(self, hours: int = 24) -> Dict[str, Dict]:
        """Get cost breakdown by model.

        Args:
            hours: Number of hours to include

        Returns:
            Dict mapping model names to their usage summaries
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [s for s in self._stats if s.timestamp >= cutoff]

        breakdown: Dict[str, Dict] = {}
        for stat in recent:
            model_key = stat.model.split(":")[-1] if ":" in stat.model else stat.model
            if model_key not in breakdown:
                breakdown[model_key] = {
                    "cost": 0.0,
                    "tokens": 0,
                    "requests": 0,
                }
            breakdown[model_key]["cost"] += stat.cost_estimate
            breakdown[model_key]["tokens"] += stat.total_tokens
            breakdown[model_key]["requests"] += 1

        return breakdown

    def clear(self) -> None:
        """Clear all tracked statistics."""
        self._stats = []
