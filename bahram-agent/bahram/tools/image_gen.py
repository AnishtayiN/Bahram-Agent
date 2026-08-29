"""Image generation for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Generate images using various providers."""

    def __init__(self, provider: str = "openai", api_key: str = "") -> None:
        self.provider = provider
        self.api_key = api_key

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        style: str = "vivid",
        quality: str = "standard",
    ) -> dict[str, Any]:
        """Generate an image from a prompt.

        Returns:
            Dict with 'url' or 'error' key.
        """
        if not self.api_key:
            return {"error": f"No API key configured for {self.provider}"}

        try:
            if self.provider == "openai":
                return await self._generate_openai(prompt, size, style, quality)
            elif self.provider == "stability":
                return await self._generate_stability(prompt)
            elif self.provider == "fal":
                return await self._generate_fal(prompt)
            else:
                return {"error": f"Unknown provider: {self.provider}"}
        except Exception as e:
            return {"error": str(e)}

    async def _generate_openai(
        self,
        prompt: str,
        size: str,
        style: str,
        quality: str,
    ) -> dict:
        """Generate using OpenAI DALL-E."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "size": size,
                    "style": style,
                    "quality": quality,
                    "n": 1,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {"url": data["data"][0]["url"]}
            else:
                return {"error": f"API error: {response.status_code}"}

    async def _generate_stability(self, prompt: str) -> dict:
        """Generate using Stability AI."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text_prompts": [{"text": prompt}],
                    "cfg_scale": 7,
                    "height": 1024,
                    "width": 1024,
                    "samples": 1,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                import base64
                image_data = base64.b64decode(data["artifacts"][0]["base64"])
                # Save to file
                output_path = "generated_image.png"
                with open(output_path, "wb") as f:
                    f.write(image_data)
                return {"path": output_path}
            else:
                return {"error": f"API error: {response.status_code}"}

    async def _generate_fal(self, prompt: str) -> dict:
        """Generate using FAL.ai."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://fal.run/fal-ai/flux/schnell",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"prompt": prompt},
                timeout=60.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {"url": data.get("images", [{}])[0].get("url", "")}
            else:
                return {"error": f"API error: {response.status_code}"}
