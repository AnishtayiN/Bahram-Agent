"""Todo/task planning tool for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TodoItem:
    """A todo item."""

    id: int
    content: str
    status: str = "pending"  # pending, in_progress, completed, cancelled
    priority: str = "medium"  # high, medium, low
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    subtasks: list["TodoItem"] = field(default_factory=list)


class TodoManager:
    """Manage task lists."""

    def __init__(self, data_dir: str = "data/todos") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lists: dict[str, list[TodoItem]] = {}
        self._counter = 0

    def _next_id(self) -> int:
        """Generate next ID."""
        self._counter += 1
        return self._counter

    def create_list(self, name: str = "default") -> list[TodoItem]:
        """Create a new todo list."""
        if name not in self._lists:
            self._lists[name] = []
        return self._lists[name]

    def add_item(
        self,
        content: str,
        list_name: str = "default",
        priority: str = "medium",
    ) -> TodoItem:
        """Add an item to the list."""
        if list_name not in self._lists:
            self.create_list(list_name)

        item = TodoItem(
            id=self._next_id(),
            content=content,
            priority=priority,
        )
        self._lists[list_name].append(item)
        self._save(list_name)
        return item

    def update_status(
        self,
        item_id: int,
        status: str,
        list_name: str = "default",
    ) -> bool:
        """Update item status."""
        items = self._lists.get(list_name, [])
        for item in items:
            if item.id == item_id:
                item.status = status
                if status == "completed":
                    item.completed_at = datetime.now().isoformat()
                self._save(list_name)
                return True
        return False

    def remove_item(self, item_id: int, list_name: str = "default") -> bool:
        """Remove an item."""
        items = self._lists.get(list_name, [])
        for i, item in enumerate(items):
            if item.id == item_id:
                items.pop(i)
                self._save(list_name)
                return True
        return False

    def get_list(self, list_name: str = "default") -> list[TodoItem]:
        """Get a todo list."""
        return self._lists.get(list_name, [])

    def render(self, list_name: str = "default") -> str:
        """Render a list as markdown."""
        items = self.get_list(list_name)
        if not items:
            return "No tasks."

        parts = []
        for item in items:
            status_icon = {
                "pending": "[ ]",
                "in_progress": "[~]",
                "completed": "[x]",
                "cancelled": "[-]",
            }.get(item.status, "[ ]")

            priority_icon = {
                "high": "!!",
                "medium": "",
                "low": "~",
            }.get(item.priority, "")

            parts.append(f"{status_icon} #{item.id} {item.content} {priority_icon}")

        return "\n".join(parts)

    def _save(self, list_name: str) -> None:
        """Save list to disk."""
        items = self._lists.get(list_name, [])
        data = [
            {
                "id": item.id,
                "content": item.content,
                "status": item.status,
                "priority": item.priority,
                "created_at": item.created_at,
                "completed_at": item.completed_at,
            }
            for item in items
        ]

        filepath = self.data_dir / f"{list_name}.json"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self, list_name: str) -> None:
        """Load list from disk."""
        filepath = self.data_dir / f"{list_name}.json"
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
            self._lists[list_name] = [
                TodoItem(**item) for item in data
            ]
