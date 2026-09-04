from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from bahram.core.config import Config
from bahram.core.context import Context, ContextWindow
from bahram.core.engine import AgentResponse, AgentEngine, Message, MessageRole, ToolCall
from bahram.core.persistence import SessionStore
from bahram.core.smart_context import SmartContextManager
from bahram.core.compressor import ContextCompressor

logger = logging.getLogger(__name__)


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent:
    def __init__(self, config: Config | None = None, config_path: str | None = None) -> None:
        if config:
            self.config = config
        elif config_path:
            self.config = Config.from_file(config_path)
        else:
            self.config = Config.from_file("config/config.yaml")

        self.engine = AgentEngine(self.config)
        self.context = Context(max_turns=self.config.memory.max_context_turns)
        max_ctx_tokens = getattr(self.config.memory, 'max_context_tokens', 8192)
        self.smart_context = SmartContextManager(max_tokens=max_ctx_tokens)
        self.compressor = ContextCompressor()
        self.sessions: dict[str, Session] = {}
        _memory_db = self.config.memory.database
        _session_db = (
            ":memory:" if _memory_db == ":memory:" else _memory_db.replace("memory.db", "sessions.db")
        )
        self._store = SessionStore(db_path=_session_db)
        self._memory = None
        self._skills = None
        self._setup_logging()

        self._planner = None
        self._verification_engine = None
        self._replanner = None
        self._plan_executor = None
        self._subagent_engine = None
        self._job_engine = None
        self._recovery_manager = None
        self._learning_engine = None
        self._skill_lifecycle = None
        self._budget_manager = None
        self._event_tracker = None

        logger.info(f"Bahram Agent v{self.config.agent.version} initialized")

    def _setup_logging(self) -> None:
        log_config = self.config.logging
        logging.basicConfig(
            level=getattr(logging, log_config.level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    async def start(self) -> None:
        logger.info("Starting Bahram Agent...")
        await self._init_providers()
        await self._init_tools()
        await self._init_memory()
        await self._init_skills()
        self._init_autonomy()
        self._init_provider_failover()
        self._wire_engine_subsystems()
        await self._init_mcp_tools()
        logger.info("Bahram Agent started successfully")

    def _init_autonomy(self) -> None:
        from bahram.autonomy.planner import Planner
        from bahram.autonomy.verification import VerificationEngine
        from bahram.autonomy.replanner import Replanner
        from bahram.autonomy.executor import PlanExecutor
        from bahram.autonomy.subagent import SubagentEngine
        from bahram.autonomy.jobs import JobEngine
        from bahram.autonomy.recovery import RecoveryManager
        from bahram.autonomy.learning import LearningEngine
        from bahram.autonomy.skill_lifecycle import SkillLifecycle
        from bahram.autonomy.budget import BudgetManager
        from bahram.autonomy.events import EventTracker

        self._event_tracker = EventTracker()
        self._budget_manager = BudgetManager()
        self._verification_engine = VerificationEngine()
        self._recovery_manager = RecoveryManager()
        self._learning_engine = LearningEngine()
        self._skill_lifecycle = SkillLifecycle(self._learning_engine)

        self._planner = Planner()
        self._replanner = Replanner(
            self._planner, self._verification_engine, max_replan_attempts=3
        )
        self._plan_executor = PlanExecutor(
            engine=self.engine,
            planner=self._planner,
            verification_engine=self._verification_engine,
            replanner=self._replanner,
            budget_manager=self._budget_manager,
            event_tracker=self._event_tracker,
            recovery_manager=self._recovery_manager,
        )
        self._subagent_engine = SubagentEngine(self.engine, event_tracker=self._event_tracker)
        self._job_engine = JobEngine(event_tracker=self._event_tracker)

        self._planner.set_provider(self._get_first_provider())
        logger.info("Autonomy layer initialized")

    def _init_provider_failover(self) -> None:
        providers = list(self.engine.providers.values())
        if len(providers) >= 2:
            from bahram.providers.fallback import FallbackProvider
            primary = providers[0]
            fallbacks = providers[1:]
            fallback_provider = FallbackProvider(primary, fallbacks)
            self.engine.providers["__fallback__"] = fallback_provider
            logger.info(
                f"Provider failover configured: primary={primary.__class__.__name__}, "
                f"fallbacks={[f.__class__.__name__ for f in fallbacks]}"
            )

    def _wire_engine_subsystems(self) -> None:
        if self._budget_manager is not None:
            self.engine.set_budget_manager(self._budget_manager)
        if self._event_tracker is not None:
            self.engine.set_event_tracker(self._event_tracker)
        logger.info("Engine subsystems wired (budget, events, circuit breaker)")

    async def _init_mcp_tools(self) -> None:
        try:
            from bahram.mcp.client import MCPClient
            mcp_config = getattr(self.config, 'mcp', None)
            if mcp_config is None:
                return
            servers = getattr(mcp_config, 'servers', [])
            if not servers:
                return
            client = MCPClient()
            for server_cfg in servers:
                try:
                    await client.connect(server_cfg)
                    tools = await client.list_tools()
                    for tool_def in tools:
                        name = f"mcp_{tool_def.get('name', 'unknown')}"
                        self.engine.register_tool(name, _MCPToolAdapter(client, tool_def))
                    logger.info(f"Registered {len(tools)} MCP tools from {server_cfg.get('name', 'unknown')}")
                except Exception as e:
                    logger.warning(f"MCP server connection failed: {e}")
        except ImportError:
            logger.debug("MCP client not available, skipping MCP tool discovery")
        except Exception as e:
            logger.warning(f"MCP tool initialization failed: {e}")

    def _get_first_provider(self) -> Any:
        providers = list(self.engine.providers.values())
        return providers[0] if providers else None

    async def stop(self) -> None:
        logger.info("Stopping Bahram Agent...")
        logger.info("Bahram Agent stopped")

    async def _init_providers(self) -> None:
        from bahram.providers import init_providers
        await init_providers(self.engine, self.config)

    async def _init_tools(self) -> None:
        from bahram.tools import init_tools
        await init_tools(self.engine, self.config)

    async def _init_memory(self) -> None:
        if self.config.memory.enabled:
            from bahram.memory.semantic import SemanticMemory
            self._memory = SemanticMemory(data_dir=self.config.memory.database)

    async def _init_skills(self) -> None:
        if self.config.skills.enabled:
            from bahram.skills.manager import SkillManager
            self._skills = SkillManager(self.config.skills)
            await self._skills.load_skills()

    def create_session(self, metadata: dict[str, Any] | None = None) -> Session:
        session = Session(metadata=metadata or {})
        self.sessions[session.id] = session
        self.context.create(session.id)
        self._store.create_session(session.id, metadata=metadata)
        logger.info(f"Created session: {session.id}")
        return session

    def get_session(self, session_id: str) -> Session | None:
        if session_id in self.sessions:
            return self.sessions[session_id]
        stored = self._store.get_session(session_id)
        if stored:
            session = Session(id=session_id, created_at=stored["created_at"], updated_at=stored["updated_at"])
            self.sessions[session_id] = session
            return session
        return None

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.context.delete(session_id)
        self._store.delete_session(session_id)
        logger.info(f"Deleted session: {session_id}")

    async def run(
        self,
        message: str,
        session_id: str | None = None,
        model: str | None = None,
        use_planning: bool = False,
    ) -> AgentResponse:
        if session_id is None:
            session = self.create_session()
            session_id = session.id
        else:
            session = self.sessions.get(session_id)
            if session is None:
                session = self.create_session(metadata={"parent_id": session_id})

        ctx = self.context.get_or_create(session_id)
        if ctx.get_system_prompt() is None:
            ctx.set_system_prompt(self._build_system_prompt())

        self.smart_context.set_system_prompt(self._build_system_prompt())

        memories = self._retrieve_memories(message)
        skills_context = self._retrieve_skills(message)

        enhanced_message = message
        if memories:
            enhanced_message = f"[Relevant memories]\n{memories}\n\n{message}"
            self.smart_context.add_context(memories, priority=3, metadata={"source": "memory"})
        if skills_context:
            enhanced_message = f"[Relevant skills]\n{skills_context}\n\n{enhanced_message}"
            self.smart_context.add_context(skills_context, priority=2, metadata={"source": "skills"})

        user_msg = Message(role=MessageRole.USER, content=enhanced_message)
        ctx.add_message(user_msg)
        self._store.add_message(session_id, user_msg)
        self.smart_context.add_history("user", enhanced_message)

        self.smart_context.optimize()
        usage = self.smart_context.get_usage()
        if usage["remaining"] < 500:
            logger.warning(f"Smart context nearly full: {usage['remaining']} tokens remaining")
            if self._event_tracker is not None and hasattr(self._event_tracker, 'emit_budget_warning'):
                self._event_tracker.emit_budget_warning(
                    session_id, "", {"message": f"Context window low: {usage['remaining']} tokens"}
                )

        smart_messages = self.smart_context.build_messages()
        if smart_messages:
            messages = smart_messages
        else:
            messages = ctx.get_messages()

        if len(messages) > 20:
            try:
                msg_dicts = [{"role": m.role.value, "content": m.content} for m in messages]
                result = await self.compressor.compress(msg_dicts, target_tokens=4000)
                if result.compressed_tokens < result.original_tokens:
                    import json as _json
                    compressed = _json.loads(result.compressed)
                    messages = []
                    for md in compressed:
                        role = MessageRole(md.get("role", "user"))
                        messages.append(Message(role=role, content=md.get("content", "")))
                    logger.info(f"Context compressed: {result.original_tokens} -> {result.compressed_tokens} tokens")
            except Exception as e:
                logger.warning(f"Context compression failed: {e}")

        if use_planning and self._planner:
            run_id = f"run_{uuid.uuid4().hex[:8]}"
            plan = await self._planner.create_plan(
                goal=message,
                run_id=run_id,
                context=memories,
                available_tools=list(self.engine.tools.keys()),
            )

            plan = await self._plan_executor.execute_plan(
                plan, messages, model=model, session_id=session_id, run_id=run_id,
            )

            if self._learning_engine is not None:
                try:
                    success = plan.status.value == "completed"
                    trajectory_steps = [
                        {"step_id": s.step_id, "objective": s.objective, "status": s.status.value}
                        for s in plan.steps
                    ]
                    tool_results = [
                        {"step_id": s.step_id, "success": s.status.value == "completed"}
                        for s in plan.steps
                    ]
                    await self.analyze_and_learn(
                        run_id=run_id,
                        goal=plan.goal,
                        trajectory_steps=trajectory_steps,
                        tool_results=tool_results,
                        success=success,
                    )
                except Exception as e:
                    logger.warning(f"Auto-learning failed: {e}")

            summary = self._summarize_plan_result(plan)
            response = AgentResponse(
                content=summary,
                state=plan.status.value,
                metadata={"plan_id": plan.id, "plan_status": plan.status.value},
            )
        else:
            response = await self.engine.run(messages, model=model, session_id=session_id)

        assistant_msg = Message(
            role=MessageRole.ASSISTANT, content=response.content,
            metadata={"tool_calls": response.tool_calls} if response.tool_calls else {},
        )
        ctx.add_message(assistant_msg)
        self._store.add_message(session_id, assistant_msg)
        self.smart_context.add_history("assistant", response.content or "")
        session.updated_at = time.time()

        self._store_memory(message, response.content)

        return response

    async def chat(
        self, message: str, session_id: str | None = None, model: str | None = None,
    ) -> AgentResponse:
        return await self.run(message, session_id, model)

    async def run_with_plan(
        self,
        message: str,
        session_id: str | None = None,
        model: str | None = None,
    ) -> AgentResponse:
        return await self.run(message, session_id, model, use_planning=True)

    async def delegate_to_subagent(
        self,
        objective: str,
        parent_run_id: str = "",
        allowed_tools: list[str] | None = None,
        context: str = "",
        model: str | None = None,
    ) -> Any:
        if not self._subagent_engine:
            raise RuntimeError("Subagent engine not initialized")

        return await self._subagent_engine.spawn(
            parent_run_id=parent_run_id or f"run_{uuid.uuid4().hex[:8]}",
            objective=objective,
            allowed_tools=allowed_tools or [],
            context=context,
            model=model,
        )

    async def create_background_job(
        self,
        job_type: str,
        session_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        if not self._job_engine:
            raise RuntimeError("Job engine not initialized")

        return await self._job_engine.enqueue(
            job_type=job_type,
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            payload=payload,
        )

    async def analyze_and_learn(
        self,
        run_id: str,
        goal: str,
        trajectory_steps: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
        success: bool,
    ) -> dict[str, Any]:
        if not self._learning_engine:
            return {"error": "Learning engine not initialized"}

        analysis = await self._learning_engine.analyze_outcome(
            run_id=run_id,
            goal=goal,
            trajectory_steps=trajectory_steps,
            tool_results=tool_results,
            success=success,
        )

        lessons = analysis.get("lessons_extracted", [])
        if len(lessons) >= 2:
            skill = await self._skill_lifecycle.generate_from_lessons(lessons, goal)
            if skill:
                analysis["generated_skill"] = skill.to_dict()

        return analysis

    def checkpoint_run(self, run_id: str, plan: Any, context_summary: str = "") -> Any:
        if not self._recovery_manager:
            raise RuntimeError("Recovery manager not initialized")

        return self._recovery_manager.checkpoint(
            run_id=run_id, plan=plan, context_summary=context_summary,
        )

    def _summarize_plan_result(self, plan: Any) -> str:
        progress = plan.get_progress()
        completed = progress["completed"]
        total = progress["total"]

        lines = [
            f"Plan completed: {plan.goal}",
            f"Status: {plan.status.value}",
            f"Steps: {completed}/{total} completed",
            f"Replans: {plan.replan_count}",
        ]

        if plan.strategy:
            lines.append(f"Strategy: {plan.strategy}")

        for step in plan.get_completed_steps():
            lines.append(f"  ✓ {step.objective}")

        for step in plan.get_failed_steps():
            lines.append(f"  ✗ {step.objective}: {step.failure_reason}")

        return "\n".join(lines)

    async def chat_streaming(
        self, message: str, session_id: str | None = None, model: str | None = None,
    ) -> AsyncIterator[str]:
        if session_id is None:
            session = self.create_session()
            session_id = session.id
        else:
            session = self.sessions.get(session_id)
            if session is None:
                session = self.create_session(metadata={"parent_id": session_id})

        ctx = self.context.get_or_create(session_id)
        if ctx.get_system_prompt() is None:
            ctx.set_system_prompt(self._build_system_prompt())

        self.smart_context.set_system_prompt(self._build_system_prompt())

        memories = self._retrieve_memories(message)
        enhanced_message = message
        if memories:
            enhanced_message = f"[Relevant memories]\n{memories}\n\n{message}"
            self.smart_context.add_context(memories, priority=3, metadata={"source": "memory"})

        user_msg = Message(role=MessageRole.USER, content=enhanced_message)
        ctx.add_message(user_msg)
        self._store.add_message(session_id, user_msg)
        self.smart_context.add_history("user", enhanced_message)

        self.smart_context.optimize()
        smart_messages = self.smart_context.build_messages()
        messages = smart_messages if smart_messages else ctx.get_messages()

        full_response = ""

        async for chunk in self.engine.run_streaming(messages, model=model):
            full_response += chunk
            yield chunk

        assistant_msg = Message(role=MessageRole.ASSISTANT, content=full_response)
        ctx.add_message(assistant_msg)
        self._store.add_message(session_id, assistant_msg)
        self.smart_context.add_history("assistant", full_response)
        session.updated_at = time.time()

    def _build_system_prompt(self) -> str:
        base_prompt = self.config.agent.system_prompt
        if not base_prompt:
            base_prompt = (
                "You are Bahram, an advanced AI agent. You are helpful, capable, and autonomous. "
                "You can use tools to accomplish tasks. When given a goal, you reason about it, "
                "plan the steps, execute tools, observe results, and continue until the task is complete."
            )

        tools_info = "\n\nAvailable tools:\n"
        for tool_name in self.engine.tools.keys():
            desc = ""
            if hasattr(self.engine.tools[tool_name], "description"):
                desc = f" - {self.engine.tools[tool_name].description}"
            tools_info += f"- {tool_name}{desc}\n"

        return base_prompt + tools_info

    def _retrieve_memories(self, query: str) -> str:
        if self._memory is None:
            return ""
        try:
            return self._memory.get_context(query, max_memories=5)
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")
            return ""

    def _store_memory(self, query: str, response: str) -> None:
        if self._memory is None:
            return
        try:
            self._memory.add(f"User: {query}\nAssistant: {response}", source="conversation")
        except Exception as e:
            logger.warning(f"Memory storage failed: {e}")

    def _retrieve_skills(self, task: str) -> str:
        skill_descriptions = []

        if self._skills is not None:
            try:
                skill = self._skills.find_skill(task)
                if skill and hasattr(skill, "metadata"):
                    skill_descriptions.append(f"Skill '{skill.metadata.name}': {skill.metadata.description}")
            except Exception as e:
                logger.warning(f"Skill retrieval failed: {e}")

        if self._skill_lifecycle is not None:
            try:
                trusted = self._skill_lifecycle.get_trusted_skills()
                for ts in trusted[:3]:
                    if hasattr(ts, 'name') and hasattr(ts, 'instructions'):
                        skill_descriptions.append(f"Learned skill '{ts.name}': {ts.instructions[:200]}")
            except Exception as e:
                logger.warning(f"Skill lifecycle retrieval failed: {e}")

        return "\n".join(skill_descriptions) if skill_descriptions else ""

    def get_history(self, session_id: str) -> list[Message]:
        ctx = self.context.get(session_id)
        if ctx:
            return ctx.get_messages()
        return []

    def clear_history(self, session_id: str) -> None:
        self.context.clear(session_id)

    async def execute_command(self, command: str, **kwargs: Any) -> Any:
        logger.info(f"Executing command: {command}")
        if self.engine._tool_executor is None:
            from bahram.core.engine import ToolExecutor
            self.engine._tool_executor = ToolExecutor(self.engine.tools, self.engine._approval_system)
        tc = ToolCall(
            id=f"cmd_{int(time.time() * 1000)}", name=command, arguments=kwargs,
        )
        result = await self.engine._tool_executor.execute(tc)
        return {"content": result.content, "success": result.success, "error": result.error}


class _MCPToolAdapter:
    def __init__(self, client: Any, tool_def: dict) -> None:
        self._client = client
        self._tool_def = tool_def
        self.name = tool_def.get("name", "unknown")
        self.description = tool_def.get("description", "")

    def schema(self) -> dict:
        return {
            "name": f"mcp_{self.name}",
            "description": self.description,
            "parameters": self._tool_def.get("inputSchema", {"type": "object", "properties": {}}),
        }

    async def execute(self, **kwargs: Any) -> str:
        result = await self._client.call_tool(self.name, kwargs)
        return str(result)
