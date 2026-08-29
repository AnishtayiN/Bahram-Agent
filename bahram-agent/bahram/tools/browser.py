"""Browser tool for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BrowserState:
    """Browser state."""

    url: str = ""
    title: str = ""
    content: str = ""
    screenshot: bytes = b""


class BrowserTool:
    """Browser automation tool."""

    def __init__(self) -> None:
        self._browser = None
        self._page = None
        self._headless: bool = True

    async def start(self, headless: bool = True) -> bool:
        """Start the browser."""
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
        """Stop the browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL."""
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
        """Click an element."""
        if not self._page:
            return False

        try:
            await self._page.click(selector)
            return True
        except Exception as e:
            logger.warning(f"Click failed: {e}")
            return False

    async def type_text(self, selector: str, text: str) -> bool:
        """Type text into an element."""
        if not self._page:
            return False

        try:
            await self._page.fill(selector, text)
            return True
        except Exception as e:
            logger.warning(f"Type failed: {e}")
            return False

    async def get_content(self) -> str:
        """Get page content."""
        if not self._page:
            return ""

        try:
            return await self._page.content()
        except Exception:
            return ""

    async def screenshot(self) -> Optional[bytes]:
        """Take a screenshot."""
        if not self._page:
            return None

        try:
            return await self._page.screenshot()
        except Exception:
            return None

    async def evaluate(self, expression: str) -> Any:
        """Evaluate JavaScript."""
        if not self._page:
            return None

        try:
            return await self._page.evaluate(expression)
        except Exception as e:
            return {"error": str(e)}

    def is_running(self) -> bool:
        """Check if browser is running."""
        return self._browser is not None
