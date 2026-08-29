from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

class WhatsAppAdapter:
    ""

    def __init__(self, phone_number_id: str = "", access_token: str = "", verify_token: str = "") -> None:
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.verify_token = verify_token
        self._message_fn: Optional[Callable] = None

    def set_message_function(self, fn: Callable) -> None:
        ""
        self._message_fn = fn

    async def handle_webhook(self, data: dict) -> dict[str, Any]:
        ""
        try:
            entry = data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            messages = value.get("messages", [])
            for msg in messages:
                if self._message_fn:
                    await self._message_fn(
                        platform="whatsapp",
                        chat_id=msg.get("from", ""),
                        user_id=msg.get("from", ""),
                        text=msg.get("text", {}).get("body", ""),
                        message_id=msg.get("id", ""),
                    )

            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Failed to handle WhatsApp webhook: {e}")
            return {"status": "error", "error": str(e)}

    async def verify_webhook(self, mode: str, token: str, challenge: str) -> str:
        ""
        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return ""

    async def send_message(self, chat_id: str, text: str, **kwargs) -> bool:
        ""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://graph.facebook.com/v17.0/{self.phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": chat_id,
                        "type": "text",
                        "text": {"body": text},
                    },
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return False

    async def send_image(self, chat_id: str, image_url: str, caption: str = "") -> bool:
        ""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://graph.facebook.com/v17.0/{self.phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "to": chat_id,
                        "type": "image",
                        "image": {
                            "link": image_url,
                            "caption": caption,
                        },
                    },
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send WhatsApp image: {e}")
            return False

    def get_platform_info(self) -> dict[str, Any]:
        ""
        return {
            "name": "whatsapp",
            "version": "1.0.0",
            "configured": bool(self.phone_number_id and self.access_token),
        }
