from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, Optional

logger = logging.getLogger(__name__)

class SignalAdapter:

    def __init__(self, number: str = "", api_url: str = "http://localhost:8080") -> None:
        self.number = number
        self.api_url = api_url.rstrip("/")
        self._message_fn: Callable | None = None

    def set_message_function(self, fn: Callable) -> None:
        self._message_fn = fn

    async def handle_webhook(self, data: dict) -> dict[str, Any]:
        try:
            envelope = data.get("envelope", {})

            if envelope.get("syncMessage"):
                sync = envelope["syncMessage"]
                if sync.get("sentMessage"):
                    sent = sync["sentMessage"]
                    if self._message_fn:
                        await self._message_fn(
                            platform="signal",
                            chat_id=sent.get("destination", {}).get("number", ""),
                            user_id=envelope.get("source", ""),
                            text=sent.get("message", ""),
                            message_id=sent.get("timestamp", ""),
                        )

            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Failed to handle Signal webhook: {e}")
            return {"status": "error", "error": str(e)}

    async def send_message(self, chat_id: str, text: str, **kwargs) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/v2/send",
                    json={
                        "number": self.number,
                        "recipients": [chat_id],
                        "message": text,
                    },
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Signal message: {e}")
            return False

    async def send_image(self, chat_id: str, image_path: str) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                with open(image_path, "rb") as f:
                    response = await client.post(
                        f"{self.api_url}/v2/send",
                        data={
                            "number": self.number,
                            "recipients": [chat_id],
                        },
                        files={"attachment": f},
                        timeout=30.0,
                    )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Signal image: {e}")
            return False

    def get_platform_info(self) -> dict[str, Any]:
        return {
            "name": "signal",
            "version": "1.0.0",
            "configured": bool(self.number),
        }
