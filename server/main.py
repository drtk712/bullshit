"""微信小程序 AI 图片生成服务端"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException
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

if not MEMEFAST_API_KEY:
    raise RuntimeError("MEMEFAST_API_KEY 环境变量未设置")

# 任务存储（线程安全）
_tasks: dict[str, dict] = {}
_tasks_lock = asyncio.Lock()

# 任务过期时间（秒）
TASK_EXPIRE_SECONDS = 3600  # 1小时

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Poster Generator")


class JobRequest(BaseModel):
    imageUrl: str
    type: str  # "palm" or "hair"
    test: bool = False  # 测试模式，不调用API


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


def generate_poster(image_url: str, job_type: str) -> str:
    """调用大模型生成海报"""
    
    palm_prompt = """Based on this palm photo, generate a beautiful palmistry analysis poster in Chinese. 
Style: minimalist line art, elegant typography, warm beige background. 
Include: a traced palm outline with labeled lines (生命线/智慧线/感情线/事业线), 
personality traits section, career compatibility section, emotional characteristics section. 
Text should be in Chinese. Format: vertical poster, clean layout, professional look."""
    
    hair_prompt = """Based on this person's photo, generate a professional hairstyle analysis poster in Chinese.
Style: modern magazine layout, dark navy background with white cards.
Include: person's photo on left with face analysis (脸型/发质/发色),
recommended hairstyles with example images on right, styles to avoid section,
hair care tips, product recommendations.
Text should be in Chinese. Format: vertical poster, clean layout, professional look."""
    
    prompt = palm_prompt if job_type == "palm" else hair_prompt
    
    logger.info(f"开始生成海报，类型: {job_type}, 图片: {mask_url(image_url)}")
    
    try:
        resp = requests.post(
            MEMEFAST_API_URL,
            json={
                "model": "gpt-image-2-all",
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
    
    logger.info(f"大模型返回: {content[:100]}...")
    return content


def extract_url_from_response(content: str) -> str:
    """从响应中提取图片 URL"""
    
    markdown_match = re.search(r'!\[.*?\]\((https?://[^\s\)]+)\)', content)
    if markdown_match:
        url = markdown_match.group(1)
        logger.info(f"提取到 Markdown 图片 URL: {url}")
        return url
    
    url_matches = re.findall(r'https?://[^\s"\'\)<>\]]+\.(?:png|jpg|jpeg|webp)', content, re.I)
    if url_matches:
        logger.info(f"提取到直接 URL: {url_matches[0]}")
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
        logger.info(f"清理过期任务: {len(expired)} 个")


async def process_job(task_id: str, image_url: str, job_type: str, is_test: bool = False):
    """后台处理任务"""
    try:
        async with _tasks_lock:
            if task_id not in _tasks:
                return
            _tasks[task_id]["status"] = "processing"
        
        if is_test:
            await asyncio.sleep(15)
            test_poster_url = "https://pro.filesystem.site/cdn/20260502/4f5e70a3dcb59a0ac9fd60424093c8.png"
            async with _tasks_lock:
                _tasks[task_id]["status"] = "completed"
                _tasks[task_id]["posterUrl"] = test_poster_url
            logger.info(f"[TEST] 任务完成: {task_id}, posterUrl: {mask_url(test_poster_url)}")
            return
        
        poster_content = await asyncio.to_thread(generate_poster, image_url, job_type)
        poster_url = extract_url_from_response(poster_content)
        
        async with _tasks_lock:
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["posterUrl"] = poster_url
        
        logger.info(f"任务完成: {task_id}, posterUrl: {mask_url(poster_url)}")
        
    except Exception as e:
        logger.error(f"任务处理失败: {task_id}, 错误: {e}")
        async with _tasks_lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "failed"
                _tasks[task_id]["errMsg"] = str(e)


@app.post("/api/job", response_model=JobCreateResponse)
async def create_job(job: JobRequest, background_tasks: BackgroundTasks):
    """创建图片生成任务"""
    
    if job.type not in ["palm", "hair"]:
        raise HTTPException(status_code=400, detail="无效的类型参数")
    
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    
    async with _tasks_lock:
        await cleanup_expired_tasks()
        _tasks[task_id] = {
            "status": "pending",
            "posterUrl": None,
            "errMsg": None,
            "createdAt": time.time()
        }
    
    background_tasks.add_task(process_job, task_id, job.imageUrl, job.type, job.test)
    
    logger.info(f"创建任务: {task_id}, test={job.test}")
    
    return JobCreateResponse(taskId=task_id)


@app.get("/api/job/{task_id}", response_model=JobStatusResponse)
async def get_job_status(task_id: str):
    """查询任务状态"""
    
    async with _tasks_lock:
        if task_id not in _tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        task = _tasks[task_id].copy()
    
    return JobStatusResponse(
        status=task["status"],
        posterUrl=task["posterUrl"],
        errMsg=task["errMsg"]
    )


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