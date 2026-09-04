"""
Homeassistant advanced.

Public objects: ``HomeAssistantAdvanced``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HomeAssistantAdvanced:
    """
    Home assistant advanced.
    """

    def __init__(self, url: str = "", token: str = "") -> None:
        """
        Initialise a HomeAssistantAdvanced instance.

        Args:
            url (str): url string. Defaults to ``''``.
            token (str): token string. Defaults to ``''``.
        """
        self.url = url.rstrip("/")
        self.token = token

    async def get_automations(self) -> dict[str, Any]:
        """
        Return the automations.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._get_states("automation")

    async def get_scripts(self) -> dict[str, Any]:
        """
        Return the scripts.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._get_states("script")

    async def get_scenes(self) -> dict[str, Any]:
        """
        Return the scenes.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._get_states("scene")

    async def get_climate(self) -> dict[str, Any]:
        """
        Return the climate.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._get_states("climate")

    async def get_lights(self) -> dict[str, Any]:
        """
        Return the lights.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._get_states("light")

    async def get_switches(self) -> dict[str, Any]:
        """
        Return the switches.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._get_states("switch")

    async def get_sensors(self) -> dict[str, Any]:
        """
        Return the sensors.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._get_states("sensor")

    async def turn_on(self, entity_id: str, **kwargs) -> dict[str, Any]:
        """
        Turn on.

        Args:
            entity_id (str): entity id string.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        domain = entity_id.split(".")[0]
        return await self._call_service(domain, "turn_on", entity_id, kwargs)

    async def turn_off(self, entity_id: str) -> dict[str, Any]:
        """
        Turn off.

        Args:
            entity_id (str): entity id string.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        domain = entity_id.split(".")[0]
        return await self._call_service(domain, "turn_off", entity_id)

    async def toggle(self, entity_id: str) -> dict[str, Any]:
        """
        Toggle.

        Args:
            entity_id (str): entity id string.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        domain = entity_id.split(".")[0]
        return await self._call_service(domain, "toggle", entity_id)

    async def set_temperature(self, entity_id: str, temperature: float) -> dict[str, Any]:
        """
        Set the temperature.

        Args:
            entity_id (str): entity id string.
            temperature (float): numeric value for temperature.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._call_service(
            "climate", "set_temperature", entity_id, {"temperature": temperature}
        )

    async def set_brightness(self, entity_id: str, brightness: int) -> dict[str, Any]:
        """
        Set the brightness.

        Args:
            entity_id (str): entity id string.
            brightness (int): numeric value for brightness.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._call_service("light", "turn_on", entity_id, {"brightness": brightness})

    async def set_color(self, entity_id: str, r: int, g: int, b: int) -> dict[str, Any]:
        """
        Set the color.

        Args:
            entity_id (str): entity id string.
            r (int): numeric value for r.
            g (int): numeric value for g.
            b (int): numeric value for b.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return await self._call_service("light", "turn_on", entity_id, {"rgb_color": [r, g, b]})

    async def _get_states(self, domain: str) -> dict[str, Any]:
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
