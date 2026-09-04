from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class SessionSearch:

    def __init__(self, data_dir: str = "data/sessions") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def index_session(self, session_id: str, messages: list[dict]) -> None:
        index_file = self.data_dir / f"{session_id}.json"

        content_parts = []
        for msg in messages:
            role = msg.get("role", "")
            text = msg.get("content", "")
            if text:
                content_parts.append(f"{role}: {text}")

        data = {
            "id": session_id,
            "content": "\n".join(content_parts),
            "messages": messages,
        }

        with open(index_file, "w") as f:
            json.dump(data, f, indent=2)

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        results = []
        query_lower = query.lower()

        for index_file in self.data_dir.glob("*.json"):
            try:
                with open(index_file) as f:
                    data = json.load(f)

                content = data.get("content", "").lower()
                if query_lower in content:

                    messages = data.get("messages", [])
                    matches = []
                    for msg in messages:
                        if query_lower in msg.get("content", "").lower():
                            matches.append(msg)

                    if matches:
                        results.append({
                            "session_id": data.get("id", index_file.stem),
                            "matches": matches[:5],
                            "match_count": len(matches),
                        })
            except Exception as e:
                logger.warning(f"Failed to search {index_file}: {e}")

        results.sort(key=lambda x: x["match_count"], reverse=True)
        return results[:limit]

    def get_session(self, session_id: str) -> dict | None:
        index_file = self.data_dir / f"{session_id}.json"
        if index_file.exists():
            with open(index_file) as f:
                return json.load(f)
        return None

    def list_sessions(self) -> list[str]:
        return [f.stem for f in self.data_dir.glob("*.json")]
