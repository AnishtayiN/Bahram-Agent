"""
API connector.

Public objects: ``APIConfig``, ``APIConnector``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """
    API config.

    Attributes:
        name (str): name of the object.
        base_url (str): base url string.
        auth_type (str): auth type string.
        auth_value (str): auth value string.
        headers (dict[str, str]): mapping of headers.
        timeout (float): timeout in seconds.
    """

    name: str
    base_url: str
    auth_type: str = "bearer"
    auth_value: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0


class APIConnector:
    """
    API connector.
    """

    def __init__(self) -> None:
        """
        Initialise a APIConnector instance.
        """
        self._apis: dict[str, APIConfig] = {}
        self._cache: dict[str, Any] = {}

    def register_api(self, config: APIConfig) -> None:
        """
        Register api.

        Args:
            config (APIConfig): configuration object.
        """
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
        """
        Request.

        Args:
            api_name (str): api name string.
            method (str): method string.
            path (str): filesystem path to operate on.
            data (dict): mapping of data. Defaults to ``None``.
            params (dict): mapping of params. Defaults to ``None``.
            use_cache (bool): when ``True``, enable use cache. Defaults to ``False``.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        config = self._apis.get(api_name)
        if not config:
            return {"error": f"API '{api_name}' not found"}

        cache_key = f"{api_name}:{method}:{path}"
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            import httpx

            url = f"{config.base_url.rstrip('/')}/{path.lstrip('/')}"
            headers = config.headers.copy()

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
                    "data": response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else response.text,
                }

                if use_cache and response.status_code == 200:
                    self._cache[cache_key] = result

                return result

        except ImportError:
            return {"error": "httpx not installed"}
        except Exception as e:
            return {"error": str(e)}

    async def get(self, api_name: str, path: str, **kwargs) -> dict:
        """
        Get.

        Args:
            api_name (str): api name string.
            path (str): filesystem path to operate on.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self.request(api_name, "GET", path, **kwargs)

    async def post(self, api_name: str, path: str, data: dict = None, **kwargs) -> dict:
        """
        Post.

        Args:
            api_name (str): api name string.
            path (str): filesystem path to operate on.
            data (dict): mapping of data. Defaults to ``None``.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self.request(api_name, "POST", path, data=data, **kwargs)

    async def put(self, api_name: str, path: str, data: dict = None, **kwargs) -> dict:
        """
        Put.

        Args:
            api_name (str): api name string.
            path (str): filesystem path to operate on.
            data (dict): mapping of data. Defaults to ``None``.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self.request(api_name, "PUT", path, data=data, **kwargs)

    async def delete(self, api_name: str, path: str, **kwargs) -> dict:
        """
        Delete.

        Args:
            api_name (str): api name string.
            path (str): filesystem path to operate on.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self.request(api_name, "DELETE", path, **kwargs)

    def clear_cache(self) -> None:
        """
        Clear cache.
        """
        self._cache.clear()

    def list_apis(self) -> list[dict]:
        """
        List apis.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "name": api.name,
                "base_url": api.base_url,
                "auth_type": api.auth_type,
            }
            for api in self._apis.values()
        ]
