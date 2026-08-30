from __future__ import annotations

import os
import pytest
from typing import Any


def _has_live_credentials() -> bool:
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY")
    )


def _get_model() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic/claude-sonnet-4-20250514"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai/gpt-4o"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter/anthropic/claude-sonnet-4-20250514"
    return "anthropic/claude-sonnet-4-20250514"


pytestmark = pytest.mark.skipif(
    not _has_live_credentials(),
    reason="No live LLM credentials available (set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY)",
)


@pytest.fixture
def live_agent():
    from bahram.core.agent import Agent
    from bahram.core.config import Config

    config = Config()
    config.agent.model = _get_model()
    agent = Agent(config=config)
    return agent


@pytest.fixture
def live_model():
    return _get_model()
