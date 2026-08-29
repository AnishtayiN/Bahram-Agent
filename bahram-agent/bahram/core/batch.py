"""Batch processing for Bahram Agent."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BatchJob:
    """A batch processing job."""

    id: str
    prompts: list[str]
    model: str = ""
    output_dir: str = "data/batch"
    status: str = "pending"
    results: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BatchProcessor:
    """Batch processing for multiple prompts."""

    def __init__(self, output_dir: str = "data/batch") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, BatchJob] = {}

    async def process_batch(
        self,
        prompts: list[str],
        model: str = "",
        max_concurrent: int = 5,
        callback: Any = None,
    ) -> BatchJob:
        """Process a batch of prompts."""
        import uuid

        job_id = str(uuid.uuid4())[:8]
        job = BatchJob(
            id=job_id,
            prompts=prompts,
            model=model,
        )
        self.jobs[job_id] = job

        logger.info(f"Starting batch job {job_id} with {len(prompts)} prompts")

        # Process prompts concurrently
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_prompt(idx: int, prompt: str):
            async with semaphore:
                try:
                    # This is a placeholder - use actual agent in production
                    result = {
                        "index": idx,
                        "prompt": prompt,
                        "response": f"Response to: {prompt[:100]}",
                        "status": "success",
                        "timestamp": datetime.now().isoformat(),
                    }
                    job.results.append(result)

                    if callback:
                        await callback(result)

                except Exception as e:
                    logger.error(f"Error processing prompt {idx}: {e}")
                    job.results.append({
                        "index": idx,
                        "prompt": prompt,
                        "error": str(e),
                        "status": "error",
                    })

        # Run all prompts
        tasks = [process_prompt(i, p) for i, p in enumerate(prompts)]
        await asyncio.gather(*tasks)

        # Save results
        job.status = "completed"
        job.completed_at = datetime.now().isoformat()
        self._save_results(job)

        logger.info(f"Batch job {job_id} completed: {len(job.results)} results")
        return job

    def _save_results(self, job: BatchJob) -> None:
        """Save batch results to file."""
        output_file = self.output_dir / f"batch_{job.id}.json"

        data = {
            "id": job.id,
            "model": job.model,
            "status": job.status,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "total_prompts": len(job.prompts),
            "results": job.results,
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get a batch job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[BatchJob]:
        """List all batch jobs."""
        return list(self.jobs.values())

    def export_sharegpt(self, job_id: str) -> str:
        """Export batch results in ShareGPT format."""
        job = self.jobs.get(job_id)
        if not job:
            return ""

        conversations = []
        for result in job.results:
            if result.get("status") == "success":
                conversations.append({
                    "conversations": [
                        {"from": "human", "value": result["prompt"]},
                        {"from": "gpt", "value": result["response"]},
                    ],
                    "metadata": {
                        "model": job.model,
                        "timestamp": result.get("timestamp"),
                    },
                })

        output_file = self.output_dir / f"sharegpt_{job_id}.json"
        with open(output_file, "w") as f:
            json.dump(conversations, f, indent=2)

        return str(output_file)

    def get_statistics(self, job_id: str) -> dict:
        """Get batch job statistics."""
        job = self.jobs.get(job_id)
        if not job:
            return {}

        successful = sum(1 for r in job.results if r.get("status") == "success")
        failed = sum(1 for r in job.results if r.get("status") == "error")

        return {
            "total": len(job.results),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(job.results) if job.results else 0,
        }
