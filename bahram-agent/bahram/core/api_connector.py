"""Intelligent API Connector for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """API configuration."""

    name: str
    base_url: str
    auth_type: str = "bearer"  # bearer, api_key, basic, oauth
    auth_value: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0


class APIConnector:
    """Intelligent API connector with auto-discovery."""

    def __init__(self) -> None:
        self._apis: dict[str, APIConfig] = {}
        self._cache: dict[str, Any] = {}

    def register_api(self, config: APIConfig) -> None:
        """Register an API."""
        self._apis[config.name] = config

    async def request(
        self,
        api_name: str,
        method: str,
        path: str,
        data: dict = None,
        params: dict = None,
        use_cache: bool = False,
    ) -> dict[str, Any]:
        """Make an API request."""
        config = self._apis.get(api_name)
        if not config:
            return {"error": f"API '{api_name}' not found"}

        # Check cache
        cache_key = f"{api_name}:{method}:{path}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            import httpx

            url = f"{config.base_url.rstrip('/')}/{path.lstrip('/')}"
            headers = config.headers.copy()

            # Add authentication
            if config.auth_type == "bearer":
                headers["Authorization"] = f"Bearer {config.auth_value}"
            elif config.auth_type == "api_key":
                headers["X-API-Key"] = config.auth_value
            elif config.auth_type == "basic":
                import base64
                auth = base64.b64encode(config.auth_value.encode()).decode()
                headers["Authorization"] = f"Basic {auth}"

            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params,
                    timeout=config.timeout,
                )

                result = {
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                }

                # Cache successful responses
                if use_cache and response.status_code == 200:
                    self._cache[cache_key] = result

                return result

        except ImportError:
            return {"error": "httpx not installed"}
        except Exception as e:
            return {"error": str(e)}

    async def get(self, api_name: str, path: str, **kwargs) -> dict:
        """GET request."""
        return await self.request(api_name, "GET", path, **kwargs)

    async def post(self, api_name: str, path: str, data: dict = None, **kwargs) -> dict:
        """POST request."""
        return await self.request(api_name, "POST", path, data=data, **kwargs)

    async def put(self, api_name: str, path: str, data: dict = None, **kwargs) -> dict:
        """PUT request."""
        return await self.request(api_name, "PUT", path, data=data, **kwargs)

    async def delete(self, api_name: str, path: str, **kwargs) -> dict:
        """DELETE request."""
        return await self.request(api_name, "DELETE", path, **kwargs)

    def clear_cache(self) -> None:
        """Clear response cache."""
        self._cache.clear()

    def list_apis(self) -> list[dict]:
        """List registered APIs."""
        return [
            {
                "name": api.name,
                "base_url": api.base_url,
                "auth_type": api.auth_type,
            }
            for api in self._apis.values()
        ]
