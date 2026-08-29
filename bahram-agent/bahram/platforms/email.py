"""Email platform adapter for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class EmailAdapter:
    """Email messaging adapter."""

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
        logger.info("Email adapter started")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._running = False
        logger.info("Email adapter stopped")

    async def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> bool:
        """Send an email."""
        logger.info(f"Email to {to}: {subject}")
        return True
