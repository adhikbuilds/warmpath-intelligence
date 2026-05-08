"""
Anthropic AI client with prompt caching.

Caching strategy:
  - System prompt (KB context block) cached as ephemeral → cache_control
  - Per-request user prompt (contact/account data) NOT cached
  - Cache TTL: 5 minutes (Anthropic ephemeral cache)

Cost model (claude-sonnet-4-6 as of 2026-05):
  Input:        $3.00  / M tokens
  Cache write:  $3.75  / M tokens
  Cache read:   $0.30  / M tokens
  Output:       $15.00 / M tokens
"""

import os
from typing import Any

import anthropic

MODEL = "claude-sonnet-4-6"

INPUT_COST = 3.00 / 1_000_000
CACHE_WRITE_COST = 3.75 / 1_000_000
CACHE_READ_COST = 0.30 / 1_000_000
OUTPUT_COST = 15.00 / 1_000_000

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def estimate_cost(usage: dict[str, int]) -> float:
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    return (
        input_tokens * INPUT_COST
        + output_tokens * OUTPUT_COST
        + cache_read * CACHE_READ_COST
        + cache_write * CACHE_WRITE_COST
    )


def generate_with_cache(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """
    Send a message to Claude with the system prompt marked for caching.
    Returns {"content": str, "usage": dict, "cost_usd": float}.
    """
    client = get_client()

    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                # Mark the system prompt for caching reused across calls
                # with the same KB context
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_prompt}],
    )

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0)
        or 0,
    }

    content = ""
    for block in response.content:
        if block.type == "text":
            content = block.text
            break

    return {
        "content": content,
        "usage": usage,
        "cost_usd": estimate_cost(usage),
        "model": MODEL,
    }
