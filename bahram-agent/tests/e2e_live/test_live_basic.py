from __future__ import annotations

import asyncio
from typing import Any

import pytest


class TestLiveBasicToolUse:
    @pytest.mark.asyncio
    async def test_simple_tool_call(self, live_agent, live_model):
        await live_agent.start()
        response = await live_agent.run(
            "Use the bash tool to run: echo 'hello from bahram'",
            model=live_model,
        )
        assert response.content is not None
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_file_operations(self, live_agent, live_model, tmp_path):
        await live_agent.start()
        test_file = tmp_path / "test.txt"
        response = await live_agent.run(
            f"Write the text 'test content' to the file {test_file} using the write tool, then read it back.",
            model=live_model,
        )
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_multi_step_task(self, live_agent, live_model):
        await live_agent.start()
        response = await live_agent.run(
            "Create a Python function that calculates fibonacci numbers, "
            "then use the execute_code tool to test it with n=10.",
            model=live_model,
        )
        assert response.content is not None
        assert len(response.content) > 0


class TestLivePlanning:
    @pytest.mark.asyncio
    async def test_planned_execution(self, live_agent, live_model):
        await live_agent.start()
        response = await live_agent.run(
            "Plan and execute: create a file called 'countdown.py' that prints numbers from 10 to 1, "
            "then run it to verify it works.",
            model=live_model,
            use_planning=True,
        )
        assert response.content is not None


class TestLiveMemory:
    @pytest.mark.asyncio
    async def test_memory_persistence(self, live_agent, live_model):
        await live_agent.start()
        session = live_agent.create_session()
        await live_agent.run(
            "Remember that the secret convention for this project is to use tabs not spaces.",
            session_id=session.id,
            model=live_model,
        )
        response = await live_agent.run(
            "What is the secret convention for this project?",
            session_id=session.id,
            model=live_model,
        )
        assert response.content is not None


class TestLiveFailureRecovery:
    @pytest.mark.asyncio
    async def testHandlesBadCommand(self, live_agent, live_model):
        await live_agent.start()
        response = await live_agent.run(
            "Try to run the command 'nonexistent_command_xyz' and handle the error gracefully.",
            model=live_model,
        )
        assert response.content is not None
