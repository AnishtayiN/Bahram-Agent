from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class WebFetchTool:
    ""

    def __init__(self) -> None:
        self._timeout: float = 30.0
        self._max_size: int = 1024 * 1024

    async def fetch(
        self,
        url: str,
        format: str = "text",
        timeout: float = None,
    ) -> dict[str, Any]:
        ""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=timeout or self._timeout,
                    follow_redirects=True,
                    headers={
                        "User-Agent": "Bahram Agent/1.0",
                    },
                )

                if response.status_code != 200:
                    return {
                        "error": f"HTTP {response.status_code}",
                        "content": "",
                    }

                content = response.text[:self._max_size]

                if format == "text":
                    return {"content": content}
                elif format == "json":
                    return {"content": response.json()}
                elif format == "html":
                    return {"content": content, "content_type": "html"}
                else:
                    return {"content": content}

        except ImportError:
            return {"error": "httpx not installed"}
        except Exception as e:
            return {"error": str(e)}

    async def fetch_text(self, url: str) -> str:
        ""
        result = await self.fetch(url, format="text")
        return result.get("content", result.get("error", ""))

    async def fetch_json(self, url: str) -> Any:
        ""
        result = await self.fetch(url, format="json")
        return result.get("content", result.get("error", ""))

    def set_timeout(self, timeout: float) -> None:
        ""
        self._timeout = timeout

    def set_max_size(self, max_size: int) -> None:
        ""
        self._max_size = max_size
