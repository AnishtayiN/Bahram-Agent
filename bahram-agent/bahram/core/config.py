"""
Config.

Public objects: ``ProviderConfig``, ``MemoryConfig``, ``SkillsConfig``, ``ToolsConfig``,
    ``PlatformConfig``, ``SchedulerConfig``, ``SecurityConfig``, ``LoggingConfig`` (+3 more).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProviderConfig:
    """
    Provider config.

    Attributes:
        api_key (str): api key string.
        base_url (str | None): base url string.
        models (list[str]): collection of models.
        temperature (float): numeric value for temperature.
        max_tokens (int): numeric value for max tokens.
    """

    api_key: str = ""
    base_url: str | None = None
    models: list[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class MemoryConfig:
    """
    Memory config.

    Attributes:
        enabled (bool): when ``True`` the object is active.
        database (str): database string.
        embedding_model (str): embedding model string.
        max_context_turns (int): numeric value for max context turns.
        auto_summarize (bool): when ``True``, enable auto summarize.
        summary_threshold (int): numeric value for summary threshold.
    """

    enabled: bool = True
    database: str = "data/memory.db"
    embedding_model: str = "all-MiniLM-L6-v2"
    max_context_turns: int = 20
    auto_summarize: bool = True
    summary_threshold: int = 50


@dataclass
class SkillsConfig:
    """
    Skills config.

    Attributes:
        enabled (bool): when ``True`` the object is active.
        directory (str): directory string.
        auto_create (bool): when ``True``, enable auto create.
        auto_improve (bool): when ``True``, enable auto improve.
    """

    enabled: bool = True
    directory: str = "skills"
    auto_create: bool = True
    auto_improve: bool = True


@dataclass
class ToolsConfig:
    """
    Tools config.

    Attributes:
        enabled (list[str]): when ``True`` the object is active.
        disabled (list[str]): collection of disabled.
        bash_timeout (int): numeric value for bash timeout.
        bash_sandbox (bool): when ``True``, enable bash sandbox.
        webfetch_timeout (int): numeric value for webfetch timeout.
        webfetch_max_size (int): numeric value for webfetch max size.
    """

    enabled: list[str] = field(
        default_factory=lambda: ["bash", "read", "write", "edit", "glob", "grep"]
    )
    disabled: list[str] = field(default_factory=list)
    bash_timeout: int = 120
    bash_sandbox: bool = False
    webfetch_timeout: int = 30
    webfetch_max_size: int = 1048576


@dataclass
class PlatformConfig:
    """
    Platform config.

    Attributes:
        enabled (bool): when ``True`` the object is active.
        token (str): token string.
        allowed_users (list[str]): collection of allowed users.
        guild_id (str): guild id string.
        app_token (str): app token string.
    """

    enabled: bool = False
    token: str = ""
    allowed_users: list[str] = field(default_factory=list)
    guild_id: str = ""
    app_token: str = ""


@dataclass
class SchedulerConfig:
    """
    Scheduler config.

    Attributes:
        enabled (bool): when ``True`` the object is active.
        max_concurrent (int): numeric value for max concurrent.
        check_interval (int): numeric value for check interval.
    """

    enabled: bool = True
    max_concurrent: int = 5
    check_interval: int = 60


@dataclass
class SecurityConfig:
    """
    Security config.

    Attributes:
        sandbox_mode (bool): when ``True``, enable sandbox mode.
        allowed_commands (list[str]): collection of allowed commands.
        blocked_commands (list[str]): collection of blocked commands.
        require_approval (list[str]): collection of require approval.
    """

    sandbox_mode: bool = False
    allowed_commands: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    require_approval: list[str] = field(default_factory=lambda: ["bash", "write", "edit"])


@dataclass
class LoggingConfig:
    """
    Logging config.

    Attributes:
        level (str): level string.
        file (str): file string.
        max_size (str): max size string.
        backup_count (int): numeric value for backup count.
    """

    level: str = "INFO"
    file: str = "logs/bahram.log"
    max_size: str = "10MB"
    backup_count: int = 5


@dataclass
class ServerConfig:
    """
    Server config.

    Attributes:
        enabled (bool): when ``True`` the object is active.
        host (str): host string.
        port (int): numeric value for port.
        auth_token (str): auth token string.
    """

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    auth_token: str = ""


@dataclass
class AgentConfig:
    """
    Agent config.

    Attributes:
        name (str): name of the object.
        version (str): version string.
        description (str): human readable description.
        model (str): model identifier in ``provider/model`` form.
        small_model (str): small model string.
        system_prompt (str): system prompt string.
        max_iterations (int): numeric value for max iterations.
        max_runtime_seconds (float): numeric value for max runtime seconds.
        max_tool_calls (int): numeric value for max tool calls.
        max_retries (int): numeric value for max retries.
    """

    name: str = "Bahram"
    version: str = "1.0.0"
    description: str = "Advanced self-improving AI agent"
    model: str = "anthropic/claude-sonnet-4-20250514"
    small_model: str = "anthropic/claude-haiku-3.5"
    system_prompt: str = ""
    max_iterations: int = 15
    max_runtime_seconds: float = 300.0
    max_tool_calls: int = 50
    max_retries: int = 3


@dataclass
class Config:
    """
    Config.

    Attributes:
        agent (AgentConfig): agent.
        providers (dict[str, ProviderConfig]): mapping of providers.
        memory (MemoryConfig): memory.
        skills (SkillsConfig): skills.
        tools (ToolsConfig): tools.
        platforms (dict[str, PlatformConfig]): mapping of platforms.
        scheduler (SchedulerConfig): scheduler.
        security (SecurityConfig): security.
        logging (LoggingConfig): logging.
        server (ServerConfig): server.
    """

    agent: AgentConfig = field(default_factory=AgentConfig)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    platforms: dict[str, PlatformConfig] = field(default_factory=dict)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    @classmethod
    def from_file(cls, path: str | Path) -> Config:
        """
        Build an instance from file.

        Args:
            path (str | Path): filesystem path to operate on.

        Returns:
            Config: the resulting Config.
        """
        path = Path(path)
        if not path.exists():
            return cls()

        try:
            import yaml

            with open(path) as f:
                data = yaml.safe_load(f)
        except ImportError:
            import json

            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
            return cls()

        data = cls._expand_env_vars(data)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Config:
        config = cls()

        if "agent" in data:
            config.agent = AgentConfig(**data["agent"])

        if "providers" in data:
            for name, provider_data in data["providers"].items():
                config.providers[name] = ProviderConfig(**provider_data)

        if "memory" in data:
            config.memory = MemoryConfig(**data["memory"])

        if "skills" in data:
            config.skills = SkillsConfig(**data["skills"])

        if "tools" in data:
            config.tools = ToolsConfig(**data["tools"])

        if "platforms" in data:
            for name, platform_data in data["platforms"].items():
                config.platforms[name] = PlatformConfig(**platform_data)

        if "scheduler" in data:
            config.scheduler = SchedulerConfig(**data["scheduler"])

        if "security" in data:
            config.security = SecurityConfig(**data["security"])

        if "logging" in data:
            config.logging = LoggingConfig(**data["logging"])

        if "server" in data:
            config.server = ServerConfig(**data["server"])

        return config

    @classmethod
    def _expand_env_vars(cls, obj: Any) -> Any:
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                return os.environ.get(var_name, "")
            return obj
        elif isinstance(obj, dict):
            return {k: cls._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls._expand_env_vars(item) for item in obj]
        return obj

    def get_provider(self, name: str) -> ProviderConfig:
        """
        Return the provider.

        Args:
            name (str): name of the object.

        Returns:
            ProviderConfig: the resulting ProviderConfig.

        Raises:
            ValueError: if the operation cannot be completed.
        """
        if name not in self.providers:
            raise ValueError(f"Provider '{name}' not configured")
        return self.providers[name]

    def get_model_provider(self, model: str) -> tuple[str, ProviderConfig]:
        """
        Return the model provider.

        Args:
            model (str): model identifier in ``provider/model`` form.

        Returns:
            tuple[str, ProviderConfig]: a sequence of str, ProviderConfig entries (empty when there
                is nothing to report).
        """
        provider_name = model.split("/")[0] if "/" in model else "anthropic"
        return provider_name, self.get_provider(provider_name)
