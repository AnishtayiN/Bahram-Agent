"""Learning journey visualization for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class JourneyNode:
    """A node in the learning journey."""

    id: str
    type: str  # skill, memory
    name: str
    content: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)


class LearningJourney:
    """Track and visualize the learning journey."""

    def __init__(self, data_dir: str = "data/journey") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._nodes: list[JourneyNode] = []
        self._load_journey()

    def _load_journey(self) -> None:
        """Load journey from disk."""
        journey_file = self.data_dir / "journey.json"
        if journey_file.exists():
            try:
                with open(journey_file) as f:
                    data = json.load(f)
                self._nodes = [JourneyNode(**n) for n in data]
            except Exception as e:
                logger.warning(f"Failed to load journey: {e}")

    def _save_journey(self) -> None:
        """Save journey to disk."""
        journey_file = self.data_dir / "journey.json"
        data = [
            {
                "id": n.id,
                "type": n.type,
                "name": n.name,
                "content": n.content,
                "created_at": n.created_at,
                "metadata": n.metadata,
            }
            for n in self._nodes
        ]
        with open(journey_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_node(
        self,
        node_type: str,
        name: str,
        content: str = "",
        metadata: dict = None,
    ) -> JourneyNode:
        """Add a node to the journey."""
        import uuid
        node = JourneyNode(
            id=str(uuid.uuid4())[:8],
            type=node_type,
            name=name,
            content=content,
            metadata=metadata or {},
        )
        self._nodes.append(node)
        self._save_journey()
        return node

    def delete_node(self, node_id: str) -> bool:
        """Delete a node."""
        for i, node in enumerate(self._nodes):
            if node.id == node_id:
                self._nodes.pop(i)
                self._save_journey()
                return True
        return False

    def list_nodes(self) -> list[JourneyNode]:
        """List all nodes."""
        return self._nodes.copy()

    def get_node(self, node_id: str) -> Optional[JourneyNode]:
        """Get a node by ID."""
        for node in self._nodes:
            if node.id == node_id:
                return node
        return None

    def render_timeline(self) -> str:
        """Render journey as a timeline."""
        if not self._nodes:
            return "No learning journey yet."

        parts = ["# Learning Journey\n"]
        for node in sorted(self._nodes, key=lambda n: n.created_at):
            icon = "🛠️" if node.type == "skill" else "💾"
            parts.append(f"- {icon} **{node.name}** ({node.created_at[:10]})")

        return "\n".join(parts)

    def get_stats(self) -> dict:
        """Get journey statistics."""
        skills = sum(1 for n in self._nodes if n.type == "skill")
        memories = sum(1 for n in self._nodes if n.type == "memory")
        return {
            "total_nodes": len(self._nodes),
            "skills": skills,
            "memories": memories,
        }
