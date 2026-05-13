"""Generation job orchestration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.cloudbase.nosql import get_point_ledger, get_poster_job_store
from app.cloudbase.storage import get_storage
from app.core.logging import compact_error, log_event
from app.services.image_tools import process_image_tool
from app.services.poster import download_image_bytes, extract_url_from_response, generate_poster, guess_ext_from_url, mask_url


logger = logging.getLogger(__name__)


async def process_job(
    task_id: str,
    image_url: str,
    source_file_id: str,
    job_type: str,
    generation_prompt: str,
    param: dict[str, Any] | None = None,
    image_urls: list[str] | None = None,
    source_file_ids: list[str] | None = None,
) -> None:
    job_store = get_poster_job_store()
    try:
        log_event(logger, "job_processing_started", task_id=task_id, type=job_type)
        if job_type in {"split", "long_image"}:
            tool_result = await asyncio.to_thread(
                process_image_tool,
                job_type,
                task_id,
                image_urls or [image_url],
                param or {},
                get_storage(),
            )
            await asyncio.to_thread(
                job_store.update_job,
                task_id,
                {
                    "status": "completed",
                    "posterFileID": tool_result.poster_file_id,
                    "resultMode": tool_result.result_mode,
                    "resultFileIDs": tool_result.result_file_ids,
                    "errMsg": "",
                    "sourceFileID": source_file_id,
                    "sourceFileIDs": source_file_ids or [source_file_id],
                },
            )
            logger.info("[工具任务完成] task_id=%s, type=%s, posterFileID=%s", task_id, job_type, mask_url(tool_result.poster_file_id))
            log_event(logger, "job_completed", task_id=task_id, type=job_type, mode=tool_result.result_mode, result_count=len(tool_result.result_file_ids or []))
            return

        poster_content = await asyncio.to_thread(generate_poster, image_url, job_type, generation_prompt)
        log_event(logger, "job_model_completed", task_id=task_id, type=job_type)
        poster_url = extract_url_from_response(poster_content)
        image_bytes = await asyncio.to_thread(download_image_bytes, poster_url)
        ext = guess_ext_from_url(poster_url)
        poster_object_id = f"posters/{task_id}{ext}"
        poster_file_id = await asyncio.to_thread(get_storage().upload_bytes, poster_object_id, image_bytes)
        await asyncio.to_thread(
            job_store.update_job,
            task_id,
            {
                "status": "completed",
                "posterFileID": poster_file_id,
                "errMsg": "",
                "sourceFileID": source_file_id,
            },
        )
        logger.info("[任务完成] task_id=%s, posterFileID=%s", task_id, mask_url(poster_file_id))
        log_event(logger, "job_completed", task_id=task_id, type=job_type, poster=mask_url(poster_file_id))

    except Exception as exc:
        logger.error("[任务失败] task_id=%s, 错误: %s", task_id, exc)
        log_event(logger, "job_failed", task_id=task_id, type=job_type, error=compact_error(exc))
        await asyncio.to_thread(mark_job_failed_with_refund, task_id, str(exc))


def mark_job_failed_with_refund(task_id: str, err_msg: str) -> None:
    try:
        get_point_ledger().refund_failed_job(task_id, err_msg, 1)
        log_event(logger, "job_refunded", task_id=task_id, error=compact_error(err_msg))
    except Exception as exc:
        logger.error("[失败结算异常] task_id=%s, 错误: %s", task_id, exc)
        log_event(logger, "job_refund_failed", task_id=task_id, error=compact_error(exc))
        get_poster_job_store().update_job(
            task_id,
            {
                "status": "failed",
                "errMsg": err_msg,
                "refundErrMsg": str(exc),
            },
        )
