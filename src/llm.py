"""Thin chat client for OpenAI-compatible providers (Fireworks, Gemini free tier) with retries."""
from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from src.config import ROOT

load_dotenv(ROOT / ".env")

PROVIDERS = {  # provider -> (base URL, env var holding the key)
    "fireworks": ("https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
}

MODELS = {  # short alias -> Fireworks model id (all verified callable on 2026-09-27)
    "kimi-k3": "accounts/fireworks/models/kimi-k3",
    "deepseek-v4p1-flash": "accounts/fireworks/models/deepseek-v4p1-flash",
    "glm-5p3": "accounts/fireworks/models/glm-5p3",
    "qwen3p8-max": "accounts/fireworks/models/qwen3p8-max",
    "gpt-oss-120b": "accounts/fireworks/models/gpt-oss-120b",
    "nemotron-lightning": "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b",
    "glm-5p3-flash": "accounts/fireworks/models/glm-5p3-flash",
}

# USD per 1M tokens (input, output), Fireworks serverless standard tier, checked 2026-09-27
# https://docs.fireworks.ai/serverless/pricing
PRICES = {
    "kimi-k3": (3.00, 15.00),
    "deepseek-v4p1-flash": (0.30, 1.20),
    "glm-5p3": (1.40, 4.40),
    "qwen3p8-max": (2.00, 6.00),
    "gpt-oss-120b": (0.15, 0.60),
    "nemotron-lightning": (0.05, 0.20),
    "glm-5p3-flash": (0.15, 0.50),
}


def provider(model: str) -> str:
    """Gemini models are addressed by their own id (e.g. 'gemini-2.5-flash'); everything else is Fireworks."""
    return "gemini" if model.startswith("gemini-") else "fireworks"


def has_price(model: str) -> bool:
    return provider(model) == "gemini" or model in PRICES


def cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> float:
    if provider(model) == "gemini":
        return 0.0  # free-tier key: no billing account, so calls cannot be charged
    p_in, p_out = PRICES[model]
    return ((input_tokens or 0) * p_in + (output_tokens or 0) * p_out) / 1e6


_clients: dict[str, OpenAI] = {}


def client(name: str) -> OpenAI:
    if name not in _clients:
        base_url, key_var = PROVIDERS[name]
        _clients[name] = OpenAI(api_key=os.environ[key_var], base_url=base_url, timeout=600)
    return _clients[name]


def chat(model: str, messages: list[dict], max_tokens: int = 32768, reasoning_effort: str | None = None,
         retries: int = 6) -> dict:
    """Return {'text', 'reasoning', 'input_tokens', 'output_tokens', 'finish_reason', 'seconds'}."""
    extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
    name = provider(model)
    for attempt in range(retries):
        try:
            t0 = time.time()
            r = client(name).chat.completions.create(model=MODELS.get(model, model), messages=messages,
                                                     temperature=0, max_tokens=max_tokens, **extra)
            msg = r.choices[0].message
            return {
                "text": msg.content or "",
                "reasoning": getattr(msg, "reasoning_content", None) or "",
                "input_tokens": r.usage.prompt_tokens if r.usage else None,
                "output_tokens": r.usage.completion_tokens if r.usage else None,
                "finish_reason": r.choices[0].finish_reason,
                "seconds": round(time.time() - t0, 1),
            }
        except Exception as e:  # rate limits, timeouts, transient 5xx
            status = getattr(e, "status_code", None)
            if attempt == retries - 1 or (status and 400 <= status < 500 and status != 429):
                raise
            wait = min(2 ** attempt * 5, 90)  # free-tier per-minute limits need long enough pauses
            print(f"  retry {attempt + 1} for {model} after {type(e).__name__}: {str(e)[:120]} (sleep {wait}s)")
            time.sleep(wait)
