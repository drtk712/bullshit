"""微信小程序 AI 图片生成服务端"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel
import requests
import time
import logging
import re
import asyncio
import os
import uuid

# 配置（从环境变量读取）
MEMEFAST_API_KEY = os.environ.get("MEMEFAST_API_KEY", "")
MEMEFAST_API_URL = os.environ.get("MEMEFAST_API_URL", "https://memefast.top/v1/chat/completions")
MEMEFAST_MODEL = os.environ.get("MEMEFAST_MODEL", "gpt-image-2-all")
POSTER_SERVER_TOKEN = os.environ.get("POSTER_SERVER_TOKEN", "")

if not MEMEFAST_API_KEY:
    raise RuntimeError("MEMEFAST_API_KEY 环境变量未设置")

if not POSTER_SERVER_TOKEN:
    raise RuntimeError("POSTER_SERVER_TOKEN 环境变量未设置")

# 任务存储（线程安全）
_tasks: dict[str, dict] = {}
_tasks_lock = asyncio.Lock()

# 任务过期时间（秒）
TASK_EXPIRE_SECONDS = 3600  # 1小时

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Poster Generator")


class JobRequest(BaseModel):
    imageUrl: str
    type: str
    generationPrompt: str
    test: bool = False  # 测试模式，不调用API
    testPosterFileID: str | None = None


class JobCreateResponse(BaseModel):
    taskId: str


class JobStatusResponse(BaseModel):
    status: str  # "pending", "processing", "completed", "failed"
    posterUrl: str | None = None
    errMsg: str | None = None


def mask_url(url: str) -> str:
    """脱敏 URL，只显示域名和路径前缀"""
    if not url:
        return ""
    try:
        parsed = url.split("/")
        domain = parsed[2] if len(parsed) > 2 else "unknown"
        return f"{domain}/..."
    except:
        return url[:20] + "..."


def generate_poster(image_url: str, job_type: str, generation_prompt: str) -> str:
    """调用大模型生成海报"""

    prompt = generation_prompt

    logger.info("[海报生成] 类型: %s, 图片: %s", job_type, mask_url(image_url))
    
    try:
        resp = requests.post(
            MEMEFAST_API_URL,
            json={
                "model": MEMEFAST_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt}
                    ]
                }],
                "stream": False
            },
            headers={
                "Authorization": f"Bearer {MEMEFAST_API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=180
        )
    except requests.exceptions.Timeout:
        raise Exception("API 请求超时（180秒），请稍后重试")
    except requests.exceptions.ConnectionError:
        raise Exception("无法连接到 API 服务，请检查网络")
    except requests.exceptions.RequestException as e:
        raise Exception(f"API 请求失败: {str(e)}")
    
    if resp.status_code != 200:
        error_detail = ""
        try:
            error_data = resp.json()
            error_detail = error_data.get("error", {}).get("message", "")
        except:
            error_detail = resp.text[:100]
        raise Exception(f"API 返回错误（{resp.status_code}): {error_detail}")
    
    try:
        result = resp.json()
    except requests.exceptions.JSONDecodeError:
        raise Exception(f"API 返回非 JSON 格式: {resp.text[:100]}")
    
    content = result.get("choices", [{}])[0].get("message", {}).get("content")
    
    if not content:
        raise Exception("大模型返回内容为空")
    
    logger.info("[海报生成] 大模型返回内容长度: %d 字符", len(content))
    return content


def extract_url_from_response(content: str) -> str:
    """从响应中提取图片 URL"""
    
    markdown_match = re.search(r'!\[.*?\]\((https?://[^\s\)]+)\)', content)
    if markdown_match:
        url = markdown_match.group(1)
        logger.info("[URL提取] Markdown 格式: %s", mask_url(url))
        return url
    
    url_matches = re.findall(r'https?://[^\s"\'\)<>\]]+\.(?:png|jpg|jpeg|webp)', content, re.I)
    if url_matches:
        logger.info("[URL提取] 直接链接: %s", mask_url(url_matches[0]))
        return url_matches[0]
    
    raise Exception("无法从响应中提取图片 URL")


async def cleanup_expired_tasks():
    """清理过期任务"""
    now = time.time()
    expired = [
        tid for tid, task in _tasks.items()
        if now - task["createdAt"] > TASK_EXPIRE_SECONDS
    ]
    for tid in expired:
        del _tasks[tid]
    if expired:
        logger.info("[任务清理] 清理过期任务: %d 个", len(expired))


async def process_job(
    task_id: str,
    image_url: str,
    job_type: str,
    generation_prompt: str,
    is_test: bool = False,
    test_poster_file_id: str | None = None,
):
    """后台处理任务"""
    try:
        async with _tasks_lock:
            if task_id not in _tasks:
                return
            _tasks[task_id]["status"] = "processing"
        
        if is_test:
            await asyncio.sleep(15)
            poster_url = (
                test_poster_file_id
                or "cloud://cloud1-d7g1nt83fde793ad3.636c-cloud1-d7g1nt83fde793ad3-1427592986/ai-posters/0274fd6869f6176c00082cfb0eeefd94.png"
            )
            async with _tasks_lock:
                _tasks[task_id]["status"] = "completed"
                _tasks[task_id]["posterUrl"] = poster_url
            logger.info("[任务完成] task_id=%s, mode=TEST, posterUrl=%s", task_id, mask_url(poster_url))
            return

        poster_content = await asyncio.to_thread(
            generate_poster,
            image_url,
            job_type,
            generation_prompt,
        )
        poster_url = extract_url_from_response(poster_content)
        
        async with _tasks_lock:
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["posterUrl"] = poster_url
        
        logger.info("[任务完成] task_id=%s, posterUrl=%s", task_id, mask_url(poster_url))
        
    except Exception as e:
        logger.error("[任务失败] task_id=%s, 错误: %s", task_id, str(e))
        async with _tasks_lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "failed"
                _tasks[task_id]["errMsg"] = str(e)


@app.post("/api/job", response_model=JobCreateResponse)
async def create_job(
    job: JobRequest,
    background_tasks: BackgroundTasks,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    """创建图片生成任务"""

    if not POSTER_SERVER_TOKEN or x_internal_token != POSTER_SERVER_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Type naming convention: lowercase alphanumeric, may contain hyphens/underscores,
    # 2-32 chars total, must start with a letter. Examples: palm, hair, ai-makeup.
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", job.type):
        raise HTTPException(status_code=400, detail="无效的类型参数")

    prompt = job.generationPrompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="缺少生成提示词")
    if len(prompt) > 4000:
        raise HTTPException(status_code=400, detail="生成提示词过长")

    task_id = f"task_{uuid.uuid4().hex[:12]}"

    logger.info("[请求入参] POST /api/job type=%s, imageUrl=%s, test=%s", job.type, mask_url(job.imageUrl), job.test)

    async with _tasks_lock:
        await cleanup_expired_tasks()
        _tasks[task_id] = {
            "status": "pending",
            "posterUrl": None,
            "errMsg": None,
            "createdAt": time.time()
        }
    
    background_tasks.add_task(
        process_job,
        task_id,
        job.imageUrl,
        job.type,
        prompt,
        job.test,
        job.testPosterFileID,
    )
    
    logger.info("[任务创建] task_id=%s, type=%s, test=%s", task_id, job.type, job.test)

    result = JobCreateResponse(taskId=task_id)
    logger.info("[请求出参] POST /api/job → %s", result.model_dump_json())
    return result


@app.get("/api/job/{task_id}", response_model=JobStatusResponse)
async def get_job_status(
    task_id: str,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    """查询任务状态"""

    if not POSTER_SERVER_TOKEN or x_internal_token != POSTER_SERVER_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    logger.info("[请求入参] GET /api/job/%s", task_id)

    async with _tasks_lock:
        if task_id not in _tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        task = _tasks[task_id].copy()

    result = JobStatusResponse(
        status=task["status"],
        posterUrl=task["posterUrl"],
        errMsg=task["errMsg"]
    )
    logger.info("[请求出参] GET /api/job/%s → %s", task_id, result.model_dump_json())
    return result


@app.get("/health")
async def health_check():
    """健康检查"""
    api_available = True
    try:
        resp = requests.get(
            MEMEFAST_API_URL.replace("/v1/chat/completions", ""),
            timeout=5
        )
        api_available = resp.status_code < 500
    except:
        api_available = False

    async with _tasks_lock:
        active_tasks = len([t for t in _tasks.values() if t["status"] in ["pending", "processing"]])

    return {
        "status": "ok" if api_available else "degraded",
        "timestamp": time.time(),
        "api": api_available,
        "activeTasks": active_tasks
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)