from __future__ import annotations

import pytest
from bahram.core.engine import AgentEngine


@pytest.fixture
def engine():
    return AgentEngine()
