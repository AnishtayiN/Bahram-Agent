"""
Todo.

Public objects: ``TodoItem``, ``TodoTool``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TodoItem:
    """
    Todo item.

    Attributes:
        id (str): id string.
        content (str): text content to process.
        status (str): status string.
        priority (str): priority string.
        created_at (float): numeric value for created at.
        completed_at (float): numeric value for completed at.
    """

    id: str
    content: str
    status: str = "pending"
    priority: str = "medium"
    created_at: float = 0.0
    completed_at: float = 0.0


class TodoTool:
    """
    Todo tool.
    """

    def __init__(self, data_dir: str = "data") -> None:
        """
        Initialise a TodoTool instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to ``'data'``.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._todos: dict[str, TodoItem] = {}
        self._load()

    def _load(self) -> None:
        todos_file = self.data_dir / "todos.json"
        if todos_file.exists():
            try:
                with open(todos_file) as f:
                    data = json.load(f)
                for todo_data in data:
                    todo = TodoItem(**todo_data)
                    self._todos[todo.id] = todo
            except Exception as e:
                logger.warning(f"Failed to load todos: {e}")

    def _save(self) -> None:
        todos_file = self.data_dir / "todos.json"
        data = [
            {
                "id": t.id,
                "content": t.content,
                "status": t.status,
                "priority": t.priority,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in self._todos.values()
        ]
        with open(todos_file, "w") as f:
            json.dump(data, f, indent=2)

    def add(
        self,
        content: str,
        priority: str = "medium",
    ) -> TodoItem:
        """
        Add.

        Args:
            content (str): text content to process.
            priority (str): priority string. Defaults to ``'medium'``.

        Returns:
            TodoItem: the resulting TodoItem.
        """
        import time
        import uuid

        todo_id = f"todo_{uuid.uuid4().hex[:8]}"
        todo = TodoItem(
            id=todo_id,
            content=content,
            priority=priority,
            created_at=time.time(),
        )
        self._todos[todo_id] = todo
        self._save()
        return todo

    def update_status(self, todo_id: str, status: str) -> bool:
        """
        Update status.

        Args:
            todo_id (str): todo id string.
            status (str): status string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if todo_id in self._todos:
            import time

            self._todos[todo_id].status = status
            if status == "completed":
                self._todos[todo_id].completed_at = time.time()
            self._save()
            return True
        return False

    def delete(self, todo_id: str) -> bool:
        """
        Delete.

        Args:
            todo_id (str): todo id string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if todo_id in self._todos:
            del self._todos[todo_id]
            self._save()
            return True
        return False

    def list_todos(self, status: str = None) -> list[dict]:
        """
        List todos.

        Args:
            status (str): status string. Defaults to ``None``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        todos = list(self._todos.values())
        if status:
            todos = [t for t in todos if t.status == status]
        return [
            {
                "id": t.id,
                "content": t.content,
                "status": t.status,
                "priority": t.priority,
            }
            for t in todos
        ]

    def get_summary(self) -> dict[str, int]:
        """
        Return the summary.

        Returns:
            dict[str, int]: a mapping of str, int.
        """
        return {
            "total": len(self._todos),
            "pending": sum(1 for t in self._todos.values() if t.status == "pending"),
            "in_progress": sum(1 for t in self._todos.values() if t.status == "in_progress"),
            "completed": sum(1 for t in self._todos.values() if t.status == "completed"),
        }

    def clear_completed(self) -> int:
        """
        Clear completed.

        Returns:
            int: the computed numeric value.
        """
        completed = [t.id for t in self._todos.values() if t.status == "completed"]
        for todo_id in completed:
            del self._todos[todo_id]
        if completed:
            self._save()
        return len(completed)
