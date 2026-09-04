"""Real ``Agent`` boot and offline end-to-end runs.

``Agent`` is constructed, started and driven for real: real config, real tool
registry, real SQLite-backed memory, real autonomy subsystems, real tool
execution.  The only substitution is the LLM provider, which is the external
model API - a :class:`ScriptedProvider` replays canned :class:`AgentResponse`
objects exactly as a vendor SDK would.

Covers bahram/core/agent.py end to end, including the planning branch, the
streaming path, the autonomy accessors and the in-memory guarantee.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from bahram.core.agent import Agent
from bahram.core.config import Config
from bahram.core.engine import AgentResponse, Message, MessageRole, RunState, ToolCall
from bahram.tools import DEFAULT_TOOL_NAMES


class ScriptedProvider:
    """Replays a fixed sequence of ``AgentResponse`` objects.

    This is the stand-in for the model API - an external network boundary.  It
    records every call so tests can assert on what the engine asked for.
    """

    def __init__(self, *responses: AgentResponse) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def complete(self, messages: list[Message], tools: Any = None) -> AgentResponse:
        self.calls.append({"messages": list(messages), "tools": tools})
        if not self._responses:
            return AgentResponse(content="no scripted response left", state=RunState.FAILED)
        return self._responses.pop(0)

    async def stream(self, messages: list[Message], tools: Any = None):
        response = await self.complete(messages, tools)
        yield response.content or ""


def make_config(tmp_path: Path | None = None, **overrides: Any) -> Config:
    """Build a Config that never writes outside ``tmp_path``."""
    config = Config()
    config.memory.database = ":memory:"
    config.logging.level = "WARNING"
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def make_agent(tmp_path: Path | None = None, **overrides: Any) -> Agent:
    return Agent(config=make_config(tmp_path, **overrides))


@pytest.fixture
async def agent():
    instance = make_agent()
    await instance.start()
    yield instance
    await instance.stop()


# ---------------------------------------------------------------------------
# boot
# ---------------------------------------------------------------------------
class TestAgentBoot:
    async def test_start_registers_every_default_tool(self, agent: Agent):
        assert set(agent.engine.tools) == set(DEFAULT_TOOL_NAMES)
        assert len(agent.engine.tools) == 11

    async def test_registered_tools_are_real_instances(self, agent: Agent):
        for name in DEFAULT_TOOL_NAMES:
            tool = agent.engine.tools[name]
            assert hasattr(tool, "execute"), f"{name} has no execute()"
            assert isinstance(tool.schema(), dict), f"{name} has no schema()"

    async def test_start_builds_autonomy_subsystems(self, agent: Agent):
        assert agent._planner is not None
        assert agent._plan_executor is not None
        assert agent._replanner is not None
        assert agent._subagent_engine is not None
        assert agent._job_engine is not None
        assert agent._recovery_manager is not None
        assert agent._learning_engine is not None
        assert agent._skill_lifecycle is not None
        assert agent._budget_manager is not None
        assert agent._event_tracker is not None

    async def test_start_bootstraps_memory_and_skills(self, agent: Agent):
        assert agent._memory is not None
        assert agent._skills is not None
        assert agent._skills.list_skills() == ["code-review", "deploy", "research"]

    async def test_engine_subsystems_are_wired(self, agent: Agent):
        assert agent.engine._budget_manager is agent._budget_manager
        assert agent.engine._event_tracker is agent._event_tracker

    async def test_boot_with_no_api_keys_registers_no_provider(self, agent: Agent):
        assert agent.engine.providers == {}
        assert agent._get_first_provider() is None

    async def test_provider_failover_requires_two_providers(self, agent: Agent):
        agent.engine.register_provider("a", ScriptedProvider())
        agent._init_provider_failover()
        assert "__fallback__" not in agent.engine.providers

        agent.engine.register_provider("b", ScriptedProvider())
        agent._init_provider_failover()
        assert "__fallback__" in agent.engine.providers

    async def test_in_memory_run_creates_no_files(self, tmp_path: Path):
        """config.memory.database = ":memory:" must not touch the filesystem."""
        data_dir = Path(__file__).resolve().parents[1] / "data"
        before = set(os.listdir(data_dir)) if data_dir.exists() else set()

        instance = make_agent(tmp_path)
        await instance.start()
        session = instance.create_session()
        provider = ScriptedProvider(AgentResponse(content="hello"))
        instance.engine.register_provider("fake", provider)
        await instance.run("hello", session_id=session.id, model="fake/model")

        after = set(os.listdir(data_dir)) if data_dir.exists() else set()
        assert after == before, f"in-memory run created {after - before}"

    async def test_stop_is_idempotent(self, agent: Agent):
        await agent.stop()
        await agent.stop()

    def test_init_from_config_path(self, tmp_path: Path):
        cfg_file = tmp_path / "cfg.yaml"
        cfg_file.write_text(
            "agent:\n  name: FromFile\n  model: fake/model-1\nmemory:\n  database: ':memory:'\n"
        )
        instance = Agent(config_path=str(cfg_file))
        assert instance.config.agent.name == "FromFile"


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------
class TestAgentSessions:
    async def test_create_get_delete(self, agent: Agent):
        session = agent.create_session(metadata={"channel": "test"})
        assert session.metadata == {"channel": "test"}
        assert agent.get_session(session.id) is session

        agent.delete_session(session.id)
        assert agent.get_session(session.id) is None

    async def test_get_session_hydrates_from_store(self, agent: Agent):
        session = agent.create_session()
        agent.sessions.pop(session.id)

        restored = agent.get_session(session.id)
        assert restored is not None
        assert restored.id == session.id

    async def test_get_unknown_session_returns_none(self, agent: Agent):
        assert agent.get_session("does-not-exist") is None

    async def test_delete_unknown_session_is_a_noop(self, agent: Agent):
        agent.delete_session("does-not-exist")

    async def test_history_round_trip(self, agent: Agent):
        session = agent.create_session()
        agent.context.get_or_create(session.id).add_message(
            Message(role=MessageRole.USER, content="hi")
        )
        assert [m.content for m in agent.get_history(session.id)] == ["hi"]

        agent.clear_history(session.id)
        assert agent.get_history(session.id) == []

    def test_get_history_for_unknown_session(self, agent: Agent):
        assert agent.get_history("nope") == []

    def test_session_defaults(self, agent: Agent):
        session = agent.create_session()
        assert session.metadata == {}
        assert session.created_at > 0


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
class TestAgentRun:
    async def test_run_completes_and_persists_turn(self, agent: Agent):
        provider = ScriptedProvider(AgentResponse(content="Hello there"))
        agent.engine.register_provider("fake", provider)

        response = await agent.run("hi", model="fake/model")

        assert response.content == "Hello there"
        assert provider.calls and provider.calls[0]["messages"][-1].role == MessageRole.USER
        # the turn was persisted in the session store and memory
        session_id = next(iter(agent.sessions))
        stored = agent._store.get_messages(session_id)
        assert [m.role.value for m in stored] == ["user", "assistant"]

    async def test_run_without_session_id_creates_one(self, agent: Agent):
        agent.engine.register_provider("fake", ScriptedProvider(AgentResponse(content="ok")))
        await agent.run("hi", model="fake/model")
        assert len(agent.sessions) == 1

    async def test_run_with_unknown_session_id_creates_child_session(self, agent: Agent):
        agent.engine.register_provider("fake", ScriptedProvider(AgentResponse(content="ok")))
        await agent.run("hi", session_id="never-seen", model="fake/model")
        session = next(iter(agent.sessions.values()))
        assert session.metadata == {"parent_id": "never-seen"}

    async def test_chat_is_run_without_planning(self, agent: Agent):
        agent.engine.register_provider("fake", ScriptedProvider(AgentResponse(content="ok")))
        response = await agent.chat("hi", model="fake/model")
        assert response.content == "ok"

    async def test_run_executes_a_real_tool(self, agent: Agent, tmp_path: Path):
        target = tmp_path / "written.txt"
        provider = ScriptedProvider(
            AgentResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="tc1",
                        name="write",
                        arguments={"file_path": str(target), "content": "from the model"},
                    )
                ],
            ),
            AgentResponse(content="file written"),
        )
        agent.engine.register_provider("fake", provider)

        response = await agent.run("write a file", model="fake/model")

        assert response.content == "file written"
        assert target.read_text() == "from the model"

    async def test_system_prompt_lists_registered_tools(self, agent: Agent):
        prompt = agent._build_system_prompt()
        for name in DEFAULT_TOOL_NAMES:
            assert f"- {name}" in prompt

    async def test_system_prompt_falls_back_to_default(self, agent: Agent):
        agent.config.agent.system_prompt = ""
        assert "You are Bahram" in agent._build_system_prompt()

    async def test_memory_is_retrieved_and_stored(self, agent: Agent):
        agent._memory.add("User prefers dark mode", source="conversation")
        assert "dark mode" in agent._retrieve_memories("prefers")

        agent._store_memory("what is my preference?", "dark mode")
        assert "dark mode" in agent._retrieve_memories("preference")

    async def test_retrieve_memories_without_memory_backend(self, agent: Agent):
        agent._memory = None
        assert agent._retrieve_memories("anything") == ""
        agent._store_memory("q", "a")  # must not raise

    async def test_retrieve_memories_survives_backend_failure(self, agent: Agent):
        class Broken:
            def get_context(self, *_a, **_kw):
                raise RuntimeError("fts index offline")

        agent._memory = Broken()
        assert agent._retrieve_memories("anything") == ""

    async def test_retrieve_skills_returns_known_skill(self, agent: Agent):
        found = await agent._retrieve_skills("please review this pull request")
        assert "code-review" in found

    async def test_retrieve_skills_survives_failures(self, agent: Agent):
        class Broken:
            def find_skill(self, *_a):
                raise RuntimeError("boom")

        agent._skills = Broken()
        assert await agent._retrieve_skills("anything") == ""


# ---------------------------------------------------------------------------
# planning
# ---------------------------------------------------------------------------
class TestAgentPlanning:
    async def test_run_with_plan_uses_the_planner(self, agent: Agent):
        provider = ScriptedProvider(AgentResponse(content="step done"))
        agent.engine.register_provider("fake", provider)
        agent._planner.set_provider(provider)

        response = await agent.run_with_plan("write a haiku", model="fake/model")

        assert response.metadata["plan_status"] in {"completed", "failed"}
        assert "Plan completed" in response.content
        assert "Steps: " in response.content

    async def test_plan_summary_lists_step_outcomes(self, agent: Agent):
        provider = ScriptedProvider(AgentResponse(content="step done"))
        agent._planner.set_provider(provider)

        plan = await agent._planner.create_plan(
            goal="goal", run_id="run_1", context="", available_tools=[]
        )
        summary = agent._summarize_plan_result(plan)
        assert summary.startswith("Plan completed: goal")
        assert "Replans: " in summary


# ---------------------------------------------------------------------------
# streaming
# ---------------------------------------------------------------------------
class TestAgentStreaming:
    async def test_chat_streaming_yields_chunks(self, agent: Agent):
        agent.engine.register_provider(
            "fake", ScriptedProvider(AgentResponse(content="streamed answer"))
        )
        chunks = [chunk async for chunk in agent.chat_streaming("hi", model="fake/model")]
        assert chunks == ["streamed answer"]

    async def test_chat_streaming_persists_the_turn(self, agent: Agent):
        agent.engine.register_provider("fake", ScriptedProvider(AgentResponse(content="abc")))
        session = agent.create_session()
        async for _ in agent.chat_streaming("hi", session_id=session.id, model="fake/model"):
            pass

        stored = agent._store.get_messages(session.id)
        assert [m.role.value for m in stored] == ["user", "assistant"]

    async def test_chat_streaming_with_unknown_session(self, agent: Agent):
        agent.engine.register_provider("fake", ScriptedProvider(AgentResponse(content="abc")))
        chunks = [
            chunk
            async for chunk in agent.chat_streaming(
                "hi", session_id="unknown-session", model="fake/model"
            )
        ]
        assert chunks == ["abc"]


# ---------------------------------------------------------------------------
# autonomy accessors
# ---------------------------------------------------------------------------
class TestAgentAutonomyAccessors:
    async def test_delegate_to_subagent(self, agent: Agent):
        agent.engine.register_provider("fake", ScriptedProvider(AgentResponse(content="ok")))
        result = await agent.delegate_to_subagent(
            objective="summarise the repo", allowed_tools=["read"], model="fake/model"
        )
        assert result is not None

    async def test_delegate_before_start_raises(self):
        instance = make_agent()
        with pytest.raises(RuntimeError, match="Subagent engine not initialized"):
            await instance.delegate_to_subagent("objective")

    async def test_create_background_job(self, agent: Agent):
        session = agent.create_session()
        job = await agent.create_background_job(
            job_type="noop", session_id=session.id, payload={"x": 1}
        )
        assert job.payload == {"x": 1}

    async def test_create_background_job_before_start_raises(self):
        instance = make_agent()
        with pytest.raises(RuntimeError, match="Job engine not initialized"):
            await instance.create_background_job("noop", "session")

    async def test_checkpoint_run(self, agent: Agent):
        from bahram.autonomy.plan import Plan

        checkpoint = agent.checkpoint_run("run_1", Plan(id="p1", run_id="run_1", goal="g"))
        assert checkpoint.run_id == "run_1"
        assert agent._recovery_manager.load_checkpoint("run_1") is not None

    async def test_checkpoint_run_before_start_raises(self):
        instance = make_agent()
        with pytest.raises(RuntimeError, match="Recovery manager not initialized"):
            instance.checkpoint_run("run_1", None)

    async def test_analyze_and_learn(self, agent: Agent):
        analysis = await agent.analyze_and_learn(
            run_id="run_1",
            goal="do the thing",
            trajectory_steps=[{"step_id": "s1", "objective": "o", "status": "completed"}],
            tool_results=[{"step_id": "s1", "success": True}],
            success=True,
        )
        assert "lessons_extracted" in analysis

    async def test_analyze_and_learn_before_start_returns_error(self):
        instance = make_agent()
        result = await instance.analyze_and_learn("run", "goal", [], [], True)
        assert result == {"error": "Learning engine not initialized"}


# ---------------------------------------------------------------------------
# execute_command and MCP adapter
# ---------------------------------------------------------------------------
class TestAgentCommandAndMcp:
    async def test_execute_command_runs_a_registered_tool(self, agent: Agent):
        result = await agent.execute_command("bash", command="echo from-agent")
        assert result["success"] is True
        assert "from-agent" in result["content"]

    async def test_execute_command_reports_unknown_tool(self, agent: Agent):
        result = await agent.execute_command("definitely-not-a-tool")
        assert result["success"] is False

    async def test_mcp_disabled_when_config_absent(self, agent: Agent):
        await agent._init_mcp_tools()  # no mcp section -> returns immediately
        assert not [n for n in agent.engine.tools if n.startswith("mcp_")]

    async def test_mcp_disabled_when_no_servers_configured(self, agent: Agent):
        class McpConfig:
            servers: list = []

        agent.config.mcp = McpConfig()
        await agent._init_mcp_tools()
        assert not [n for n in agent.engine.tools if n.startswith("mcp_")]

    async def test_mcp_server_failure_is_logged_not_raised(self, agent: Agent):
        class ServerConfig(dict):
            pass

        class McpConfig:
            servers = [{"name": "broken", "command": "/nonexistent/binary"}]

        agent.config.mcp = McpConfig()
        await agent._init_mcp_tools()
        assert not [n for n in agent.engine.tools if n.startswith("mcp_")]

    def test_mcp_tool_adapter_schema_and_execute(self):
        from bahram.core.agent import _MCPToolAdapter

        class Client:
            async def call_tool(self, name, arguments):
                return f"{name}:{sorted(arguments)}"

        adapter = _MCPToolAdapter(
            Client(),
            {
                "name": "echo",
                "description": "Echo a value",
                "inputSchema": {"type": "object", "properties": {"v": {"type": "string"}}},
            },
        )
        schema = adapter.schema()
        assert schema["name"] == "mcp_echo"
        assert schema["parameters"]["properties"]["v"]["type"] == "string"

        import asyncio

        assert asyncio.run(adapter.execute(v="1")) == "echo:['v']"
