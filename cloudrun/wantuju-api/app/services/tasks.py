"""Feature job task service."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import replace
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.cloudbase.storage import CloudBaseStorage
from app.core.config import validation_api_key
from app.core.logging import compact_error, log_event, mask_openid
from app.db import Database, created_id, get_point_ledger
from app.db.repository import row_to_doc
from app.services.features import FeatureService
from app.services.job_queue import QueuedJob, job_queue
from app.services.users import UserService


logger = logging.getLogger(__name__)
FEATURE_JOBS_COLLECTION = "feature_jobs"
TASK_STATUS_FILTERS = {"pending", "processing", "completed", "failed"}
MULTI_IMAGE_TYPES = {"long_image"}
PROCESSING_RECOVERY_AFTER_MS = 15 * 60 * 1000


class JobCreationError(ValueError):
    def __init__(self, message: str, *, cleanup_uploads: bool = False):
        super().__init__(message)
        self.cleanup_uploads = cleanup_uploads


class ValidationServiceError(RuntimeError):
    pass


def to_public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "_id": task.get("_id"),
        "type": task.get("type"),
        "featureTitle": task.get("featureTitle") or "",
        "featureHomeDesc": task.get("featureHomeDesc") or "",
        "featureDescription": task.get("featureDescription") or "",
        "status": task.get("status"),
        "fileID": task.get("fileID") or None,
        "fileIDs": task.get("fileIDs") if isinstance(task.get("fileIDs"), list) else [],
        "posterFileID": task.get("posterFileID") or None,
        "resultMode": task.get("resultMode") or "single",
        "resultFileIDs": task.get("resultFileIDs") if isinstance(task.get("resultFileIDs"), list) else [],
        "errMsg": task.get("errMsg") or "",
        "pointsCost": task.get("pointsCost") or 0,
        "pointsConsumed": bool(task.get("pointsConsumed")),
        "pointsRefunded": bool(task.get("pointsRefunded")),
        "createdAt": task.get("createdAt"),
        "updatedAt": task.get("updatedAt"),
    }


def to_task_status(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": task.get("status"),
        "posterFileID": task.get("posterFileID"),
        "resultMode": task.get("resultMode") or "single",
        "resultFileIDs": task.get("resultFileIDs") if isinstance(task.get("resultFileIDs"), list) else [],
        "errMsg": task.get("errMsg"),
    }


def to_shared_task(task: dict[str, Any], task_id: str) -> dict[str, Any]:
    return {
        "_id": task.get("_id") or task_id,
        "type": task.get("type"),
        "featureTitle": task.get("featureTitle") or "",
        "featureHomeDesc": task.get("featureHomeDesc") or "",
        "featureDescription": task.get("featureDescription") or "",
        "status": task.get("status"),
        "posterFileID": task.get("posterFileID") or None,
        "createdAt": task.get("createdAt"),
    }


class TaskService:
    def __init__(
        self,
        db: Database | None = None,
        storage: CloudBaseStorage | None = None,
        user_service: UserService | None = None,
        feature_service: FeatureService | None = None,
    ):
        self.db = db or Database()
        self.storage = storage or CloudBaseStorage()
        self.user_service = user_service or UserService(self.db)
        self.feature_service = feature_service or FeatureService(self.db)

    async def create_job(
        self,
        openid: str,
        *,
        feature_type: str,
        file_id: str = "",
        file_ids: list[str] | None = None,
        param: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        feature_type = str(feature_type or "").strip()
        normalized_param = normalize_job_param(param)
        is_multi_image = feature_type in MULTI_IMAGE_TYPES
        normalized_file_ids = normalize_file_ids(file_ids if is_multi_image else (file_ids or [file_id]))
        primary_file_id = normalized_file_ids[0] if normalized_file_ids else ""

        if not feature_type or not primary_file_id or (is_multi_image and len(normalized_file_ids) < 2):
            raise JobCreationError("缺少必要参数", cleanup_uploads=True)

        feature_config = self.feature_service.get_enabled_config(feature_type)
        if not feature_config:
            raise JobCreationError("功能暂不可用", cleanup_uploads=True)

        user = self.user_service.ensure_user(openid)
        if int(user.get("points") or 0) < 1:
            raise JobCreationError("积分不足，请先获取积分", cleanup_uploads=True)

        validation = self.validate_image(primary_file_id, feature_config)
        if not validation["passed"]:
            raise JobCreationError(validation["reason"], cleanup_uploads=True)

        image_urls = self.resolve_download_urls(normalized_file_ids)
        image_url = image_urls[0]
        now = int(time.time() * 1000)
        public_config = feature_config.get("public") if isinstance(feature_config.get("public"), dict) else {}
        generation_config = feature_config.get("generation") if isinstance(feature_config.get("generation"), dict) else {}
        prompt = str(generation_config.get("prompt") or "").strip()
        if not prompt and feature_type not in {"split", "long_image"}:
            raise JobCreationError("缺少处理提示词", cleanup_uploads=True)
        rendered_prompt = render_prompt_template(prompt, normalized_param)
        task_doc = {
            "type": feature_type,
            "featureTitle": public_config.get("title") or "",
            "featureHomeDesc": public_config.get("homeDesc") or "",
            "featureDescription": public_config.get("description") or "",
            "param": normalized_param,
            "fileID": primary_file_id,
            "fileIDs": normalized_file_ids,
            "generationPrompt": rendered_prompt,
            "status": "pending",
            "posterFileID": None,
            "resultMode": "single",
            "resultFileIDs": [],
            "errMsg": "",
            "openid": openid,
            "pointsCost": 1,
            "pointsConsumed": True,
            "pointsRefunded": False,
            "consumeTransactionId": None,
            "refundTransactionId": None,
            "createdAt": now,
            "updatedAt": now,
        }
        task_id: str | None = None
        try:
            task_id, _task = get_point_ledger().create_pending_job(task_doc, amount=1)
            log_event(
                logger,
                "task_created",
                task_id=task_id,
                type=feature_type,
                openid=mask_openid(openid),
                file_count=len(normalized_file_ids),
            )
            queued = QueuedJob(
                task_id=task_id,
                image_url=image_url,
                source_file_id=primary_file_id,
                job_type=feature_type,
                generation_prompt=rendered_prompt,
                param=normalized_param,
                image_urls=image_urls,
                source_file_ids=normalized_file_ids,
            )
            if not await job_queue.enqueue(queued):
                raise RuntimeError("任务已在队列中")
            log_event(logger, "task_enqueued", task_id=task_id, type=feature_type, queue_size=job_queue.stats()["queueSize"])
            return {"taskId": task_id}
        except Exception as exc:
            err_msg = str(exc) if isinstance(exc, JobCreationError) else str(exc) or "创建任务失败"
            log_event(logger, "task_create_failed", task_id=task_id or "", type=feature_type, openid=mask_openid(openid), error=compact_error(err_msg))
            if task_id:
                try:
                    get_point_ledger().refund_failed_job(task_id, err_msg, 1)
                except Exception:
                    self.db.update_document(
                        FEATURE_JOBS_COLLECTION,
                        task_id,
                        {
                            "status": "failed",
                            "errMsg": err_msg,
                            "pointsRefunded": False,
                            "refundTransactionId": None,
                            "updatedAt": int(time.time() * 1000),
                        },
                    )
                raise JobCreationError(err_msg) from exc
            raise JobCreationError(err_msg, cleanup_uploads=True) from exc

    async def create_job_v2(
        self,
        openid: str,
        *,
        feature_type: str,
        file_id: str = "",
        file_ids: list[str] | None = None,
        param: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        feature_type = str(feature_type or "").strip()
        normalized_param = normalize_job_param(param)
        is_multi_image = feature_type in MULTI_IMAGE_TYPES
        normalized_file_ids = normalize_file_ids(file_ids if is_multi_image else (file_ids or [file_id]))
        primary_file_id = normalized_file_ids[0] if normalized_file_ids else ""

        if not feature_type or not primary_file_id or (is_multi_image and len(normalized_file_ids) < 2):
            raise JobCreationError("缺少必要参数", cleanup_uploads=True)

        feature_config = self.feature_service.get_enabled_config(feature_type)
        if not feature_config:
            raise JobCreationError("功能暂不可用", cleanup_uploads=True)

        user = self.user_service.ensure_user(openid)
        if int(user.get("points") or 0) < 1:
            raise JobCreationError("积分不足，请先获取积分", cleanup_uploads=True)

        image_urls = self.resolve_download_urls(normalized_file_ids)
        image_url = image_urls[0]
        now = int(time.time() * 1000)
        public_config = feature_config.get("public") if isinstance(feature_config.get("public"), dict) else {}
        generation_config = feature_config.get("generation") if isinstance(feature_config.get("generation"), dict) else {}
        prompt = str(generation_config.get("prompt") or "").strip()
        if not prompt and feature_type not in {"split", "long_image"}:
            raise JobCreationError("缺少处理提示词", cleanup_uploads=True)
        rendered_prompt = render_prompt_template(prompt, normalized_param)
        task_doc = {
            "type": feature_type,
            "flow": "v2",
            "featureTitle": public_config.get("title") or "",
            "featureHomeDesc": public_config.get("homeDesc") or "",
            "featureDescription": public_config.get("description") or "",
            "param": normalized_param,
            "validation": feature_config.get("validation") if isinstance(feature_config.get("validation"), dict) else None,
            "fileID": primary_file_id,
            "fileIDs": normalized_file_ids,
            "generationPrompt": rendered_prompt,
            "status": "pending",
            "posterFileID": None,
            "resultMode": "single",
            "resultFileIDs": [],
            "errMsg": "",
            "openid": openid,
            "pointsCost": 1,
            "pointsConsumed": False,
            "pointsRefunded": False,
            "consumeTransactionId": None,
            "refundTransactionId": None,
            "createdAt": now,
            "updatedAt": now,
        }
        task_id: str | None = None
        try:
            create_result = self.db.insert_documents(FEATURE_JOBS_COLLECTION, [task_doc])
            task_id = created_id(create_result)
            if not task_id:
                raise RuntimeError("创建任务失败")

            log_event(
                logger,
                "task_v2_created",
                task_id=task_id,
                type=feature_type,
                openid=mask_openid(openid),
                file_count=len(normalized_file_ids),
            )
            queued = QueuedJob(
                task_id=task_id,
                image_url=image_url,
                source_file_id=primary_file_id,
                job_type=feature_type,
                generation_prompt=rendered_prompt,
                param=normalized_param,
                image_urls=image_urls,
                source_file_ids=normalized_file_ids,
                flow="v2",
            )
            if not await job_queue.enqueue(queued):
                raise RuntimeError("任务已在队列中")
            log_event(logger, "task_v2_enqueued", task_id=task_id, type=feature_type, queue_size=job_queue.stats()["queueSize"])
            return {"taskId": task_id}
        except Exception as exc:
            err_msg = str(exc) or "创建任务失败"
            log_event(logger, "task_v2_create_failed", task_id=task_id or "", type=feature_type, openid=mask_openid(openid), error=compact_error(err_msg))
            if task_id:
                self.db.update_document(
                    FEATURE_JOBS_COLLECTION,
                    task_id,
                    {
                        "status": "failed",
                        "errMsg": err_msg,
                        "pointsConsumed": False,
                        "pointsRefunded": False,
                        "updatedAt": int(time.time() * 1000),
                    },
                )
                self.cleanup_uploads(normalized_file_ids)
                raise JobCreationError(err_msg) from exc
            raise JobCreationError(err_msg, cleanup_uploads=True) from exc

    def list_tasks(self, openid: str, *, page: int = 1, page_size: int = 5, status_filter: str = "all") -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = min(50, max(1, int(page_size or 5)))
        skip = (page - 1) * page_size
        query: dict[str, Any] = {"openid": openid}

        if status_filter in TASK_STATUS_FILTERS:
            query["status"] = status_filter

        total = self.db.count_documents(FEATURE_JOBS_COLLECTION, query)
        tasks = self.db.find_many(
            FEATURE_JOBS_COLLECTION,
            query,
            sort={"createdAt": -1},
            limit=page_size,
            skip=skip,
        )

        return {
            "tasks": [to_public_task(task) for task in tasks],
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": skip + page_size < total,
        }

    def get_task(self, openid: str, task_id: str) -> dict[str, Any] | None:
        task = self.db.get_document(FEATURE_JOBS_COLLECTION, task_id)
        if not task or task.get("openid") != openid:
            return None
        return to_public_task(task)

    def get_task_status(self, openid: str, task_id: str) -> dict[str, Any] | None:
        task = self.db.get_document(FEATURE_JOBS_COLLECTION, task_id)
        if not task or task.get("openid") != openid:
            return None
        return to_task_status(task)

    def get_shared_task(self, task_id: str) -> dict[str, Any] | None:
        task = self.db.get_document(FEATURE_JOBS_COLLECTION, task_id)
        if not task or task.get("status") != "completed" or not task.get("posterFileID"):
            return None
        return to_shared_task(task, task_id)

    def delete_task(self, openid: str, task_id: str) -> dict[str, str]:
        task = self.db.get_document(FEATURE_JOBS_COLLECTION, task_id)
        if not task or task.get("openid") != openid:
            raise ValueError("任务不存在")

        if task.get("status") in {"pending", "processing"}:
            raise ValueError("进行中的任务不能删除")

        file_ids = [
            task.get("posterFileID"),
            *(
                task.get("resultFileIDs")
                if isinstance(task.get("resultFileIDs"), list)
                else []
            ),
        ]
        try:
            self.storage.delete_objects([item for item in file_ids if item])
        except Exception:
            pass

        self.db.delete_document(FEATURE_JOBS_COLLECTION, task_id)
        log_event(logger, "task_deleted", task_id=task_id, openid=mask_openid(openid), status=task.get("status"))
        return {"taskId": task_id}

    def claim_processing_job(self, task_id: str) -> dict[str, Any] | None:
        now = int(time.time() * 1000)
        token = f"{task_id}:{now}"
        result = self.db.call(
            "wantuju_claim_job",
            {
                "task_id": task_id,
                "token": token,
                "now_ms": now,
                "lease_ms": PROCESSING_RECOVERY_AFTER_MS,
            },
        )
        if not result:
            return None
        fresh_job = row_to_doc(FEATURE_JOBS_COLLECTION, result)
        if fresh_job.get("processingLeaseToken") != token:
            return None
        log_event(logger, "task_claimed_processing", task_id=task_id, type=fresh_job.get("type"), lease_at=now)
        return fresh_job

    async def recover_unfinished_jobs(self, *, limit: int = 50) -> int:
        now = int(time.time() * 1000)
        processing_before = now - PROCESSING_RECOVERY_AFTER_MS
        jobs = self.db.find_many(
            FEATURE_JOBS_COLLECTION,
            {
                "$or": [
                    {"status": "pending"},
                    {"status": "processing", "updatedAt": {"$lt": processing_before}},
                ]
            },
            sort={"createdAt": 1},
            limit=limit,
        )
        recovered = 0
        for job in jobs:
            try:
                claimed = self.claim_processing_job(str(job.get("_id") or ""))
                if not claimed:
                    continue
                queued = self.build_queue_job_from_task(claimed)
            except Exception as exc:
                logger.warning("[任务恢复跳过] task_id=%s error=%s", job.get("_id"), exc)
                continue
            queued = replace(queued, already_claimed=True)
            if await job_queue.enqueue(queued):
                recovered += 1
        return recovered

    def build_queue_job_from_task(self, task: dict[str, Any]) -> QueuedJob:
        file_ids = task.get("fileIDs") if isinstance(task.get("fileIDs"), list) else []
        normalized_file_ids = normalize_file_ids(file_ids or [task.get("fileID")])
        if not normalized_file_ids:
            raise JobCreationError("任务缺少图片")
        image_urls = self.resolve_download_urls(normalized_file_ids)
        prompt = str(task.get("generationPrompt") or "").strip()
        if not prompt and task.get("type") not in {"split", "long_image"}:
            raise JobCreationError("任务缺少处理提示词")
        return QueuedJob(
            task_id=str(task.get("_id") or ""),
            image_url=image_urls[0],
            source_file_id=str(task.get("fileID") or normalized_file_ids[0]),
            job_type=str(task.get("type") or ""),
            generation_prompt=prompt,
            param=task.get("param") if isinstance(task.get("param"), dict) else {},
            image_urls=image_urls,
            source_file_ids=normalized_file_ids,
            flow=str(task.get("flow") or "v1"),
        )

    def validate_image(self, file_id: str, feature_config: dict[str, Any]) -> dict[str, Any]:
        validation_config = feature_config.get("validation")
        if not isinstance(validation_config, dict):
            return {"passed": True, "reason": ""}

        image_url = self.resolve_download_urls([file_id])[0]
        prompt = build_validation_prompt(validation_config.get("prompt"))
        service_url = str(validation_config.get("serviceUrl") or "").strip()
        model = str(validation_config.get("model") or "").strip()
        if not service_url or not model:
            return {"passed": False, "reason": "图片验证配置异常，请稍后重试"}

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 32000,
        }
        request = Request(
            service_url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=validation_request_headers(validation_config),
        )
        try:
            with urlopen(request, timeout=55) as response:
                if response.status != 200:
                    return {"passed": False, "reason": "验证服务响应异常，请稍后重试"}
                data = json.loads(response.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                return {"passed": False, "reason": "图片验证服务异常，请稍后重试"}
            return parse_validation_result(content, validation_config.get("failMessage"))
        except TimeoutError:
            return {"passed": False, "reason": "验证服务超时，请稍后重试"}
        except (HTTPError, URLError, ValueError):
            return {"passed": False, "reason": "验证失败，请稍后重试"}

    def validate_image_with_retry(self, file_id: str, feature_config: dict[str, Any], max_retries: int = 2) -> dict[str, Any]:
        last_error = "验证失败，请稍后重试"
        for attempt in range(1, max(0, max_retries) + 2):
            try:
                return self.validate_image_once(file_id, feature_config)
            except ValidationServiceError as exc:
                last_error = str(exc) or last_error
                log_event(logger, "image_validation_retry", attempt=attempt, max_retries=max_retries, error=compact_error(last_error))
                if attempt <= max_retries:
                    time.sleep(min(2 * attempt, 5))
        return {"passed": False, "reason": last_error}

    def validate_image_once(self, file_id: str, feature_config: dict[str, Any]) -> dict[str, Any]:
        validation_config = feature_config.get("validation")
        if not isinstance(validation_config, dict):
            return {"passed": True, "reason": ""}

        image_url = self.resolve_download_urls([file_id])[0]
        prompt = build_validation_prompt(validation_config.get("prompt"))
        service_url = str(validation_config.get("serviceUrl") or "").strip()
        model = str(validation_config.get("model") or "").strip()
        if not service_url or not model:
            raise ValidationServiceError("图片验证配置异常，请稍后重试")

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 32000,
        }
        request = Request(
            service_url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=validation_request_headers(validation_config),
        )
        try:
            with urlopen(request, timeout=55) as response:
                if response.status != 200:
                    raise ValidationServiceError("验证服务响应异常，请稍后重试")
                data = json.loads(response.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                raise ValidationServiceError("图片验证服务异常，请稍后重试")
            parsed = parse_validation_result(content, validation_config.get("failMessage"))
            if not parsed["passed"] and parsed["reason"] == "验证服务响应格式异常，请稍后重试":
                raise ValidationServiceError(parsed["reason"])
            return parsed
        except TimeoutError as exc:
            raise ValidationServiceError("验证服务超时，请稍后重试") from exc
        except (HTTPError, URLError, ValueError) as exc:
            raise ValidationServiceError("验证失败，请稍后重试") from exc

    def resolve_download_urls(self, file_ids: list[str]) -> list[str]:
        urls = self.storage.get_download_urls(file_ids)
        if len(urls) != len(file_ids) or any(not item for item in urls):
            raise JobCreationError("图片链接生成失败", cleanup_uploads=True)
        return urls

    def cleanup_uploads(self, file_ids: list[str]) -> None:
        try:
            self.storage.delete_objects(file_ids)
        except Exception:
            pass


def validation_request_headers(validation_config: dict[str, Any]) -> dict[str, str]:
    """OpenAI-compatible headers. No key is sent unless one is configured."""
    headers = {"Content-Type": "application/json"}
    api_key = str(validation_config.get("apiKey") or validation_config.get("api_key") or "").strip()
    if not api_key:
        api_key = validation_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def normalize_job_param(input_value: Any) -> dict[str, str]:
    if not isinstance(input_value, dict):
        return {}

    result: dict[str, str] = {}
    for key, value in input_value.items():
        key_text = str(key or "")
        if not re.fullmatch(r"[a-zA-Z0-9_]{1,32}", key_text):
            continue
        value_text = str(value or "").strip()
        if value_text:
            result[key_text] = value_text[:200]
    return result


def normalize_file_ids(input_value: Any) -> list[str]:
    values = input_value if isinstance(input_value, list) else [input_value]
    result = []
    for item in values:
        text = str(item or "").strip()
        if text.startswith("cloud://"):
            result.append(text)
    return result[:9]


def strip_thinking_text(content: str) -> str:
    answer_text = str(content or "")
    tag_index = answer_text.rfind("</think>")
    if tag_index > -1:
        answer_text = answer_text[tag_index + len("</think>"):]
    return answer_text.strip()


def build_validation_prompt(requirement: Any) -> str:
    return f"""
快速的分析这张图片是否符合下面的要求。
要求：{str(requirement or "").strip()}

如果符合，请只回答：
是

如果不符合，请回答：
否｜原因：一句简短中文原因,不超过40个中文字符
""".strip()


def parse_validation_result(content: str, fallback_reason: Any = None) -> dict[str, Any]:
    fallback = str(fallback_reason or "图片不符合要求，请重新上传")
    text = "".join(line.strip() for line in strip_thinking_text(content).replace("\r", "\n").split("\n") if line.strip())
    if text.startswith("是"):
        return {"passed": True, "reason": ""}
    if text.startswith("否"):
        reason_match = re.search(r"原因\s*[:：]\s*(.+)$", text) or re.search(r"^否\s*[|｜]\s*(.+)$", text)
        raw_reason = str(reason_match.group(1) if reason_match else "")
        reason = re.sub(r"^原因\s*[:：]\s*", "", raw_reason).strip()[:40]
        return {"passed": False, "reason": reason or fallback}
    return {"passed": False, "reason": "验证服务响应格式异常，请稍后重试"}


def render_prompt_template(prompt: str, param: dict[str, Any] | None = None) -> str:
    values = param or {}

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = values.get(key)
        if value is None:
            value = ""
        return str(value).strip()

    return re.sub(r"\$\{([a-zA-Z0-9_]+)\}", replace, prompt)
