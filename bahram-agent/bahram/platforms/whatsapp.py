"""WhatsApp platform adapter for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class WhatsAppAdapter:
    """WhatsApp messaging adapter."""

    def __init__(self, config: dict = None) -> None:
        self.config = config or {}
        self._handler: Optional[Callable] = None
        self._running = False

    def set_handler(self, handler: Callable) -> None:
        """Set message handler."""
        self._handler = handler

    async def start(self) -> None:
        """Start the adapter."""
        self._running = True
        logger.info("WhatsApp adapter started")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._running = False
        logger.info("WhatsApp adapter stopped")

    async def send_message(
        self,
        chat_id: str,
        text: str,
        **kwargs: Any,
    ) -> bool:
        """Send a message."""
        logger.info(f"WhatsApp message to {chat_id}: {text[:100]}...")
        return True

    async def send_image(
        self,
        chat_id: str,
        image_path: str,
        caption: str = "",
    ) -> bool:
        """Send an image."""
        logger.info(f"WhatsApp image to {chat_id}")
        return True

    async def send_file(
        self,
        chat_id: str,
        file_path: str,
        caption: str = "",
    ) -> bool:
        """Send a file."""
        logger.info(f"WhatsApp file to {chat_id}")
        return True

    async def set_typing(self, chat_id: str, typing: bool = True) -> None:
        """Set typing indicator."""
        pass
