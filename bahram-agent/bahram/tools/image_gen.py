from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

class ImageGenTool:
    ""

    def __init__(self) -> None:
        self._provider: str = "openai"
        self._api_key: str = ""
        self._output_dir: str = "data/images"

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        style: str = "vivid",
        output_path: str = None,
    ) -> dict[str, Any]:
        ""
        if self._provider == "openai":
            return await self._generate_openai(prompt, size, style, output_path)
        else:
            return {"error": f"Unsupported provider: {self._provider}"}

    async def _generate_openai(
        self,
        prompt: str,
        size: str,
        style: str,
        output_path: str = None,
    ) -> dict[str, Any]:
        ""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": prompt,
                        "size": size,
                        "style": style,
                        "n": 1,
                    },
                    timeout=120.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    image_url = data["data"][0]["url"]

                    if output_path:
                        img_response = await client.get(image_url)
                        if img_response.status_code == 200:
                            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                            Path(output_path).write_bytes(img_response.content)
                            return {
                                "url": image_url,
                                "path": output_path,
                            }

                    return {"url": image_url}
                else:
                    error = response.json().get("error", {}).get("message", "Unknown error")
                    return {"error": error}

        except ImportError:
            return {"error": "httpx not installed"}
        except Exception as e:
            return {"error": str(e)}

    def set_provider(self, provider: str) -> None:
        ""
        self._provider = provider

    def set_api_key(self, api_key: str) -> None:
        ""
        self._api_key = api_key
