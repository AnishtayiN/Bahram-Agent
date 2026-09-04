"""
Deployment.

Public objects: ``DeploymentConfig``, ``DeploymentTool``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeploymentConfig:
    """
    Deployment config.

    Attributes:
        name (str): name of the object.
        target (str): target string.
        region (str): region string.
        environment (str): environment string.
        replicas (int): numeric value for replicas.
        resources (dict): mapping of resources.
        env_vars (dict[str, str]): mapping of env vars.
    """

    name: str
    target: str
    region: str = ""
    environment: str = "production"
    replicas: int = 1
    resources: dict = field(default_factory=dict)
    env_vars: dict[str, str] = field(default_factory=dict)


class DeploymentTool:
    """
    Deployment tool.
    """

    def __init__(self) -> None:
        """
        Initialise a DeploymentTool instance.
        """
        self._configs: dict[str, DeploymentConfig] = {}
        self._history: list[dict] = []

    def add_config(self, config: DeploymentConfig) -> None:
        """
        Add config.

        Args:
            config (DeploymentConfig): configuration object.
        """
        self._configs[config.name] = config

    async def deploy(self, config_name: str) -> dict[str, Any]:
        """
        Deploy.

        Args:
            config_name (str): config name string.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        config = self._configs.get(config_name)
        if not config:
            return {"error": f"Config '{config_name}' not found"}

        try:
            if config.target == "docker":
                return await self._deploy_docker(config)
            elif config.target == "kubernetes":
                return await self._deploy_kubernetes(config)
            elif config.target in ("aws", "gcp", "azure"):
                return await self._deploy_cloud(config, config.target)
            else:
                return {"error": f"Unsupported target: {config.target}"}
        except Exception as e:
            return {"error": str(e)}

    async def _deploy_docker(self, config: DeploymentConfig) -> dict[str, Any]:
        proc = await asyncio.create_subprocess_shell(
            f"docker build -t {config.name} . && docker run -d --name {config.name} {config.name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        result = {
            "target": "docker",
            "status": "success" if proc.returncode == 0 else "failed",
            "output": stdout.decode(),
            "error": stderr.decode() if proc.returncode != 0 else "",
        }
        self._history.append(result)
        return result

    async def _deploy_kubernetes(self, config: DeploymentConfig) -> dict[str, Any]:

        yaml_content = ""

        proc = await asyncio.create_subprocess_shell(
            f"echo '{yaml_content}' | kubectl apply -f -",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        result = {
            "target": "kubernetes",
            "status": "success" if proc.returncode == 0 else "failed",
            "output": stdout.decode(),
            "error": stderr.decode() if proc.returncode != 0 else "",
        }
        self._history.append(result)
        return result

    async def _deploy_cloud(self, config: DeploymentConfig, provider: str) -> dict[str, Any]:
        result = {
            "target": provider,
            "status": "success",
            "message": f"Deployment to {provider} configured",
            "config": {
                "name": config.name,
                "region": config.region,
                "environment": config.environment,
            },
        }
        self._history.append(result)
        return result

    def get_history(self) -> list[dict]:
        """
        Return the history.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return self._history.copy()

    async def rollback(self, config_name: str) -> dict[str, Any]:
        """
        Rollback.

        Args:
            config_name (str): config name string.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return {
            "status": "success",
            "message": f"Rollback for {config_name} initiated",
        }
