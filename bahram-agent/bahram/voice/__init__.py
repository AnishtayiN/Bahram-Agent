from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class VoiceTranscriber:

    def __init__(self, method: str = "whisper") -> None:
        self.method = method
        self._whisper_model = None

    async def transcribe(self, audio_path: str) -> Optional[str]:
        try:
            if self.method == "whisper":
                return await self._transcribe_whisper(audio_path)
            elif self.method == "command":
                return await self._transcribe_command(audio_path)
            else:
                logger.error(f"Unknown transcription method: {self.method}")
                return None
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return None

    async def _transcribe_whisper(self, audio_path: str) -> Optional[str]:
        try:
            import whisper

            if self._whisper_model is None:
                self._whisper_model = whisper.load_model("base")

            result = self._whisper_model.transcribe(audio_path)
            return result.get("text", "")

        except ImportError:
            logger.error("whisper not installed. Install with: pip install openai-whisper")
            return None
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return None

    async def _transcribe_command(self, audio_path: str) -> Optional[str]:
        import os

        command = os.environ.get("BAHRAM_STT_COMMAND")
        if not command:
            logger.error("BAHRAM_STT_COMMAND not set")
            return None

        try:

            cmd = command.format(audio_path=audio_path)

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=60
            )

            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.error(f"STT command failed: {stderr.decode()}")
                return None

        except Exception as e:
            logger.error(f"Command transcription failed: {e}")
            return None

    async def convert_ogg_to_wav(self, ogg_path: str) -> str:
        wav_path = tempfile.mktemp(suffix=".wav")

        try:
            process = await asyncio.create_subprocess_shell(
                f"ffmpeg -i {ogg_path} -ar 16000 -ac 1 {wav_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await process.wait()
            return wav_path

        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            return ogg_path
