from __future__ import annotations

import asyncio
import os
import tempfile
import time
import uuid

import pytest

from bahram.autonomy.tool_gateway import ToolGateway, ToolRoute, ToolSearchResult
from bahram.core.context_architecture import ContextArchitecture, ContextCategory, ContextElement
from bahram.core.engine import AgentEngine, AgentResponse, Message, MessageRole, RunConfig, ToolCall
from bahram.core.observability import Observability, ObservabilityEvent
from bahram.memory.semantic import SemanticMemory
from bahram.security.kernel import AuthorizationRequest, Capability, SecurityKernel


class FakeTool:
    def __init__(self, name: str, desc: str = ""):
        self._name = name
        self._desc = desc
        self.description = desc

    def schema(self):
        return {"name": self._name, "description": self._desc, "parameters": {"type": "object", "properties": {}}}

    async def execute(self, **kwargs):
        return f"{self._name} done"


# ═══════════════════════════════════════════════════════════════
# TOOL GATEWAY TESTS
# ═══════════════════════════════════════════════════════════════

class TestToolGatewayRoutes:
    def test_initializes_routes_for_all_tools(self):
        tools = {
            "bash": FakeTool("bash", "Execute bash commands in shell"),
            "read": FakeTool("read", "Read file contents from disk"),
            "write": FakeTool("write", "Write file contents to disk"),
            "websearch": FakeTool("websearch", "Search the web for information"),
        }
        gw = ToolGateway(tools)
        assert len(gw._routes) == 4
        assert gw._routes["bash"].risk_level == "high"
        assert gw._routes["bash"].requires_approval is True
        assert gw._routes["read"].risk_level == "low"
        assert gw._routes["write"].risk_level == "medium"

    def test_search_tools_returns_relevant_results(self):
        tools = {
            "bash": FakeTool("bash", "Execute bash shell commands in terminal"),
            "read": FakeTool("read", "Read file contents from disk storage"),
            "write": FakeTool("write", "Write content to files on disk"),
            "git": FakeTool("git", "Git version control operations for repos"),
        }
        gw = ToolGateway(tools)
        results = gw.search_tools("execute bash command in shell")
        assert len(results) > 0
        assert results[0].tool_name == "bash"

    def test_filter_by_risk(self):
        tools = {
            "bash": FakeTool("bash", "Execute bash commands in shell"),
            "read": FakeTool("read", "Read file contents from disk"),
            "write": FakeTool("write", "Write file contents to disk"),
        }
        gw = ToolGateway(tools)
        low_risk = gw.filter_by_risk("low")
        assert "read" in low_risk
        assert "bash" not in low_risk
        medium_risk = gw.filter_by_risk("medium")
        assert "read" in medium_risk
        assert "write" in medium_risk

    def test_filter_by_capability(self):
        tools = {
            "bash": FakeTool("bash", "Execute bash commands in shell"),
            "read": FakeTool("read", "Read file contents from disk"),
        }
        gw = ToolGateway(tools)
        exec_tools = gw.filter_by_capability("execution")
        assert "bash" in exec_tools

    def test_get_route(self):
        tools = {"bash": FakeTool("bash", "Execute bash commands")}
        gw = ToolGateway(tools)
        route = gw.get_route("bash")
        assert route is not None
        assert route.tool_name == "bash"
        assert gw.get_route("nonexistent") is None

    def test_get_tools_for_context(self):
        tools = {
            "bash": FakeTool("bash", "Execute bash commands"),
            "read": FakeTool("read", "Read file contents"),
            "websearch": FakeTool("websearch", "Search the web"),
        }
        gw = ToolGateway(tools)
        result = gw.get_tools_for_context("list files in directory", allowed_risk="high")
        assert len(result) > 0


# ═══════════════════════════════════════════════════════════════
# SECURITY KERNEL TESTS
# ═══════════════════════════════════════════════════════════════

class TestSecurityKernel:
    def test_default_capabilities_granted(self):
        kernel = SecurityKernel()
        caps = kernel._capabilities.get("system", [])
        cap_names = {c.name for c in caps}
        assert "file_read" in cap_names
        assert "file_write" in cap_names
        assert "execute" in cap_names

    def test_authorization_granted_for_existing_capability(self):
        kernel = SecurityKernel()
        req = AuthorizationRequest(
            request_id="r1", identity="system", capability="file_read",
            resource="/tmp/test.txt", risk_level="low",
        )
        result = kernel.check_authorization(req)
        assert result.granted is True
        assert result.scope == "workspace"

    def test_authorization_denied_for_missing_capability(self):
        kernel = SecurityKernel()
        req = AuthorizationRequest(
            request_id="r2", identity="unknown_user", capability="file_read",
            resource="/tmp/test.txt", risk_level="low",
        )
        result = kernel.check_authorization(req)
        assert result.granted is False
        assert "no capability" in result.reason

    def test_authorization_denied_for_risk_exceeding_capability(self):
        kernel = SecurityKernel()
        kernel.grant_capability("limited_user", Capability(
            name="execute", scope="workspace", max_risk="low",
        ))
        req = AuthorizationRequest(
            request_id="r3", identity="limited_user", capability="execute",
            resource="rm -rf /", risk_level="critical",
        )
        result = kernel.check_authorization(req)
        assert result.granted is False

    def test_child_capability_enforcement(self):
        kernel = SecurityKernel()
        kernel.enforce_child_scope("parent_agent", "child_agent")
        parent_caps = {c.name for c in kernel._capabilities.get("parent_agent", [])}
        child_caps = {c.name for c in kernel._capabilities.get("child_agent", [])}
        assert child_caps.issubset(parent_caps)

    def test_one_time_capability(self):
        kernel = SecurityKernel()
        kernel.grant_capability("temp_user", Capability(
            name="single_use", scope="session", max_risk="low", one_time=True,
        ))
        req1 = AuthorizationRequest(
            request_id="r4", identity="temp_user", capability="single_use",
            resource="x", risk_level="low",
        )
        result1 = kernel.check_authorization(req1)
        assert result1.granted is True
        req2 = AuthorizationRequest(
            request_id="r5", identity="temp_user", capability="single_use",
            resource="x", risk_level="low",
        )
        result2 = kernel.check_authorization(req2)
        assert result2.granted is False

    def test_audit_log_records_denials(self):
        kernel = SecurityKernel()
        req = AuthorizationRequest(
            request_id="r6", identity="attacker", capability="admin",
            resource="/etc/shadow", risk_level="critical",
        )
        kernel.check_authorization(req)
        log = kernel.get_audit_log()
        assert len(log) >= 1
        assert log[-1]["capability"] == "admin"

    def test_revoke_capability(self):
        kernel = SecurityKernel()
        assert kernel.revoke_capability("system", "file_read") is True
        req = AuthorizationRequest(
            request_id="r7", identity="system", capability="file_read",
            resource="x", risk_level="low",
        )
        result = kernel.check_authorization(req)
        assert result.granted is False


# ═══════════════════════════════════════════════════════════════
# CONTEXT ARCHITECTURE TESTS
# ═══════════════════════════════════════════════════════════════

class TestContextArchitecture:
    def test_build_messages_preserves_order(self):
        ca = ContextArchitecture(max_tokens=1000)
        ca.add_stable("System identity", source="identity")
        ca.add_contextual("Project info", source="project", priority=5)
        ca.add_volatile("Current task", source="task", priority=10)
        msgs = ca.build_messages()
        assert len(msgs) == 3
        assert msgs[0]["content"] == "System identity"
        assert msgs[1]["content"] == "Project info"
        assert msgs[2]["content"] == "Current task"

    def test_optimize_removes_low_priority_volatile(self):
        ca = ContextArchitecture(max_tokens=50)
        ca.add_stable("sys", source="s")
        ca.add_volatile("x" * 200, source="low", priority=1)
        ca.add_volatile("y" * 200, source="high", priority=100)
        removed = ca.optimize()
        assert removed >= 1
        usage = ca.get_usage()
        assert usage["remaining"] >= 0

    def test_get_usage(self):
        ca = ContextArchitecture(max_tokens=1000)
        ca.add_stable("hello", source="test")
        usage = ca.get_usage()
        assert usage["stable_tokens"] > 0
        assert usage["max_tokens"] == 1000

    def test_get_trace(self):
        ca = ContextArchitecture(max_tokens=1000)
        ca.add_stable("test", source="test_source")
        ca.build_messages()
        trace = ca.get_trace()
        assert len(trace) >= 1
        assert trace[0]["source"] == "test_source"

    def test_clear_volatile(self):
        ca = ContextArchitecture(max_tokens=1000)
        ca.add_volatile("data", source="s")
        count = ca.clear_volatile()
        assert count == 1
        assert len(ca._volatile) == 0


# ═══════════════════════════════════════════════════════════════
# OBSERVABILITY TESTS
# ═══════════════════════════════════════════════════════════════

class TestObservability:
    def test_emit_creates_event(self, tmp_path):
        obs = Observability(data_dir=str(tmp_path / "obs"))
        event = obs.emit("test_event", session_id="s1", run_id="r1", key="value")
        assert event.event_type == "test_event"
        assert event.session_id == "s1"

    def test_persistence_to_jsonl(self, tmp_path):
        obs = Observability(data_dir=str(tmp_path / "obs"))
        obs.emit("event_a", session_id="s1")
        obs.emit("event_b", session_id="s1")
        assert os.path.exists(os.path.join(str(tmp_path / "obs"), "events.jsonl"))
        events = obs.query_events(session_id="s1")
        assert len(events) == 2

    def test_query_filters_by_type(self, tmp_path):
        obs = Observability(data_dir=str(tmp_path / "obs"))
        obs.emit("type_a", session_id="s1")
        obs.emit("type_b", session_id="s1")
        obs.emit("type_a", session_id="s1")
        results = obs.query_events(event_type="type_a")
        assert len(results) == 2

    def test_emit_run_created(self, tmp_path):
        obs = Observability(data_dir=str(tmp_path / "obs"))
        e = obs.emit_run_created("s1", "r1", model="test")
        assert e.event_type == "run_created"

    def test_emit_tool_completed(self, tmp_path):
        obs = Observability(data_dir=str(tmp_path / "obs"))
        e = obs.emit_tool_completed("s1", "r1", tool_call_id="tc1")
        assert e.event_type == "tool_completed"
        assert e.tool_call_id == "tc1"

    def test_get_event_types(self, tmp_path):
        obs = Observability(data_dir=str(tmp_path / "obs"))
        obs.emit("alpha")
        obs.emit("beta")
        obs.emit("alpha")
        types = obs.get_event_types()
        assert "alpha" in types
        assert "beta" in types

    def test_all_emit_helpers(self, tmp_path):
        obs = Observability(data_dir=str(tmp_path / "obs"))
        obs.emit_session_loaded("s1")
        obs.emit_memory_loaded("s1", "r1")
        obs.emit_context_built("s1", "r1")
        obs.emit_plan_created("s1", "r1", plan_id="p1")
        obs.emit_step_started("s1", "r1", step_id="st1")
        obs.emit_step_completed("s1", "r1", step_id="st1")
        obs.emit_step_failed("s1", "r1", step_id="st1")
        obs.emit_tool_selected("s1", "r1", tool_name="bash")
        obs.emit_tool_started("s1", "r1", tool_call_id="tc1")
        obs.emit_tool_failed("s1", "r1", tool_call_id="tc1")
        obs.emit_replanned("s1", "r1")
        obs.emit_subagent_spawned("s1", "r1", subagent_id="sa1")
        obs.emit_subagent_completed("s1", "r1", subagent_id="sa1")
        obs.emit_provider_failed("s1", "r1")
        obs.emit_provider_fallback("s1", "r1")
        obs.emit_circuit_opened("s1", "r1")
        obs.emit_circuit_closed("s1", "r1")
        obs.emit_budget_warning("s1", "r1")
        obs.emit_budget_exceeded("s1", "r1")
        obs.emit_context_compressed("s1", "r1")
        obs.emit_lesson_created("s1", "r1")
        obs.emit_skill_promoted("s1", "r1")
        obs.emit_run_completed("s1", "r1")
        obs.emit_approval_requested("s1", "r1")
        obs.emit_approval_granted("s1", "r1")
        assert len(obs._events) >= 25


# ═══════════════════════════════════════════════════════════════
# MEMORY 2.0 TESTS
# ═══════════════════════════════════════════════════════════════

class TestMemoryV2:
    def test_scope_isolation(self, tmp_path):
        m1 = SemanticMemory(data_dir=str(tmp_path / "m1"))
        m2 = SemanticMemory(data_dir=str(tmp_path / "m2"))
        m1.add("secret user A data", source="ua", scope="user_a")
        m2.add("secret user B data", source="ub", scope="user_b")
        results_a = m1.search("secret", scope="user_a")
        assert any("user A" in r.content for r in results_a)
        results_b = m1.search("secret", scope="user_b")
        assert not any("user B" in r.content for r in results_b)
        m1.close()
        m2.close()

    def test_consolidation_removes_old(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path / "mem"))
        mem.add("old data", source="test", confidence=0.05)
        removed = mem.consolidate(max_age_hours=0, min_confidence=0.1)
        assert removed >= 1
        mem.close()

    def test_decay_reduces_confidence(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path / "mem"))
        mem.add("decayable", source="test", confidence=1.0)
        mem.decay(decay_rate=0.5)
        row = mem._conn.execute("SELECT confidence FROM memories WHERE source='test'").fetchone()
        assert row[0] < 1.0
        mem.close()

    def test_user_profile_store_and_retrieve(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path / "mem"))
        mem.store_user_profile("user1", "style", "concise")
        profile = mem.get_user_profile("user1")
        all_content = " ".join(profile["preferences"] + profile["facts"])
        assert "concise" in all_content
        mem.close()

    def test_importance_and_confidence_stored(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path / "mem"))
        mid = mem.add("important", source="test", importance=0.9, confidence=0.8)
        row = mem.get(mid)
        assert row is not None
        mem.close()

    def test_search_with_scope_filter(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path / "mem"))
        mem.add("project data", source="p", scope="project")
        mem.add("global data", source="g", scope="global")
        results = mem.search("data", scope="project")
        assert all(r.scope == "project" for r in results)
        mem.close()

    def test_migration_adds_columns(self, tmp_path):
        import sqlite3
        db_path = str(tmp_path / "mem" / "memory.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT, source TEXT, timestamp REAL, metadata TEXT)")
        conn.commit()
        conn.close()
        mem = SemanticMemory(data_dir=str(tmp_path / "mem"))
        mem.add("test", source="s")
        cursor = mem._conn.execute("PRAGMA table_info(memories)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "scope" in columns
        assert "importance" in columns
        mem.close()


# ═══════════════════════════════════════════════════════════════
# ENGINE TRAJECTORY PERSISTENCE TESTS
# ═══════════════════════════════════════════════════════════════

class WorkingProvider:
    async def complete(self, messages, tools=None, **kwargs):
        return AgentResponse(content="done")
    async def stream(self, messages, tools=None, **kwargs):
        yield ""


class AlwaysFailProvider:
    async def complete(self, messages, tools=None, **kwargs):
        raise Exception("provider failed")
    async def stream(self, messages, tools=None, **kwargs):
        yield ""


class TestEngineTrajectory:
    @pytest.mark.asyncio
    async def test_trajectory_persisted_on_success(self, tmp_path):
        engine = AgentEngine()
        engine.providers["test"] = WorkingProvider()
        engine.set_trajectory_dir(str(tmp_path / "traj"))
        resp = await engine.run(
            [Message(role=MessageRole.USER, content="hello")],
            model="test/model", session_id="s1",
        )
        assert resp.state.value == "completed"
        assert "trajectory" in resp.metadata
        traj_files = os.listdir(str(tmp_path / "traj"))
        assert len(traj_files) == 1
        assert traj_files[0].endswith(".json")

    @pytest.mark.asyncio
    async def test_trajectory_persisted_on_failure(self, tmp_path):
        engine = AgentEngine()
        engine.providers["test"] = AlwaysFailProvider()
        engine.set_trajectory_dir(str(tmp_path / "traj"))
        resp = await engine.run(
            [Message(role=MessageRole.USER, content="hello")],
            model="test/model", session_id="s1",
        )
        assert resp.state.value == "failed"
        traj_files = os.listdir(str(tmp_path / "traj"))
        assert len(traj_files) == 1

    @pytest.mark.asyncio
    async def test_trajectory_persisted_on_cancel(self, tmp_path):
        engine = AgentEngine()

        class CancelAfterCall:
            def __init__(self):
                self.n = 0
            async def complete(self, messages, tools=None, **kwargs):
                self.n += 1
                if self.n == 1:
                    engine.cancel()
                    return AgentResponse(
                        content="",
                        tool_calls=[ToolCall(id="tc1", name="fast", arguments={})],
                    )
                return AgentResponse(content="x")
            async def stream(self, messages, tools=None, **kwargs):
                yield ""

        engine.providers["test"] = CancelAfterCall()
        engine.register_tool("fast", type("T", (), {
            "schema": lambda s: {"name": "fast", "description": "f", "parameters": {"type": "object", "properties": {}}},
            "execute": lambda s, **kw: "ok",
        })())
        engine.set_trajectory_dir(str(tmp_path / "traj"))
        resp = await engine.run(
            [Message(role=MessageRole.USER, content="hello")],
            model="test/model", session_id="s1",
        )
        assert resp.state.value == "cancelled"
        traj_files = os.listdir(str(tmp_path / "traj"))
        assert len(traj_files) == 1
