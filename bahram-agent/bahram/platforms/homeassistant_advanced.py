"""Home Assistant advanced integration for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HomeAssistantAdvanced:
    """Advanced Home Assistant features."""

    def __init__(self, url: str = "", token: str = "") -> None:
        self.url = url.rstrip("/")
        self.token = token

    async def get_automations(self) -> dict[str, Any]:
        """Get all automations."""
        return await self._get_states("automation")

    async def get_scripts(self) -> dict[str, Any]:
        """Get all scripts."""
        return await self._get_states("script")

    async def get_scenes(self) -> dict[str, Any]:
        """Get all scenes."""
        return await self._get_states("scene")

    async def get_climate(self) -> dict[str, Any]:
        """Get climate entities."""
        return await self._get_states("climate")

    async def get_lights(self) -> dict[str, Any]:
        """Get all lights."""
        return await self._get_states("light")

    async def get_switches(self) -> dict[str, Any]:
        """Get all switches."""
        return await self._get_states("switch")

    async def get_sensors(self) -> dict[str, Any]:
        """Get all sensors."""
        return await self._get_states("sensor")

    async def turn_on(self, entity_id: str, **kwargs) -> dict[str, Any]:
        """Turn on an entity."""
        domain = entity_id.split(".")[0]
        return await self._call_service(domain, "turn_on", entity_id, kwargs)

    async def turn_off(self, entity_id: str) -> dict[str, Any]:
        """Turn off an entity."""
        domain = entity_id.split(".")[0]
        return await self._call_service(domain, "turn_off", entity_id)

    async def toggle(self, entity_id: str) -> dict[str, Any]:
        """Toggle an entity."""
        domain = entity_id.split(".")[0]
        return await self._call_service(domain, "toggle", entity_id)

    async def set_temperature(self, entity_id: str, temperature: float) -> dict[str, Any]:
        """Set climate temperature."""
        return await self._call_service(
            "climate", "set_temperature", entity_id,
            {"temperature": temperature}
        )

    async def set_brightness(self, entity_id: str, brightness: int) -> dict[str, Any]:
        """Set light brightness (0-255)."""
        return await self._call_service(
            "light", "turn_on", entity_id,
            {"brightness": brightness}
        )

    async def set_color(self, entity_id: str, r: int, g: int, b: int) -> dict[str, Any]:
        """Set light color."""
        return await self._call_service(
            "light", "turn_on", entity_id,
            {"rgb_color": [r, g, b]}
        }

    async def _get_states(self, domain: str) -> dict[str, Any]:
        """Get states for a domain."""
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
                    filtered = [s for s in states if s["entity_id"].startswith(domain + ".")]
                    return {"entities": filtered}
                else:
                    return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def _call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: dict = None,
    ) -> dict[str, Any]:
        """Call a Home Assistant service."""
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
                    json={"entity_id": entity_id, **(data or {})},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    return {"status": "ok"}
                else:
                    return {"error": f"API error: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
