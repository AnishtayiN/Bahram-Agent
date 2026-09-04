from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class HomeAssistantTool:

    def __init__(self, url: str = "", token: str = "") -> None:
        self.url = url.rstrip("/")
        self.token = token

    async def list_entities(self, domain: str = "") -> dict[str, Any]:
        if not self.url or not self.token:
            return {"error": "Home Assistant not configured"}

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/api/states",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    states = response.json()
                    if domain:
                        states = [s for s in states if s["entity_id"].startswith(domain + ".")]
                    return {"entities": states[:50]}
                else:
                    return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def get_state(self, entity_id: str) -> dict[str, Any]:
        if not self.url or not self.token:
            return {"error": "Home Assistant not configured"}

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/api/states/{entity_id}",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    return {"state": response.json()}
                else:
                    return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: dict = None,
    ) -> dict[str, Any]:
        if not self.url or not self.token:
            return {"error": "Home Assistant not configured"}

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/api/services/{domain}/{service}",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "entity_id": entity_id,
                        **(data or {}),
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    return {"status": "ok"}
                else:
                    return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
