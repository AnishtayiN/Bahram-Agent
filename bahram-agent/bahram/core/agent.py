"""Main Agent class for Bahram."""

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
    """Represents a conversation session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent:
    """Main Bahram Agent class.

    This is the primary interface for interacting with Bahram.
    It manages sessions, context, and coordinates all agent operations.
    """

    def __init__(self, config: Optional[Config] = None, config_path: Optional[str] = None) -> None:
        """Initialize the agent.

        Args:
            config: Configuration object. If None, loads from config_path or default.
            config_path: Path to configuration file.
        """
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
        """Setup logging configuration."""
        log_config = self.config.logging
        logging.basicConfig(
            level=getattr(logging, log_config.level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    async def start(self) -> None:
        """Start the agent."""
        logger.info("Starting Bahram Agent...")

        # Initialize providers
        await self._init_providers()

        # Initialize tools
        await self._init_tools()

        # Initialize memory
        await self._init_memory()

        # Initialize skills
        await self._init_skills()

        logger.info("Bahram Agent started successfully")

    async def stop(self) -> None:
        """Stop the agent."""
        logger.info("Stopping Bahram Agent...")
        # Cleanup resources
        logger.info("Bahram Agent stopped")

    async def _init_providers(self) -> None:
        """Initialize LLM providers."""
        from bahram.core.providers import init_providers

        await init_providers(self.engine, self.config)

    async def _init_tools(self) -> None:
        """Initialize tools."""
        from bahram.tools import init_tools

        await init_tools(self.engine, self.config)

    async def _init_memory(self) -> None:
        """Initialize memory system."""
        if self.config.memory.enabled:
            from bahram.memory import init_memory

            await init_memory(self.config)

    async def _init_skills(self) -> None:
        """Initialize skills system."""
        if self.config.skills.enabled:
            from bahram.skills import init_skills

            await init_skills(self.engine, self.config)

    def create_session(self, metadata: Optional[dict[str, Any]] = None) -> Session:
        """Create a new session."""
        session = Session(metadata=metadata or {})
        self.sessions[session.id] = session
        self.context.create(session.id)
        logger.info(f"Created session: {session.id}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        self.sessions.pop(session_id, None)
        self.context.delete(session_id)
        logger.info(f"Deleted session: {session_id}")

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AgentResponse:
        """Send a message and get a response.

        Args:
            message: The user message.
            session_id: Session ID. If None, creates a new session.
            model: Model to use. If None, uses default.

        Returns:
            AgentResponse with the agent's response.
        """
        # Get or create session
        if session_id is None:
            session = self.create_session()
            session_id = session.id
        else:
            session = self.sessions.get(session_id)
            if session is None:
                session = self.create_session(metadata={"parent_id": session_id})

        # Get context
        ctx = self.context.get_or_create(session_id)

        # Set system prompt if not set
        if ctx.get_system_prompt() is None:
            system_prompt = self._build_system_prompt()
            ctx.set_system_prompt(system_prompt)

        # Add user message
        user_msg = Message(role=MessageRole.USER, content=message)
        ctx.add_message(user_msg)

        # Run agent
        messages = ctx.get_messages()
        response = await self.engine.run(messages, model=model)

        # Add assistant response to context
        assistant_msg = Message(
            role=MessageRole.ASSISTANT,
            content=response.content,
            metadata={"tool_calls": response.tool_calls} if response.tool_calls else {},
        )
        ctx.add_message(assistant_msg)

        # Update session timestamp
        session.updated_at = time.time()

        return response

    async def chat_streaming(
        self,
        message: str,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Send a message and stream the response.

        Args:
            message: The user message.
            session_id: Session ID. If None, creates a new session.
            model: Model to use. If None, uses default.

        Yields:
            Response chunks as they arrive.
        """
        # Get or create session
        if session_id is None:
            session = self.create_session()
            session_id = session.id
        else:
            session = self.sessions.get(session_id)
            if session is None:
                session = self.create_session(metadata={"parent_id": session_id})

        # Get context
        ctx = self.context.get_or_create(session_id)

        # Set system prompt if not set
        if ctx.get_system_prompt() is None:
            system_prompt = self._build_system_prompt()
            ctx.set_system_prompt(system_prompt)

        # Add user message
        user_msg = Message(role=MessageRole.USER, content=message)
        ctx.add_message(user_msg)

        # Run agent with streaming
        messages = ctx.get_messages()
        full_response = ""

        async for chunk in self.engine.run_streaming(messages, model=model):
            full_response += chunk
            yield chunk

        # Add assistant response to context
        assistant_msg = Message(
            role=MessageRole.ASSISTANT,
            content=full_response,
        )
        ctx.add_message(assistant_msg)

        # Update session timestamp
        session.updated_at = time.time()

    def _build_system_prompt(self) -> str:
        """Build the system prompt."""
        base_prompt = self.config.agent.system_prompt
        if not base_prompt:
            base_prompt = f"""You are {self.config.agent.name}, an advanced AI agent.
You are autonomous, reliable, and constantly learning.
Execute tasks with confidence and verify with care."""

        # Add tool information
        tools_info = "\n\nAvailable tools:\n"
        for tool_name in self.engine.tools.keys():
            tools_info += f"- {tool_name}\n"

        return base_prompt + tools_info

    def get_history(self, session_id: str) -> list[Message]:
        """Get conversation history for a session."""
        ctx = self.context.get(session_id)
        if ctx:
            return ctx.get_messages()
        return []

    def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        self.context.clear(session_id)

    async def execute_command(self, command: str, **kwargs: Any) -> Any:
        """Execute a custom command."""
        # This can be extended to support custom commands
        logger.info(f"Executing command: {command}")
        return await self.engine.execute_tool(
            ToolCall(
                id=f"cmd_{int(time.time() * 1000)}",
                name=command,
                arguments=kwargs,
            )
        )
