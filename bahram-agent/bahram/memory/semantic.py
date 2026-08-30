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
    scope: str = "global"


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
        self._migrate()
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                timestamp REAL DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                scope TEXT DEFAULT 'global',
                importance REAL DEFAULT 0.5,
                confidence REAL DEFAULT 1.0,
                access_count INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
            CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp);
        """)
        try:
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope)")
        except Exception:
            pass
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

    def _migrate(self) -> None:
        try:
            cursor = self._conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
            if not cursor.fetchone():
                return
            cursor = self._conn.execute("PRAGMA table_info(memories)")
            columns = {row[1] for row in cursor.fetchall()}
            if "scope" not in columns:
                self._conn.execute("ALTER TABLE memories ADD COLUMN scope TEXT DEFAULT 'global'")
            if "importance" not in columns:
                self._conn.execute("ALTER TABLE memories ADD COLUMN importance REAL DEFAULT 0.5")
            if "confidence" not in columns:
                self._conn.execute("ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 1.0")
            if "access_count" not in columns:
                self._conn.execute("ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0")
            self._conn.commit()
        except Exception as e:
            logger.debug(f"Migration skipped: {e}")

    def add(
        self, content: str, source: str = "", metadata: dict = None,
        scope: str = "global", importance: float = 0.5, confidence: float = 1.0,
    ) -> str:
        memory_id = str(uuid.uuid4())[:12]
        self._conn.execute(
            "INSERT INTO memories (id, content, source, timestamp, metadata, scope, importance, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (memory_id, content, source, time.time(), "{}" if not metadata else str(metadata),
             scope, importance, confidence),
        )
        self._conn.commit()
        return memory_id

    def search(
        self, query: str, limit: int = 10, min_score: float = 0.0,
        scope: str | None = None,
    ) -> list[MemoryResult]:
        results = []
        scope_clause = ""
        scope_params: list[Any] = []
        if scope:
            scope_clause = " AND scope = ?"
            scope_params = [scope]
        try:
            rows = self._conn.execute(
                "SELECT m.id, m.content, m.source, m.timestamp, m.metadata, m.scope, "
                "rank FROM memories_fts f JOIN memories m ON f.rowid = m.rowid "
                "WHERE memories_fts MATCH ?" + scope_clause + " ORDER BY rank LIMIT ?",
                (query, *scope_params, limit),
            ).fetchall()
            for row in rows:
                score = abs(row[5]) if row[5] else 0.0
                if score >= min_score:
                    results.append(MemoryResult(
                        id=row[0], content=row[1], score=score,
                        source=row[2], timestamp=row[3], scope=row[5] if len(row) > 5 else "global",
                    ))
        except Exception:
            query_lower = f"%{query}%"
            sql = ("SELECT id, content, source, timestamp, metadata, scope FROM memories "
                   "WHERE (content LIKE ? OR source LIKE ?)" + scope_clause +
                   " ORDER BY timestamp DESC LIMIT ?")
            params: list[Any] = [query_lower, query_lower, *scope_params, limit]
            rows = self._conn.execute(sql, params).fetchall()
            for row in rows:
                results.append(MemoryResult(
                    id=row[0], content=row[1], score=0.5,
                    source=row[2], timestamp=row[3], scope=row[5] if len(row) > 5 else "global",
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
        scopes = [r[0] for r in self._conn.execute("SELECT DISTINCT scope FROM memories").fetchall()]
        return {"total_memories": count, "sources": sources, "scopes": scopes}

    def consolidate(self, max_age_hours: int = 168, min_confidence: float = 0.1) -> int:
        cutoff = time.time() - (max_age_hours * 3600)
        cur = self._conn.execute(
            "DELETE FROM memories WHERE timestamp < ? AND confidence < ?",
            (cutoff, min_confidence),
        )
        self._conn.commit()
        return cur.rowcount

    def decay(self, decay_rate: float = 0.99) -> int:
        cur = self._conn.execute(
            "UPDATE memories SET confidence = confidence * ? WHERE confidence > 0.1",
            (decay_rate,),
        )
        self._conn.commit()
        return cur.rowcount

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        rows = self.search(query=user_id, limit=20, scope="user")
        profile = {"user_id": user_id, "preferences": [], "conventions": [], "facts": []}
        for r in rows:
            if "preference" in r.source.lower():
                profile["preferences"].append(r.content[:200])
            elif "convention" in r.source.lower():
                profile["conventions"].append(r.content[:200])
            else:
                profile["facts"].append(r.content[:200])
        return profile

    def store_user_profile(self, user_id: str, key: str, value: str) -> str:
        return self.add(
            content=f"{key}: {value}",
            source=f"user_profile_{user_id}",
            scope="user",
            importance=0.7,
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
