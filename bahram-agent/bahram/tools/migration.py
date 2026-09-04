"""
Migration.

Public objects: ``MigrationRule``, ``CodeMigration``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MigrationRule:
    """
    Migration rule.

    Attributes:
        name (str): name of the object.
        source_pattern (str): source pattern string.
        target_pattern (str): target pattern string.
        language (str): language string.
        description (str): human readable description.
    """

    name: str
    source_pattern: str
    target_pattern: str
    language: str
    description: str = ""


class CodeMigration:
    """
    Code migration.
    """

    def __init__(self) -> None:
        """
        Initialise a CodeMigration instance.
        """
        self._rules: dict[str, list[MigrationRule]] = {
            "python2_to_3": [
                MigrationRule(
                    "print_function",
                    r"print\s+(.+)",
                    r"print(\1)",
                    "python",
                    "Convert print statement to function",
                ),
                MigrationRule(
                    "except_syntax",
                    r"except\s+(\w+)\s*,\s*(\w+)",
                    r"except \1 as \2",
                    "python",
                    "Convert except syntax",
                ),
                MigrationRule(
                    "unicode_literal", r"u\"(.+)\"", r"\"\1\"", "python", "Remove unicode prefix"
                ),
                MigrationRule(
                    "xrange", r"xrange\(", r"range(", "python", "Replace xrange with range"
                ),
                MigrationRule(
                    "raw_input", r"raw_input\(", r"input(", "python", "Replace raw_input with input"
                ),
            ],
            "fastapi_migration": [
                MigrationRule(
                    "router",
                    r"@app\.(get|post|put|delete)\(",
                    r"@router.\1(",
                    "python",
                    "Migrate to router-based routing",
                ),
            ],
            "pydantic_v1_to_v2": [
                MigrationRule(
                    "validator",
                    r"@validator\((.+)\)",
                    r"@field_validator(\1, mode='before')",
                    "python",
                    "Migrate Pydantic v1 to v2",
                ),
                MigrationRule(
                    "class_config",
                    r"class Config:",
                    r"model_config = ConfigDict(",
                    "python",
                    "Migrate Config class",
                ),
            ],
        }

    async def migrate(
        self,
        source_path: str,
        target_path: str,
        migration_type: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Migrate.

        Args:
            source_path (str): source path string.
            target_path (str): target path string.
            migration_type (str): migration type string.
            dry_run (bool): when ``True`` nothing is written. Defaults to ``False``.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        rules = self._rules.get(migration_type, [])
        if not rules:
            return {"error": f"Unknown migration type: {migration_type}"}

        source = Path(source_path)
        if not source.exists():
            return {"error": f"Source path not found: {source_path}"}

        if source.is_file():
            return await self._migrate_file(source, target_path, rules, dry_run)
        else:
            return await self._migrate_directory(source, target_path, rules, dry_run)

    async def _migrate_file(
        self,
        source: Path,
        target_path: str,
        rules: list[MigrationRule],
        dry_run: bool,
    ) -> dict[str, Any]:
        try:
            content = source.read_text(errors="replace")
            changes = []

            for rule in rules:
                if rule.language == "python" or source.suffix == ".py":
                    new_content = re.sub(rule.source_pattern, rule.target_pattern, content)
                    if new_content != content:
                        changes.append(
                            {
                                "rule": rule.name,
                                "description": rule.description,
                                "count": len(re.findall(rule.source_pattern, content)),
                            }
                        )
                        content = new_content

            target = Path(target_path)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)

            return {
                "source": str(source),
                "target": target_path,
                "changes": changes,
                "total_changes": sum(c["count"] for c in changes),
                "dry_run": dry_run,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _migrate_directory(
        self,
        source: Path,
        target_path: str,
        rules: list[MigrationRule],
        dry_run: bool,
    ) -> dict[str, Any]:
        results = []
        for py_file in source.rglob("*.py"):
            rel_path = py_file.relative_to(source)
            target_file = Path(target_path) / rel_path
            result = await self._migrate_file(py_file, str(target_file), rules, dry_run)
            results.append(result)

        return {
            "files_migrated": len(results),
            "total_changes": sum(r.get("total_changes", 0) for r in results),
            "results": results,
        }

    def get_migration_types(self) -> list[str]:
        """
        Return the migration types.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return list(self._rules.keys())

    def get_rules(self, migration_type: str) -> list[dict]:
        """
        Return the rules.

        Args:
            migration_type (str): migration type string.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        rules = self._rules.get(migration_type, [])
        return [
            {
                "name": r.name,
                "description": r.description,
                "source": r.source_pattern,
                "target": r.target_pattern,
            }
            for r in rules
        ]
