"""
Whatsapp.

Public objects: ``WhatsAppAdapter``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class WhatsAppAdapter:
    """
    Whats app adapter.
    """

    def __init__(
        self, phone_number_id: str = "", access_token: str = "", verify_token: str = ""
    ) -> None:
        """
        Initialise a WhatsAppAdapter instance.

        Args:
            phone_number_id (str): phone number id string. Defaults to ``''``.
            access_token (str): access token string. Defaults to ``''``.
            verify_token (str): verify token string. Defaults to ``''``.
        """
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.verify_token = verify_token
        self._message_fn: Callable | None = None

    def set_message_function(self, fn: Callable) -> None:
        """
        Set the message function.

        Args:
            fn (Callable): callable used for fn.
        """
        self._message_fn = fn

    async def handle_webhook(self, data: dict) -> dict[str, Any]:
        """
        Handle webhook.

        Args:
            data (dict): mapping of data.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
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
        """
        Verify webhook.

        Args:
            mode (str): mode string.
            token (str): token string.
            challenge (str): challenge string.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        if mode == "subscribe" and token == self.verify_token:
            return challenge
        return ""

    async def send_message(self, chat_id: str, text: str, **kwargs) -> bool:
        """
        Send message.

        Args:
            chat_id (str): chat id string.
            text (str): text string.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
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
        """
        Send image.

        Args:
            chat_id (str): chat id string.
            image_url (str): image url string.
            caption (str): caption string. Defaults to ``''``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
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
        """
        Return the platform info.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "name": "whatsapp",
            "version": "1.0.0",
            "configured": bool(self.phone_number_id and self.access_token),
        }
