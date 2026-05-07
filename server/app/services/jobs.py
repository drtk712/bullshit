"""Generation job orchestration."""
from __future__ import annotations

import asyncio
import logging

from app.cloudbase.nosql import get_point_ledger, get_poster_job_store
from app.cloudbase.storage import get_storage
from app.services.poster import download_image_bytes, extract_url_from_response, generate_poster, guess_ext_from_url, mask_url


logger = logging.getLogger(__name__)


async def process_job(
    task_id: str,
    image_url: str,
    source_file_id: str,
    job_type: str,
    generation_prompt: str,
    is_test: bool = False,
    test_poster_file_id: str | None = None,
) -> None:
    """Process one accepted generation job and persist the final state."""
    job_store = get_poster_job_store()
    try:
        await asyncio.to_thread(job_store.update_job, task_id, {"status": "processing", "errMsg": ""})

        if is_test:
            poster_file_id = (
                test_poster_file_id
                or "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-posters/0274fd6869f6176c00082cfb0eeefd94.png"
            )
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
            logger.info("[任务完成] task_id=%s, mode=TEST, posterFileID=%s", task_id, mask_url(poster_file_id))
            return

        poster_content = await asyncio.to_thread(generate_poster, image_url, job_type, generation_prompt)
        poster_url = extract_url_from_response(poster_content)
        image_bytes = await asyncio.to_thread(download_image_bytes, poster_url)
        ext = guess_ext_from_url(poster_url)
        poster_object_id = f"ai-posters/{task_id}{ext}"
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

    except Exception as exc:
        logger.error("[任务失败] task_id=%s, 错误: %s", task_id, exc)
        await asyncio.to_thread(mark_job_failed_with_refund, task_id, str(exc))


def accept_job(task_id: str) -> tuple[dict, bool]:
    """Accept an init task and charge points in the same transaction."""
    return get_point_ledger().accept_job(task_id, 1)


def mark_job_failed_with_refund(task_id: str, err_msg: str) -> None:
    """Refund a failed job, then persist failed status."""
    try:
        get_point_ledger().refund_failed_job(task_id, err_msg, 1)
    except Exception as exc:
        logger.error("[失败结算异常] task_id=%s, 错误: %s", task_id, exc)
        get_poster_job_store().update_job(
            task_id,
            {
                "status": "failed",
                "errMsg": err_msg,
                "refundErrMsg": str(exc),
            },
        )
