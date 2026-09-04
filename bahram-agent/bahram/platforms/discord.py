from __future__ import annotations

import logging

from bahram.platforms.base import BasePlatform, PlatformMessage

logger = logging.getLogger(__name__)


class DiscordPlatform(BasePlatform):
    @property
    def name(self) -> str:
        return "discord"

    async def start(self) -> None:
        try:
            import discord
            from discord.ext import commands

            token = self.config.token
            if not token:
                logger.error("Discord token not configured")
                return

            intents = discord.Intents.default()
            intents.message_content = True

            self.bot = commands.Bot(command_prefix="!", intents=intents)

            @self.bot.event
            async def on_ready():
                logger.info(f"Discord bot logged in as {self.bot.user}")

            @self.bot.event
            async def on_message(message: discord.Message):
                if message.author == self.bot.user:
                    return

                msg = PlatformMessage(
                    platform="discord",
                    user_id=str(message.author.id),
                    user_name=str(message.author),
                    content=message.content,
                    chat_id=str(message.channel.id),
                    message_id=str(message.id),
                    timestamp=message.created_at.timestamp(),
                    reply_to=str(message.reference.message_id) if message.reference else None,
                )

                await self._handle_message(msg)

            await self.bot.start(token)

        except ImportError:
            logger.error("discord.py not installed. Install with: pip install discord.py")
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")

    async def stop(self) -> None:
        if hasattr(self, "bot"):
            await self.bot.close()
            logger.info("Discord bot stopped")

    async def send_message(self, chat_id: str, content: str) -> None:
        if hasattr(self, "bot"):
            channel = self.bot.get_channel(int(chat_id))
            if channel:
                await channel.send(content)

    async def reply(self, message: PlatformMessage, content: str) -> None:
        if hasattr(self, "bot"):
            channel = self.bot.get_channel(int(message.chat_id))
            if channel:
                msg = await channel.fetch_message(int(message.message_id))
                if msg:
                    await msg.reply(content)
