"""
Email.

Public objects: ``EmailAdapter``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class EmailAdapter:
    """
    Email adapter.
    """

    def __init__(self, config: dict = None) -> None:
        """
        Initialise a EmailAdapter instance.

        Args:
            config (dict): configuration object. Defaults to ``None``.
        """
        self.config = config or {}
        self._handler: Callable | None = None
        self._running = False

    def set_handler(self, handler: Callable) -> None:
        """
        Set the handler.

        Args:
            handler (Callable): callable used for handler.
        """
        self._handler = handler

    async def start(self) -> None:
        """
        Start the component and acquire any resources it needs.

        Note:
            Coroutine - must be awaited.
        """
        self._running = True
        logger.info("Email adapter started")

    async def stop(self) -> None:
        """
        Stop the component and release any resources it holds.

        Note:
            Coroutine - must be awaited.
        """
        self._running = False
        logger.info("Email adapter stopped")

    async def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> bool:
        """
        Send message.

        Args:
            to (str): to string.
            subject (str): subject string.
            body (str): body string.
            **kwargs (Any): keyword arguments forwarded to the implementation.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        logger.info(f"Email to {to}: {subject}")
        return True
