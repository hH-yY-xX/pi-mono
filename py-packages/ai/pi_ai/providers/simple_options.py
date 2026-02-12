"""
Simple options utilities for provider implementations.
"""

from __future__ import annotations

from pi_ai.types import (
    Api,
    Model,
    SimpleStreamOptions,
    StreamOptions,
    ThinkingBudgets,
    ThinkingLevel,
)


def build_base_options(
    model: Model,
    options: SimpleStreamOptions | None = None,
    api_key: str | None = None,
) -> StreamOptions:
    """Build base stream options from simple options."""
    if options is None:
        options = SimpleStreamOptions()

    return StreamOptions(
        temperature=options.temperature,
        max_tokens=options.max_tokens or min(model.max_tokens, 32000),
        api_key=api_key or options.api_key,
        cache_retention=options.cache_retention,
        session_id=options.session_id,
        headers=options.headers,
        max_retry_delay_ms=options.max_retry_delay_ms,
    )


def clamp_reasoning(
    effort: ThinkingLevel | None,
) -> ThinkingLevel | None:
    """Clamp reasoning level (xhigh -> high for most providers)."""
    return "high" if effort == "xhigh" else effort


def adjust_max_tokens_for_thinking(
    base_max_tokens: int,
    model_max_tokens: int,
    reasoning_level: ThinkingLevel,
    custom_budgets: ThinkingBudgets | None = None,
) -> tuple[int, int]:
    """
    Adjust max tokens to accommodate thinking budget.
    
    Returns:
        Tuple of (max_tokens, thinking_budget)
    """
    default_budgets: dict[str, int] = {
        "minimal": 1024,
        "low": 2048,
        "medium": 8192,
        "high": 16384,
    }

    budgets = default_budgets.copy()
    if custom_budgets:
        if custom_budgets.minimal is not None:
            budgets["minimal"] = custom_budgets.minimal
        if custom_budgets.low is not None:
            budgets["low"] = custom_budgets.low
        if custom_budgets.medium is not None:
            budgets["medium"] = custom_budgets.medium
        if custom_budgets.high is not None:
            budgets["high"] = custom_budgets.high

    min_output_tokens = 1024
    level = clamp_reasoning(reasoning_level) or "low"
    thinking_budget = budgets.get(level, 2048)
    max_tokens = min(base_max_tokens + thinking_budget, model_max_tokens)

    if max_tokens <= thinking_budget:
        thinking_budget = max(0, max_tokens - min_output_tokens)

    return max_tokens, thinking_budget
