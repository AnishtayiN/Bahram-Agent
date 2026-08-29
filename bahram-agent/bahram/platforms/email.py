from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

class EmailAdapter:
    ""

    def __init__(self, config: dict = None) -> None:
        self.config = config or {}
        self._handler: Optional[Callable] = None
        self._running = False

    def set_handler(self, handler: Callable) -> None:
        ""
        self._handler = handler

    async def start(self) -> None:
        ""
        self._running = True
        logger.info("Email adapter started")

    async def stop(self) -> None:
        ""
        self._running = False
        logger.info("Email adapter stopped")

    async def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        **kwargs: Any,
    ) -> bool:
        ""
        logger.info(f"Email to {to}: {subject}")
        return True
