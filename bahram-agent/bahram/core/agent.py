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
        self.sessions: dict[str, Session] = {}
        self._store = SessionStore(db_path=self.config.memory.database.replace("memory.db", "sessions.db"))
        self._memory = None
        self._skills = None
        self._setup_logging()
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
        logger.info("Bahram Agent started successfully")

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
        self, message: str, session_id: str | None = None, model: str | None = None,
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

        memories = self._retrieve_memories(message)
        skills_context = self._retrieve_skills(message)

        enhanced_message = message
        if memories:
            enhanced_message = f"[Relevant memories]\n{memories}\n\n{message}"
        if skills_context:
            enhanced_message = f"[Relevant skills]\n{skills_context}\n\n{enhanced_message}"

        user_msg = Message(role=MessageRole.USER, content=enhanced_message)
        ctx.add_message(user_msg)
        self._store.add_message(session_id, user_msg)

        messages = ctx.get_messages()
        response = await self.engine.run(messages, model=model, session_id=session_id)

        assistant_msg = Message(
            role=MessageRole.ASSISTANT, content=response.content,
            metadata={"tool_calls": response.tool_calls} if response.tool_calls else {},
        )
        ctx.add_message(assistant_msg)
        self._store.add_message(session_id, assistant_msg)
        session.updated_at = time.time()

        self._store_memory(message, response.content)

        return response

    async def chat(
        self, message: str, session_id: str | None = None, model: str | None = None,
    ) -> AgentResponse:
        return await self.run(message, session_id, model)

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

        user_msg = Message(role=MessageRole.USER, content=message)
        ctx.add_message(user_msg)

        messages = ctx.get_messages()
        full_response = ""

        async for chunk in self.engine.run_streaming(messages, model=model):
            full_response += chunk
            yield chunk

        assistant_msg = Message(role=MessageRole.ASSISTANT, content=full_response)
        ctx.add_message(assistant_msg)
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
        if self._skills is None:
            return ""
        try:
            skill = self._skills.find_skill(task)
            if skill and hasattr(skill, "metadata"):
                return f"Skill '{skill.metadata.name}': {skill.metadata.description}"
        except Exception as e:
            logger.warning(f"Skill retrieval failed: {e}")
        return ""

    def get_history(self, session_id: str) -> list[Message]:
        ctx = self.context.get(session_id)
        if ctx:
            return ctx.get_messages()
        return []

    def clear_history(self, session_id: str) -> None:
        self.context.clear(session_id)

    async def execute_command(self, command: str, **kwargs: Any) -> Any:
        logger.info(f"Executing command: {command}")
        return await self.engine.execute_tool(ToolCall(
            id=f"cmd_{int(time.time() * 1000)}", name=command, arguments=kwargs,
        ))
