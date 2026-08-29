"""Browser automation for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BrowserTool:
    """Browser automation tool."""

    def __init__(self) -> None:
        self._page: Any = None
        self._browser: Any = None

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL."""
        try:
            from playwright.async_api import async_playwright

            if not self._browser:
                pw = await async_playwright().__aenter__()
                self._browser = await pw.chromium.launch(headless=True)
                self._page = await self._browser.new_page()

            await self._page.goto(url, wait_until="domcontentloaded")
            title = await self._page.title()

            return {
                "status": "ok",
                "url": url,
                "title": title,
            }
        except ImportError:
            return {"error": "Playwright not installed. Run: pip install playwright && playwright install"}
        except Exception as e:
            return {"error": str(e)}

    async def snapshot(self) -> dict[str, Any]:
        """Take a snapshot of the current page."""
        if not self._page:
            return {"error": "No page loaded"}

        try:
            content = await self._page.content()
            text = await self._page.inner_text("body")

            return {
                "status": "ok",
                "text": text[:5000],
                "html": content[:5000],
            }
        except Exception as e:
            return {"error": str(e)}

    async def click(self, selector: str) -> dict[str, Any]:
        """Click an element."""
        if not self._page:
            return {"error": "No page loaded"}

        try:
            await self._page.click(selector)
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    async def type_text(self, selector: str, text: str) -> dict[str, Any]:
        """Type text into an element."""
        if not self._page:
            return {"error": "No page loaded"}

        try:
            await self._page.fill(selector, text)
            return {"status": "ok"}
        except Exception as e:
            return {"error": str(e)}

    async def screenshot(self, path: str = "screenshot.png") -> dict[str, Any]:
        """Take a screenshot."""
        if not self._page:
            return {"error": "No page loaded"}

        try:
            await self._page.screenshot(path=path)
            return {"status": "ok", "path": path}
        except Exception as e:
            return {"error": str(e)}

    async def close(self) -> None:
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None
