from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DBConfig:

    db_type: str
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    user: str = ""
    password: str = ""

class DatabaseTool:

    def __init__(self, config: DBConfig = None) -> None:
        self.config = config
        self._connection = None

    async def connect(self) -> bool:
        if not self.config:
            return False

        try:
            if self.config.db_type == "sqlite":
                return await self._connect_sqlite()
            elif self.config.db_type == "postgresql":
                return await self._connect_postgresql()
            elif self.config.db_type == "mysql":
                return await self._connect_mysql()
            return False
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    async def _connect_sqlite(self) -> bool:
        try:
            import aiosqlite
            self._connection = await aiosqlite.connect(self.config.database)
            return True
        except ImportError:
            logger.warning("aiosqlite not installed")
            return False

    async def _connect_postgresql(self) -> bool:
        try:
            import asyncpg
            self._connection = await asyncpg.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )
            return True
        except ImportError:
            logger.warning("asyncpg not installed")
            return False

    async def _connect_mysql(self) -> bool:
        try:
            import aiomysql
            self._connection = await aiomysql.connect(
                host=self.config.host,
                port=self.config.port,
                db=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )
            return True
        except ImportError:
            logger.warning("aiomysql not installed")
            return False

    async def execute(self, query: str, params: tuple = None) -> list[dict]:
        if not self._connection:
            return []

        try:
            if self.config.db_type == "sqlite":
                cursor = await self._connection.execute(query, params or ())
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                return [dict(zip(columns, row)) for row in rows]
            elif self.config.db_type == "postgresql":
                rows = await self._connection.fetch(query, *(params or ()))
                return [dict(row) for row in rows]
            elif self.config.db_type == "mysql":
                async with self._connection.cursor() as cursor:
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    return [dict(zip(columns, row)) for row in rows]
            return []
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return []

    async def insert(self, table: str, data: dict) -> bool:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" if self.config.db_type == "sqlite" else "%s"] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        return await self.execute(query, tuple(data.values())) is not None

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None
