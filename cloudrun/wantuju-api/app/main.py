"""CloudBase Run Wantuju API entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.admin.routes import router as admin_router
from app.api import features, miniapp, share_rewards, tasks, transactions, users
from app.cloudbase.client import CloudBaseError
from app.core.logging import configure_logging, request_log_middleware
from app.services.job_queue import job_queue
from app.services.tasks import TaskService


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await job_queue.start()
    try:
        recovered = await TaskService().recover_unfinished_jobs()
        if recovered:
            logger.info("[恢复任务] %s 个任务已重新入队", recovered)
    except CloudBaseError:
        logger.exception("[恢复任务失败] CloudBase 暂不可用，服务继续启动")
    try:
        yield
    finally:
        await job_queue.stop()


app = FastAPI(title="Wantuju API", version="0.1.0", lifespan=lifespan)
app.middleware("http")(request_log_middleware)
app.include_router(miniapp.router)
app.include_router(features.router)
app.include_router(users.router)
app.include_router(share_rewards.router)
app.include_router(transactions.router)
app.include_router(tasks.router)
app.include_router(admin_router, prefix="/admin")
