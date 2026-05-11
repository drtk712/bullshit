"""FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from typing import Any

import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.admin.routes import router as admin_router
from app.config import settings
from app.services.job_queue import QueuedJob, job_queue
from app.services.jobs import accept_job
from app.services.poster import mask_url


IMAGE_TOOL_TYPES = {"split", "long_image"}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await job_queue.start()
    try:
        yield
    finally:
        await job_queue.stop()


app = FastAPI(title="Feature Poster Generator", lifespan=lifespan)
app.include_router(admin_router, prefix="/admin")


class JobRequest(BaseModel):
    taskId: str
    imageUrl: str
    imageUrls: list[str] | None = None
    sourceFileID: str
    sourceFileIDs: list[str] | None = None
    type: str
    generationPrompt: str
    param: dict[str, Any] | None = None
    test: bool = False
    testPosterFileID: str | None = None


@app.post("/api/job")
async def create_job(
    job: JobRequest,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    """Accept a mini-program generation task and enqueue local processing."""
    if not settings.poster_server_token or x_internal_token != settings.poster_server_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", job.type):
        raise HTTPException(status_code=400, detail="无效的类型参数")

    prompt = render_prompt_template(job.generationPrompt.strip(), job.param)
    if not prompt and job.type not in IMAGE_TOOL_TYPES:
        raise HTTPException(status_code=400, detail="缺少生成提示词")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="生成提示词过长")

    logger.info("[请求入参] POST /api/job taskId=%s type=%s imageUrl=%s test=%s", job.taskId, job.type, mask_url(job.imageUrl), job.test)

    try:
        accepted_task, should_enqueue = await asyncio.to_thread(accept_job, job.taskId)
    except ValueError as exc:
        logger.warning("[任务拒绝] task_id=%s, reason=%s", job.taskId, exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not should_enqueue:
        status = str(accepted_task.get("status") or "")
        if status == "pending" and not await job_queue.contains(job.taskId):
            logger.warning("[任务恢复入队] task_id=%s status=pending", job.taskId)
        else:
            logger.info("[任务已接管] task_id=%s, status=%s", job.taskId, accepted_task.get("status"))
            return {"taskId": job.taskId, "accepted": True, "alreadyAccepted": True, **job_queue.stats()}

    queued_job = QueuedJob(
        task_id=job.taskId,
        image_url=job.imageUrl,
        source_file_id=job.sourceFileID,
        job_type=job.type,
        generation_prompt=prompt,
        param=job.param,
        image_urls=job.imageUrls,
        source_file_ids=job.sourceFileIDs,
        is_test=job.test,
        test_poster_file_id=job.testPosterFileID,
    )
    queued = await job_queue.enqueue(queued_job)
    if not queued:
        logger.info("[任务已接管] task_id=%s, status=%s", job.taskId, accepted_task.get("status"))
        return {"taskId": job.taskId, "accepted": True, "alreadyQueued": True, **job_queue.stats()}

    logger.info("[任务入队] task_id=%s, type=%s, status=%s, test=%s, queue=%s", job.taskId, job.type, accepted_task.get("status"), job.test, job_queue.stats())
    return {"taskId": job.taskId, "accepted": True, **job_queue.stats()}


def render_prompt_template(prompt: str, param: dict[str, Any] | None = None) -> str:
    """Render simple ${key} placeholders in generation prompts."""
    values = param or {}

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = values.get(key)
        if value is None:
            value = ""
        return str(value).strip()

    return re.sub(r"\$\{([a-zA-Z0-9_]+)\}", replace, prompt)


@app.get("/health")
async def health_check():
    """Health check for the local server and upstream model endpoint."""
    api_available = True
    try:
        resp = requests.get(settings.memefast_api_url.replace("/v1/chat/completions", ""), timeout=5)
        api_available = resp.status_code < 500
    except requests.exceptions.RequestException:
        api_available = False

    return {
        "status": "ok" if api_available else "degraded",
        "timestamp": time.time(),
        "api": api_available,
        **job_queue.stats(),
    }
