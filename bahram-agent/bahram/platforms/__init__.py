"""Platform integrations for Bahram Agent."""

from bahram.platforms.base import BasePlatform
from bahram.platforms.telegram import TelegramPlatform
from bahram.platforms.discord import DiscordPlatform
from bahram.platforms.slack import SlackPlatform

__all__ = ["BasePlatform", "TelegramPlatform", "DiscordPlatform", "SlackPlatform"]
