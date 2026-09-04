"""
Batch.

Public objects: ``BatchItem``, ``BatchProcessor``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BatchItem:
    """
    Batch item.

    Attributes:
        id (str): id string.
        data (Any): data.
        status (str): status string.
        result (Any): result.
        error (str): error string.
    """

    id: str
    data: Any
    status: str = "pending"
    result: Any = None
    error: str = ""


class BatchProcessor:
    """
    Batch processor.
    """

    def __init__(self, batch_size: int = 10, max_concurrent: int = 3) -> None:
        """
        Initialise a BatchProcessor instance.

        Args:
            batch_size (int): numeric value for batch size. Defaults to ``10``.
            max_concurrent (int): numeric value for max concurrent. Defaults to ``3``.
        """
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self._queue: list[BatchItem] = []
        self._results: list[BatchItem] = []

    def add_item(self, id: str, data: Any) -> None:
        """
        Add item.

        Args:
            id (str): id string.
            data (Any): data.
        """
        self._queue.append(BatchItem(id=id, data=data))

    def add_items(self, items: list[tuple[str, Any]]) -> None:
        """
        Add items.

        Args:
            items (list[tuple[str, Any]]): collection of items.
        """
        for id, data in items:
            self.add_item(id, data)

    async def process(
        self,
        processor: Callable,
        **kwargs,
    ) -> list[dict]:
        """
        Process.

        Args:
            processor (Callable): callable used for processor.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).

        Note:
            Coroutine - must be awaited.
        """
        self._results = []
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_item(item: BatchItem) -> BatchItem:
            async with semaphore:
                item.status = "processing"
                try:
                    item.result = await processor(item.data, **kwargs)
                    item.status = "completed"
                except Exception as e:
                    item.error = str(e)
                    item.status = "failed"
                    logger.warning(f"Batch item {item.id} failed: {e}")
                return item

        for i in range(0, len(self._queue), self.batch_size):
            batch = self._queue[i : i + self.batch_size]
            tasks = [process_item(item) for item in batch]
            results = await asyncio.gather(*tasks)
            self._results.extend(results)

        self._queue.clear()

        return [
            {
                "id": r.id,
                "status": r.status,
                "result": r.result,
                "error": r.error,
            }
            for r in self._results
        ]

    def get_statistics(self) -> dict[str, Any]:
        """
        Return the statistics.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        total = len(self._results)
        completed = sum(1 for r in self._results if r.status == "completed")
        failed = sum(1 for r in self._results if r.status == "failed")
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "success_rate": (completed / total * 100) if total > 0 else 0,
        }

    def clear(self) -> None:
        """
        Clear.
        """
        self._queue.clear()
        self._results.clear()
