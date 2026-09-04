from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class HonchoModel:

    def __init__(self, data_dir: str = "data/honcho") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, dict] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        profiles_file = self.data_dir / "profiles.json"
        if profiles_file.exists():
            try:
                with open(profiles_file) as f:
                    self._profiles = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load profiles: {e}")

    def _save_profiles(self) -> None:
        profiles_file = self.data_dir / "profiles.json"
        try:
            with open(profiles_file, "w") as f:
                json.dump(self._profiles, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")

    def get_profile(self, user_id: str) -> dict:
        if user_id not in self._profiles:
            self._profiles[user_id] = {
                "id": user_id,
                "created": datetime.now().isoformat(),
                "updated": datetime.now().isoformat(),
                "preferences": {},
                "communication_style": {},
                "topics": {},
                "interactions": 0,
                "sessions": [],
            }
        return self._profiles[user_id]

    def update_profile(self, user_id: str, updates: dict) -> None:
        profile = self.get_profile(user_id)
        profile.update(updates)
        profile["updated"] = datetime.now().isoformat()
        self._save_profiles()

    def record_interaction(self, user_id: str, message: str, response: str) -> None:
        profile = self.get_profile(user_id)
        profile["interactions"] = profile.get("interactions", 0) + 1

        self._extract_preferences(user_id, message)

        self._update_communication_style(user_id, message, response)

        self._save_profiles()

    def _extract_preferences(self, user_id: str, message: str) -> None:
        profile = self.get_profile(user_id)
        preferences = profile.get("preferences", {})

        message_lower = message.lower()

        persian_chars = sum(1 for c in message if '\u0600' <= c <= '\u06FF')
        if persian_chars > len(message) * 0.3:
            preferences["language"] = "persian"
        else:
            preferences["language"] = "english"

        formal_indicators = ["please", "thank you", "excuse me", "لطفا", "ممنون"]
        if any(indicator in message_lower for indicator in formal_indicators):
            preferences["formality"] = "formal"
        else:
            preferences["formality"] = "casual"

        profile["preferences"] = preferences

    def _update_communication_style(self, user_id: str, message: str, response: str) -> None:
        profile = self.get_profile(user_id)
        style = profile.setdefault("communication_style", {})

        avg_length = style.get("avg_message_length", 0)
        interactions = profile.get("interactions", 1)
        style["avg_message_length"] = (avg_length * (interactions - 1) + len(message)) / interactions

        avg_response = style.get("avg_response_length", 0)
        style["avg_response_length"] = (avg_response * (interactions - 1) + len(response)) / interactions

        profile["communication_style"] = style

    def add_topic(self, user_id: str, topic: str, sentiment: float = 0.0) -> None:
        profile = self.get_profile(user_id)
        topics = profile.get("topics", {})

        if topic not in topics:
            topics[topic] = {
                "mentions": 0,
                "sentiment": 0.0,
                "first_seen": datetime.now().isoformat(),
            }

        topics[topic]["mentions"] = topics[topic].get("mentions", 0) + 1
        topics[topic]["sentiment"] = (
            topics[topic].get("sentiment", 0) + sentiment
        ) / 2
        topics[topic]["last_seen"] = datetime.now().isoformat()

        profile["topics"] = topics
        self._save_profiles()

    def get_recommendations(self, user_id: str) -> list[str]:
        profile = self.get_profile(user_id)
        topics = profile.get("topics", {})

        sorted_topics = sorted(
            topics.items(),
            key=lambda x: (x[1].get("mentions", 0), x[1].get("sentiment", 0)),
            reverse=True,
        )

        return [topic for topic, _ in sorted_topics[:5]]

    def get_user_summary(self, user_id: str) -> str:
        profile = self.get_profile(user_id)
        preferences = profile.get("preferences", {})
        topics = profile.get("topics", {})
        style = profile.get("communication_style", {})
        summary = f"User Profile: {user_id}\n"
        summary += f"Style: {style.get('formality', 'unknown')}\n" if style else ""
        summary += f"Interactions: {profile.get('interactions', 0)}\n"
        summary += f"Language: {preferences.get('language', 'unknown')}\n"
        summary += f"Formality: {preferences.get('formality', 'unknown')}\n"

        if topics:
            top_topics = sorted(topics.keys(), key=lambda t: topics[t].get("mentions", 0), reverse=True)[:3]
            summary += f"Top topics: {', '.join(top_topics)}\n"

        return summary

    def list_profiles(self) -> list[str]:
        return list(self._profiles.keys())

    def delete_profile(self, user_id: str) -> None:
        self._profiles.pop(user_id, None)
        self._save_profiles()
