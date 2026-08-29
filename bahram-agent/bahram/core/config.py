"""Configuration management for Bahram Agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    api_key: str = ""
    base_url: Optional[str] = None
    models: list[str] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096


class MemoryConfig(BaseModel):
    """Memory system configuration."""

    enabled: bool = True
    database: str = "data/memory.db"
    embedding_model: str = "all-MiniLM-L6-v2"
    max_context_turns: int = 20
    auto_summarize: bool = True
    summary_threshold: int = 50


class SkillsConfig(BaseModel):
    """Skills system configuration."""

    enabled: bool = True
    directory: str = "skills"
    auto_create: bool = True
    auto_improve: bool = True
    hub_url: str = "https://skills.bahram-agent.dev"


class ToolsConfig(BaseModel):
    """Tools configuration."""

    enabled: list[str] = Field(
        default_factory=lambda: ["bash", "read", "write", "edit", "glob", "grep"]
    )
    disabled: list[str] = Field(default_factory=list)
    bash_timeout: int = 120
    bash_sandbox: bool = False
    webfetch_timeout: int = 30
    webfetch_max_size: int = 1048576


class PlatformConfig(BaseModel):
    """Platform integration configuration."""

    enabled: bool = False
    token: str = ""
    allowed_users: list[str] = Field(default_factory=list)
    guild_id: str = ""
    app_token: str = ""


class SchedulerConfig(BaseModel):
    """Scheduler configuration."""

    enabled: bool = True
    max_concurrent: int = 5
    check_interval: int = 60


class SecurityConfig(BaseModel):
    """Security configuration."""

    sandbox_mode: bool = False
    allowed_commands: list[str] = Field(default_factory=list)
    blocked_commands: list[str] = Field(default_factory=list)
    require_approval: list[str] = Field(default_factory=lambda: ["bash", "write", "edit"])


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    file: str = "logs/bahram.log"
    max_size: str = "10MB"
    backup_count: int = 5


class ServerConfig(BaseModel):
    """API server configuration."""

    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    auth_token: str = ""


class AgentConfig(BaseModel):
    """Agent configuration."""

    name: str = "Bahram"
    version: str = "1.0.0"
    description: str = "Advanced self-improving AI agent"
    model: str = "anthropic/claude-sonnet-4-6"
    small_model: str = "anthropic/claude-haiku-3.5"
    system_prompt: str = ""


class Config(BaseSettings):
    """Main configuration for Bahram Agent."""

    agent: AgentConfig = Field(default_factory=AgentConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    platforms: dict[str, PlatformConfig] = Field(default_factory=dict)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    model_config = {"env_prefix": "BAHRAM_", "env_file": ".env"}

    @classmethod
    def from_file(cls, path: str | Path) -> Config:
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f)

        # Expand environment variables
        data = cls._expand_env_vars(data)

        return cls(**data)

    @classmethod
    def _expand_env_vars(cls, obj: Any) -> Any:
        """Recursively expand environment variables in config."""
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
        """Get a provider configuration by name."""
        if name not in self.providers:
            raise ValueError(f"Provider '{name}' not configured")
        return self.providers[name]

    def get_model_provider(self, model: str) -> tuple[str, ProviderConfig]:
        """Get the provider for a given model."""
        provider_name = model.split("/")[0] if "/" in model else "anthropic"
        return provider_name, self.get_provider(provider_name)
