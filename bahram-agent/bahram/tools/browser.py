"""
Browser.

Public objects: ``BrowserState``, ``BrowserTool``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BrowserState:
    """
    Browser state.

    Attributes:
        url (str): url string.
        title (str): title string.
        content (str): text content to process.
        screenshot (bytes): screenshot.
    """

    url: str = ""
    title: str = ""
    content: str = ""
    screenshot: bytes = b""


class BrowserTool:
    """
    Browser tool.
    """

    def __init__(self) -> None:
        """
        Initialise a BrowserTool instance.
        """
        self._browser = None
        self._page = None
        self._headless: bool = True

    async def start(self, headless: bool = True) -> bool:
        """
        Start the component and acquire any resources it needs.

        Args:
            headless (bool): when ``True``, enable headless. Defaults to ``True``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=headless)
            self._page = await self._browser.new_page()
            self._headless = headless
            return True

        except ImportError:
            logger.warning("playwright not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False

    async def stop(self) -> None:
        """
        Stop the component and release any resources it holds.

        Note:
            Coroutine - must be awaited.
        """
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def navigate(self, url: str) -> dict[str, Any]:
        """
        Navigate.

        Args:
            url (str): url string.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        if not self._page:
            return {"error": "Browser not started"}

        try:
            await self._page.goto(url, wait_until="domcontentloaded")
            title = await self._page.title()
            content = await self._page.content()

            return {
                "url": url,
                "title": title,
                "content": content[:10000],
            }
        except Exception as e:
            return {"error": str(e)}

    async def click(self, selector: str) -> bool:
        """
        Click.

        Args:
            selector (str): selector string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        if not self._page:
            return False

        try:
            await self._page.click(selector)
            return True
        except Exception as e:
            logger.warning(f"Click failed: {e}")
            return False

    async def type_text(self, selector: str, text: str) -> bool:
        """
        Type text.

        Args:
            selector (str): selector string.
            text (str): text string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        if not self._page:
            return False

        try:
            await self._page.fill(selector, text)
            return True
        except Exception as e:
            logger.warning(f"Type failed: {e}")
            return False

    async def get_content(self) -> str:
        """
        Return the content.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        if not self._page:
            return ""

        try:
            return await self._page.content()
        except Exception:
            return ""

    async def screenshot(self) -> bytes | None:
        """
        Screenshot.

        Returns:
            bytes | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        if not self._page:
            return None

        try:
            return await self._page.screenshot()
        except Exception:
            return None

    async def evaluate(self, expression: str) -> Any:
        """
        Evaluate.

        Args:
            expression (str): expression string.

        Returns:
            Any: the resulting Any.

        Note:
            Coroutine - must be awaited.
        """
        if not self._page:
            return None

        try:
            return await self._page.evaluate(expression)
        except Exception as e:
            return {"error": str(e)}

    def is_running(self) -> bool:
        """
        Return ``True`` when running.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        return self._browser is not None
