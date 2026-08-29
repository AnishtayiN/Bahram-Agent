from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from bahram.core.config import Config
from bahram.core.context import Context, ContextWindow
from bahram.core.engine import AgentResponse, AgentEngine, Message, MessageRole, ToolCall

logger = logging.getLogger(__name__)

@dataclass
class Session:
    ""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

class Agent:
    ""

    def __init__(self, config: Optional[Config] = None, config_path: Optional[str] = None) -> None:
        ""
        if config:
            self.config = config
        elif config_path:
            self.config = Config.from_file(config_path)
        else:
            self.config = Config.from_file("config/config.yaml")

        self.engine = AgentEngine(self.config)
        self.context = Context(max_turns=self.config.memory.max_context_turns)
        self.sessions: dict[str, Session] = {}

        self._setup_logging()
        logger.info(f"Bahram Agent v{self.config.agent.version} initialized")

    def _setup_logging(self) -> None:
        ""
        log_config = self.config.logging
        logging.basicConfig(
            level=getattr(logging, log_config.level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    async def start(self) -> None:
        ""
        logger.info("Starting Bahram Agent...")

        await self._init_providers()

        await self._init_tools()

        await self._init_memory()

        await self._init_skills()

        logger.info("Bahram Agent started successfully")

    async def stop(self) -> None:
        ""
        logger.info("Stopping Bahram Agent...")

        logger.info("Bahram Agent stopped")

    async def _init_providers(self) -> None:
        ""
        from bahram.core.providers import init_providers

        await init_providers(self.engine, self.config)

    async def _init_tools(self) -> None:
        ""
        from bahram.tools import init_tools

        await init_tools(self.engine, self.config)

    async def _init_memory(self) -> None:
        ""
        if self.config.memory.enabled:
            from bahram.memory import init_memory

            await init_memory(self.config)

    async def _init_skills(self) -> None:
        ""
        if self.config.skills.enabled:
            from bahram.skills import init_skills

            await init_skills(self.engine, self.config)

    def create_session(self, metadata: Optional[dict[str, Any]] = None) -> Session:
        ""
        session = Session(metadata=metadata or {})
        self.sessions[session.id] = session
        self.context.create(session.id)
        logger.info(f"Created session: {session.id}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        ""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> None:
        ""
        self.sessions.pop(session_id, None)
        self.context.delete(session_id)
        logger.info(f"Deleted session: {session_id}")

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AgentResponse:
        ""

        if session_id is None:
            session = self.create_session()
            session_id = session.id
        else:
            session = self.sessions.get(session_id)
            if session is None:
                session = self.create_session(metadata={"parent_id": session_id})

        ctx = self.context.get_or_create(session_id)

        if ctx.get_system_prompt() is None:
            system_prompt = self._build_system_prompt()
            ctx.set_system_prompt(system_prompt)

        user_msg = Message(role=MessageRole.USER, content=message)
        ctx.add_message(user_msg)

        messages = ctx.get_messages()
        response = await self.engine.run(messages, model=model)

        assistant_msg = Message(
            role=MessageRole.ASSISTANT,
            content=response.content,
            metadata={"tool_calls": response.tool_calls} if response.tool_calls else {},
        )
        ctx.add_message(assistant_msg)

        session.updated_at = time.time()

        return response

    async def chat_streaming(
        self,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        ""

        if session_id is None:
            session = self.create_session()
            session_id = session.id
        else:
            session = self.sessions.get(session_id)
            if session is None:
                session = self.create_session(metadata={"parent_id": session_id})

        ctx = self.context.get_or_create(session_id)

        if ctx.get_system_prompt() is None:
            system_prompt = self._build_system_prompt()
            ctx.set_system_prompt(system_prompt)

        user_msg = Message(role=MessageRole.USER, content=message)
        ctx.add_message(user_msg)

        messages = ctx.get_messages()
        full_response = ""

        async for chunk in self.engine.run_streaming(messages, model=model):
            full_response += chunk
            yield chunk

        assistant_msg = Message(
            role=MessageRole.ASSISTANT,
            content=full_response,
        )
        ctx.add_message(assistant_msg)

        session.updated_at = time.time()

    def _build_system_prompt(self) -> str:
        ""
        base_prompt = self.config.agent.system_prompt
        if not base_prompt:
            base_prompt = f""

        tools_info = "\n\nAvailable tools:\n"
        for tool_name in self.engine.tools.keys():
            tools_info += f"- {tool_name}\n"

        return base_prompt + tools_info

    def get_history(self, session_id: str) -> list[Message]:
        ""
        ctx = self.context.get(session_id)
        if ctx:
            return ctx.get_messages()
        return []

    def clear_history(self, session_id: str) -> None:
        ""
        self.context.clear(session_id)

    async def execute_command(self, command: str, **kwargs: Any) -> Any:
        ""

        logger.info(f"Executing command: {command}")
        return await self.engine.execute_tool(
            ToolCall(
                id=f"cmd_{int(time.time() * 1000)}",
                name=command,
                arguments=kwargs,
            )
        )
