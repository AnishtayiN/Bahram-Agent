from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class MemoryResult:
    id: str
    content: str
    score: float
    source: str
    timestamp: float
    metadata: dict = field(default_factory=dict)


class SemanticMemory:
    def __init__(self, data_dir: str = "data/memory") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.data_dir / "memory.db"
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                timestamp REAL DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
            CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp);
        """)
        try:
            self._conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content, source,
                    content='memories',
                    content_rowid='rowid'
                );
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content, source)
                    VALUES (new.rowid, new.content, new.source);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, source)
                    VALUES ('delete', old.rowid, old.content, old.source);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, source)
                    VALUES ('delete', old.rowid, old.content, old.source);
                    INSERT INTO memories_fts(rowid, content, source)
                    VALUES (new.rowid, new.content, new.source);
                END;
            """)
        except Exception as e:
            logger.warning(f"FTS5 not available, using LIKE fallback: {e}")
        self._conn.commit()

    def add(self, content: str, source: str = "", metadata: dict = None) -> str:
        memory_id = str(uuid.uuid4())[:12]
        self._conn.execute(
            "INSERT INTO memories (id, content, source, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
            (memory_id, content, source, time.time(), "{}" if not metadata else str(metadata)),
        )
        self._conn.commit()
        return memory_id

    def search(self, query: str, limit: int = 10, min_score: float = 0.0) -> list[MemoryResult]:
        results = []
        try:
            rows = self._conn.execute(
                "SELECT id, content, source, timestamp, metadata, "
                "rank FROM memories_fts WHERE memories_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (query, limit),
            ).fetchall()
            for row in rows:
                score = abs(row[5]) if row[5] else 0.0
                if score >= min_score:
                    results.append(MemoryResult(
                        id=row[0], content=row[1], score=score,
                        source=row[2], timestamp=row[3],
                    ))
        except Exception:
            query_lower = f"%{query}%"
            rows = self._conn.execute(
                "SELECT id, content, source, timestamp, metadata FROM memories "
                "WHERE content LIKE ? OR source LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (query_lower, query_lower, limit),
            ).fetchall()
            for row in rows:
                results.append(MemoryResult(
                    id=row[0], content=row[1], score=0.5,
                    source=row[2], timestamp=row[3],
                ))
        return results

    def get(self, memory_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT id, content, source, timestamp, metadata FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()
        if row:
            return {"id": row[0], "content": row[1], "source": row[2], "timestamp": row[3], "metadata": row[4]}
        return None

    def delete(self, memory_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def get_context(self, query: str, max_memories: int = 5) -> str:
        results = self.search(query, limit=max_memories)
        if not results:
            return ""
        return "\n".join(f"[{r.source}] {r.content[:200]}" for r in results)

    def get_statistics(self) -> dict[str, Any]:
        count = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        sources = [r[0] for r in self._conn.execute("SELECT DISTINCT source FROM memories").fetchall()]
        return {"total_memories": count, "sources": sources}

    def close(self) -> None:
        if self._conn:
            self._conn.close()
