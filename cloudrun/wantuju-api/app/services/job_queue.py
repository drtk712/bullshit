"""In-memory queue for generation jobs."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.core.logging import log_event
from app.services.jobs_runtime import process_job, process_job_v2


logger = logging.getLogger(__name__)
MAX_CONCURRENT_JOBS = 5


@dataclass(frozen=True)
class QueuedJob:
    task_id: str
    image_url: str
    source_file_id: str
    job_type: str
    generation_prompt: str
    param: dict[str, Any] | None = None
    image_urls: list[str] | None = None
    source_file_ids: list[str] | None = None
    flow: str = "v1"
    already_claimed: bool = False


class JobQueue:
    def __init__(self, worker_count: int = MAX_CONCURRENT_JOBS) -> None:
        self.worker_count = worker_count
        self.queue: asyncio.Queue[QueuedJob] = asyncio.Queue()
        self.queued_task_ids: set[str] = set()
        self.active_task_ids: set[str] = set()
        self.workers: list[asyncio.Task[None]] = []
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        if self.workers:
            return
        self.workers = [
            asyncio.create_task(self._worker(index + 1), name=f"job-worker-{index + 1}")
            for index in range(self.worker_count)
        ]
        logger.info("[队列启动] workers=%s", self.worker_count)

    async def stop(self) -> None:
        for worker in self.workers:
            worker.cancel()
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []
        logger.info("[队列停止]")

    async def enqueue(self, job: QueuedJob) -> bool:
        async with self.lock:
            if job.task_id in self.queued_task_ids or job.task_id in self.active_task_ids:
                log_event(logger, "queue_duplicate", task_id=job.task_id, type=job.job_type)
                return False
            self.queued_task_ids.add(job.task_id)
            await self.queue.put(job)
            log_event(logger, "queue_enqueued", task_id=job.task_id, type=job.job_type, queued=self.queue.qsize(), active=len(self.active_task_ids))
            return True

    async def contains(self, task_id: str) -> bool:
        async with self.lock:
            return task_id in self.queued_task_ids or task_id in self.active_task_ids

    async def _worker(self, worker_id: int) -> None:
        while True:
            job = await self.queue.get()
            async with self.lock:
                self.queued_task_ids.discard(job.task_id)
                self.active_task_ids.add(job.task_id)
            logger.info("[队列取出] worker=%s task_id=%s queued=%s active=%s", worker_id, job.task_id, self.queue.qsize(), len(self.active_task_ids))
            log_event(logger, "queue_dequeued", worker=worker_id, task_id=job.task_id, type=job.job_type, queued=self.queue.qsize(), active=len(self.active_task_ids))
            try:
                try:
                    from app.services.tasks import TaskService

                    if not job.already_claimed:
                        claimed = TaskService().claim_processing_job(job.task_id)
                        if not claimed:
                            logger.info("[队列跳过] worker=%s task_id=%s claim_failed", worker_id, job.task_id)
                            continue
                    processor = process_job_v2 if job.flow == "v2" else process_job
                    await processor(
                        job.task_id,
                        job.image_url,
                        job.source_file_id,
                        job.job_type,
                        job.generation_prompt,
                        job.param,
                        job.image_urls,
                        job.source_file_ids,
                    )
                except Exception:
                    logger.exception("[队列任务异常] worker=%s task_id=%s", worker_id, job.task_id)
            finally:
                async with self.lock:
                    self.active_task_ids.discard(job.task_id)
                self.queue.task_done()

    def stats(self) -> dict[str, Any]:
        return {
            "workerCount": self.worker_count,
            "aliveWorkers": sum(1 for worker in self.workers if not worker.done()),
            "queueSize": self.queue.qsize(),
            "queuedTasks": len(self.queued_task_ids),
            "activeTasks": len(self.active_task_ids),
            "activeTaskIds": sorted(self.active_task_ids),
        }


job_queue = JobQueue()
