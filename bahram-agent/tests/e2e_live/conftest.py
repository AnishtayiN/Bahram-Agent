from __future__ import annotations

import os

import pytest


def _live_api_key() -> str | None:
    """Return a usable live API key or None when not configured."""
    for key in (
        "BAHRAM_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "GROQ_API_KEY",
        "GOOGLE_API_KEY",
    ):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


@pytest.fixture
def live_agent():
    """Agent backed by a real LLM API; skipped unless a key is configured."""
    if not _live_api_key():
        pytest.skip("Live API key not configured (BAHRAM_API_KEY/ANTHROPIC_API_KEY/...)")
    from bahram.core.agent import Agent
    from bahram.core.config import Config

    config = Config.from_file("config/config.yaml")
    config.agent.model = os.environ.get("BAHRAM_MODEL", "anthropic/claude-sonnet-4-20250514")
    agent = Agent(config=config)
    return agent


@pytest.fixture
def live_model() -> str:
    if not _live_api_key():
        pytest.skip("Live API key not configured (BAHRAM_API_KEY/ANTHROPIC_API_KEY/...)")
    return os.environ.get("BAHRAM_MODEL", "anthropic/claude-sonnet-4-20250514")
