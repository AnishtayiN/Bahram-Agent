"""
Modes.

Public objects: ``VoiceTranscriber``, ``TextToSpeech``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VoiceTranscriber:
    """
    Voice transcriber.
    """

    def __init__(self, provider: str = "openai", api_key: str = "") -> None:
        """
        Initialise a VoiceTranscriber instance.

        Args:
            provider (str): provider string. Defaults to ``'openai'``.
            api_key (str): api key string. Defaults to ``''``.
        """
        self.provider = provider
        self.api_key = api_key

    async def transcribe(
        self,
        audio_path: str,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Transcribe.

        Args:
            audio_path (str): audio path string.
            language (str): language string. Defaults to ``'en'``.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        if not self.api_key:
            return {"error": f"No API key configured for {self.provider}"}

        try:
            if self.provider == "openai":
                return await self._transcribe_openai(audio_path, language)
            else:
                return {"error": f"Unknown provider: {self.provider}"}
        except Exception as e:
            return {"error": str(e)}

    async def _transcribe_openai(
        self,
        audio_path: str,
        language: str,
    ) -> dict:
        import httpx

        async with httpx.AsyncClient() as client:
            with open(audio_path, "rb") as f:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (Path(audio_path).name, f, "audio/mpeg")},
                    data={"model": "whisper-1", "language": language},
                    timeout=60.0,
                )

            if response.status_code == 200:
                data = response.json()
                return {"text": data["text"]}
            else:
                return {"error": f"API error: {response.status_code}"}


class TextToSpeech:
    """
    Text to speech.
    """

    def __init__(self, provider: str = "openai", api_key: str = "") -> None:
        """
        Initialise a TextToSpeech instance.

        Args:
            provider (str): provider string. Defaults to ``'openai'``.
            api_key (str): api key string. Defaults to ``''``.
        """
        self.provider = provider
        self.api_key = api_key

    async def synthesize(
        self,
        text: str,
        voice: str = "alloy",
        output_path: str = "output.mp3",
    ) -> dict[str, Any]:
        """
        Synthesize.

        Args:
            text (str): text string.
            voice (str): voice string. Defaults to ``'alloy'``.
            output_path (str): output path string. Defaults to ``'output.mp3'``.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        if not self.api_key:
            return {"error": f"No API key configured for {self.provider}"}

        try:
            if self.provider == "openai":
                return await self._synthesize_openai(text, voice, output_path)
            else:
                return {"error": f"Unknown provider: {self.provider}"}
        except Exception as e:
            return {"error": str(e)}

    async def _synthesize_openai(
        self,
        text: str,
        voice: str,
        output_path: str,
    ) -> dict:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "tts-1",
                    "input": text,
                    "voice": voice,
                },
                timeout=60.0,
            )

            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return {"path": output_path}
            else:
                return {"error": f"API error: {response.status_code}"}
