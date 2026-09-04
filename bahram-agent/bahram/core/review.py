from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class ReviewItem:

    conversation_id: str
    timestamp: float
    summary: str
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    reviewed: bool = False

class BackgroundReviewer:

    def __init__(self, data_dir: str = "data/memory") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._reviews: list[ReviewItem] = []
        self._enabled = True
        self._review_fn: Callable | None = None
        self._load()

    def _load(self) -> None:
        reviews_file = self.data_dir / "reviews.json"
        if reviews_file.exists():
            try:
                with open(reviews_file) as f:
                    data = json.load(f)
                self._reviews = [ReviewItem(**r) for r in data]
            except Exception as e:
                logger.warning(f"Failed to load reviews: {e}")

    def _save(self) -> None:
        reviews_file = self.data_dir / "reviews.json"
        data = [
            {
                "conversation_id": r.conversation_id,
                "timestamp": r.timestamp,
                "summary": r.summary,
                "issues": r.issues,
                "suggestions": r.suggestions,
                "reviewed": r.reviewed,
            }
            for r in self._reviews
        ]
        with open(reviews_file, "w") as f:
            json.dump(data, f, indent=2)

    def set_review_function(self, fn: Callable) -> None:
        self._review_fn = fn

    async def review_conversation(
        self,
        conversation_id: str,
        messages: list[dict],
        model_fn: Callable = None,
    ) -> ReviewItem:

        review_fn = model_fn or self._review_fn

        if review_fn:
            prompt = ""

            try:
                response = await review_fn([{"role": "user", "content": prompt}])
                result = json.loads(response)
            except Exception as e:
                logger.warning(f"Review failed: {e}")
                result = {
                    "summary": "Review failed",
                    "issues": [str(e)],
                    "suggestions": [],
                }
        else:

            result = self._heuristic_review(messages)

        review = ReviewItem(
            conversation_id=conversation_id,
            timestamp=time.time(),
            summary=result.get("summary", ""),
            issues=result.get("issues", []),
            suggestions=result.get("suggestions", []),
        )

        self._reviews.append(review)
        self._save()
        return review

    def _heuristic_review(self, messages: list[dict]) -> dict:
        issues = []
        suggestions = []

        for msg in messages:
            if not msg.get("content", "").strip():
                issues.append("Empty message found")

        contents = [msg.get("content", "") for msg in messages]
        for i in range(len(contents) - 1):
            if contents[i] == contents[i + 1] and contents[i]:
                issues.append("Repeated message content")

        for msg in messages:
            content = msg.get("content", "")
            if len(content) > 10000:
                issues.append("Very long message detected")
                suggestions.append("Consider summarizing long content")

        if not issues:
            summary = "Conversation looks good"
        else:
            summary = f"Found {len(issues)} issue(s)"

        return {
            "summary": summary,
            "issues": issues,
            "suggestions": suggestions,
        }

    def get_pending_reviews(self) -> list[dict]:
        return [
            {
                "conversation_id": r.conversation_id,
                "timestamp": r.timestamp,
                "summary": r.summary,
            }
            for r in self._reviews
            if not r.reviewed
        ]

    def mark_reviewed(self, conversation_id: str) -> bool:
        for r in self._reviews:
            if r.conversation_id == conversation_id:
                r.reviewed = True
                self._save()
                return True
        return False

    def get_statistics(self) -> dict[str, Any]:
        total = len(self._reviews)
        reviewed = sum(1 for r in self._reviews if r.reviewed)
        issues = sum(len(r.issues) for r in self._reviews)
        return {
            "total_reviews": total,
            "reviewed": reviewed,
            "pending": total - reviewed,
            "total_issues": issues,
            "avg_issues_per_review": issues / total if total > 0 else 0,
        }
