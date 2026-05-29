"""
Pluggable AI client with a stable interface.

The provider is selected at runtime via the AI_PROVIDER env var so the model is
swappable without code changes ("plug and play"):

    AI_PROVIDER=anthropic     → Claude (default), with prompt caching
    AI_PROVIDER=azure_openai  → Azure OpenAI (e.g. the droid-llm resource)
    AI_PROVIDER=mock          → deterministic template, no external calls

Every provider returns the SAME shape:
    {"content": str, "usage": dict, "cost_usd": float, "model": str}

CRITICAL: any provider error (missing key, SDK not installed, API failure) is
caught and falls back to the mock provider. A bad AI configuration must never
take down the deployed service.

Cost model (claude-sonnet-4-6 as of 2026-05):
  Input $3.00 / Cache write $3.75 / Cache read $0.30 / Output $15.00  (per M tokens)
"""

import os
from typing import Any

PROVIDER = os.getenv("AI_PROVIDER", "anthropic").lower()

# ── Anthropic ────────────────────────────────────────────────────────────────

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

INPUT_COST = 3.00 / 1_000_000
CACHE_WRITE_COST = 3.75 / 1_000_000
CACHE_READ_COST = 0.30 / 1_000_000
OUTPUT_COST = 15.00 / 1_000_000

_anthropic_client: Any = None


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _anthropic_client = anthropic.Anthropic(api_key=api_key)
    return _anthropic_client


def estimate_cost(usage: dict[str, int]) -> float:
    return (
        usage.get("input_tokens", 0) * INPUT_COST
        + usage.get("output_tokens", 0) * OUTPUT_COST
        + usage.get("cache_read_input_tokens", 0) * CACHE_READ_COST
        + usage.get("cache_creation_input_tokens", 0) * CACHE_WRITE_COST
    )


def _anthropic_generate(
    system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
) -> dict[str, Any]:
    client = _get_anthropic()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                # Cache the system/KB block — reused across calls in a workspace.
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
        "model": ANTHROPIC_MODEL,
    }


# ── Azure OpenAI ─────────────────────────────────────────────────────────────
# Uses the existing droid-llm AI Services resource. The deployment name is the
# model the customer wants (e.g. gpt-4.1-nano). Endpoint/key/deployment come
# entirely from env so swapping models is a config change, not a code change.

# Rough per-token estimate for the small default deployment (nano-class). These
# are best-effort; treat cost_usd as an estimate for the Azure path.
AZURE_INPUT_COST = float(os.getenv("AZURE_OPENAI_INPUT_COST_PER_M", "0.10")) / 1_000_000
AZURE_OUTPUT_COST = float(os.getenv("AZURE_OPENAI_OUTPUT_COST_PER_M", "0.40")) / 1_000_000

_azure_client: Any = None


def _get_azure():
    global _azure_client
    if _azure_client is None:
        from openai import AzureOpenAI

        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        if not endpoint or not api_key:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY not set")
        _azure_client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )
    return _azure_client


def _azure_generate(
    system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
) -> dict[str, Any]:
    client = _get_azure()
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-nano")
    response = client.chat.completions.create(
        model=deployment,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    u = response.usage
    cached = 0
    details = getattr(u, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", 0) or 0
    usage = {
        "input_tokens": u.prompt_tokens,
        "output_tokens": u.completion_tokens,
        "cache_read_input_tokens": cached,
        "cache_creation_input_tokens": 0,
    }
    cost = u.prompt_tokens * AZURE_INPUT_COST + u.completion_tokens * AZURE_OUTPUT_COST
    return {
        "content": response.choices[0].message.content or "",
        "usage": usage,
        "cost_usd": cost,
        "model": f"azure:{deployment}",
    }


# ── Mock (deterministic fallback) ──────────────────────────────────────────────


def _mock_generate(
    system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
) -> dict[str, Any]:
    # Deterministic stand-in so the service stays up with no AI provider/key.
    snippet = user_prompt.strip().replace("\n", " ")[:240]
    content = (
        "[mock AI output — no live provider configured]\n"
        f"Context received: {snippet}"
    )
    return {
        "content": content,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        "cost_usd": 0.0,
        "model": "mock",
    }


# ── Public entrypoint (stable signature — callers depend on this) ───────────────


def generate_with_cache(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """
    Generate text via the configured provider. Returns
    {"content": str, "usage": dict, "cost_usd": float, "model": str}.

    Any provider failure degrades to the mock provider so the service never
    crashes on a missing key or AI outage.
    """
    try:
        if PROVIDER == "azure_openai":
            return _azure_generate(system_prompt, user_prompt, max_tokens, temperature)
        if PROVIDER == "mock":
            return _mock_generate(system_prompt, user_prompt, max_tokens, temperature)
        return _anthropic_generate(system_prompt, user_prompt, max_tokens, temperature)
    except Exception as exc:  # noqa: BLE001 — intentional catch-all to stay up
        print(f"[ai_client] provider '{PROVIDER}' failed ({exc}); falling back to mock")
        return _mock_generate(system_prompt, user_prompt, max_tokens, temperature)
