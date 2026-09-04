from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProviderConfig:

    api_key: str = ""
    base_url: str | None = None
    models: list[str] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096

@dataclass
class MemoryConfig:

    enabled: bool = True
    database: str = "data/memory.db"
    embedding_model: str = "all-MiniLM-L6-v2"
    max_context_turns: int = 20
    auto_summarize: bool = True
    summary_threshold: int = 50

@dataclass
class SkillsConfig:

    enabled: bool = True
    directory: str = "skills"
    auto_create: bool = True
    auto_improve: bool = True

@dataclass
class ToolsConfig:

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

    enabled: bool = False
    token: str = ""
    allowed_users: list[str] = field(default_factory=list)
    guild_id: str = ""
    app_token: str = ""

@dataclass
class SchedulerConfig:

    enabled: bool = True
    max_concurrent: int = 5
    check_interval: int = 60

@dataclass
class SecurityConfig:

    sandbox_mode: bool = False
    allowed_commands: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    require_approval: list[str] = field(default_factory=lambda: ["bash", "write", "edit"])

@dataclass
class LoggingConfig:

    level: str = "INFO"
    file: str = "logs/bahram.log"
    max_size: str = "10MB"
    backup_count: int = 5

@dataclass
class ServerConfig:

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    auth_token: str = ""

@dataclass
class AgentConfig:
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
        if name not in self.providers:
            raise ValueError(f"Provider '{name}' not configured")
        return self.providers[name]

    def get_model_provider(self, model: str) -> tuple[str, ProviderConfig]:
        provider_name = model.split("/")[0] if "/" in model else "anthropic"
        return provider_name, self.get_provider(provider_name)
