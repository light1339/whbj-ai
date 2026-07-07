import os
import uuid
import base64
import asyncio
import requests
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import FileResponse
from openai import OpenAI
from app.core.database import db
from app.core.auth import get_current_user
from app.core.volc_config import OPENAI_IMAGE_API_KEY, OPENAI_IMAGE_BASE_URL, OPENAI_IMAGE_MODEL

router = APIRouter()

# MongoDB 集合
image_tasks_collection = db["image_tasks"]

# gpt-image-2 支持的分辨率选项
SIZE_OPTIONS = [
    "1024x1024", "1024x1536", "1536x1024",
    "2000x1000", "1000x2000", "2000x667", "667x2000",
]
QUALITY_OPTIONS = ["low", "medium", "high"]
THINKING_OPTIONS = ["off", "low", "medium", "high"]
BACKGROUND_OPTIONS = ["auto", "transparent", "opaque"]


def _call_openai_image_api(
    task_id: str,
    prompt: str,
    size: str,
    quality: str,
    n: int,
    thinking: str | None,
    background: str | None,
    seed: int,
    image_urls: list[str] | None = None,
) -> dict | None:
    """同步调用 OpenAI gpt-image-2 API"""
    client = OpenAI(
        api_key=OPENAI_IMAGE_API_KEY,
        base_url=OPENAI_IMAGE_BASE_URL,
    )

    params: dict = {
        "model": OPENAI_IMAGE_MODEL,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": n,
    }
    if thinking and thinking != "off":
        params["thinking"] = thinking
    if background and background != "auto":
        params["background"] = background
    if seed >= 0:
        params["seed"] = seed
    if image_urls:
        params["image"] = image_urls

    ref_count = len(image_urls) if image_urls else 0
    print(f"  [调用 gpt-image-2] task_id={task_id}, size={size}, quality={quality}, n={n}, ref_images={ref_count}")
    response = client.images.generate(**params)
    return response


async def _save_images(task_id: str, response) -> list[str]:
    """将生成的图片保存到本地，返回路径列表"""
    image_dir = Path("app/static/images")
    image_dir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []
    for i, img_data in enumerate(response.data):
        suffix = f"_{i}" if len(response.data) > 1 else ""
        filename = f"{task_id}{suffix}.png"
        filepath = image_dir / filename

        if img_data.b64_json:
            filepath.write_bytes(base64.b64decode(img_data.b64_json))
        elif img_data.url:
            r = requests.get(img_data.url, timeout=60)
            r.raise_for_status()
            filepath.write_bytes(r.content)
        else:
            continue

        paths.append(f"/static/images/{filename}")

    return paths


@router.post("/generate")
async def generate_image(
    request: Request,
    current_user: dict | None = Depends(get_current_user),
):
    """提交图片生成任务"""
    try:
        body = await request.json()
        prompt = body.get("prompt", "").strip()
        size = body.get("size", "1024x1024")
        quality = body.get("quality", "medium")
        n = body.get("n", 1)
        thinking = body.get("thinking", "off")
        background = body.get("background", "auto")
        seed = body.get("seed", -1)
        image_urls = body.get("image_urls", None)
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误，必须为 JSON")

    if not prompt and not image_urls:
        raise HTTPException(status_code=400, detail="提示词不能为空")
    if size not in SIZE_OPTIONS:
        raise HTTPException(status_code=400, detail=f"无效的分辨率，可选: {SIZE_OPTIONS}")
    if quality not in QUALITY_OPTIONS:
        raise HTTPException(status_code=400, detail=f"无效的画质，可选: {QUALITY_OPTIONS}")
    if not 1 <= n <= 10:
        raise HTTPException(status_code=400, detail="生成张数范围: 1-10")
    if image_urls and len(image_urls) > 16:
        raise HTTPException(status_code=400, detail="参考图片最多 16 张")

    task_id = str(uuid.uuid4())
    user_id = current_user["user_id"] if current_user else None
    has_reference = bool(image_urls)

    # 写入 pending 状态
    task_doc = {
        "_id": task_id,
        "user_id": user_id,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": n,
        "thinking": thinking,
        "background": background,
        "seed": seed,
        "has_reference": has_reference,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "error_message": None,
        "image_paths": [],
    }
    await image_tasks_collection.insert_one(task_doc)

    # 异步调用 OpenAI
    asyncio.create_task(_run_image_generation(task_id, user_id, prompt, size, quality, n, thinking, background, seed, image_urls))

    return {"task_id": task_id, "status": "pending", "message": "图片生成任务已提交"}


async def _run_image_generation(
    task_id: str,
    user_id: str | None,
    prompt: str,
    size: str,
    quality: str,
    n: int,
    thinking: str | None,
    background: str | None,
    seed: int,
    image_urls: list[str] | None = None,
):
    """在线程池中执行 OpenAI 调用，避免阻塞事件循环"""
    try:
        # 更新为 processing
        await image_tasks_collection.update_one(
            {"_id": task_id},
            {"$set": {"status": "processing", "updated_at": datetime.utcnow()}},
        )

        if not OPENAI_IMAGE_API_KEY:
            raise Exception("未配置 OPENAI_IMAGE_API_KEY")

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            _call_openai_image_api,
            task_id, prompt, size, quality, n, thinking, background, seed, image_urls,
        )

        # 保存图片
        image_paths = await _save_images(task_id, response)

        await image_tasks_collection.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "status": "completed",
                    "image_paths": image_paths,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        print(f"  [图片生成完成] {task_id}, {len(image_paths)} 张")

    except Exception as e:
        print(f"  [图片生成失败] {task_id}: {e}")
        await image_tasks_collection.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e),
                    "updated_at": datetime.utcnow(),
                }
            },
        )


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: dict | None = Depends(get_current_user),
):
    """查询图片生成任务状态"""
    task = await image_tasks_collection.find_one({"_id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task["_id"],
        "status": task["status"],
        "prompt": task.get("prompt"),
        "image_paths": task.get("image_paths", []),
        "error_message": task.get("error_message"),
        "size": task.get("size"),
        "quality": task.get("quality"),
        "n": task.get("n"),
        "has_reference": task.get("has_reference", False),
        "created_at": task.get("created_at").isoformat() if task.get("created_at") else None,
        "updated_at": task.get("updated_at").isoformat() if task.get("updated_at") else None,
    }


@router.get("/result/{task_id}/{index}")
async def get_image_result(
    task_id: str,
    index: int = 0,
    current_user: dict | None = Depends(get_current_user),
):
    """获取生成的图片文件"""
    task = await image_tasks_collection.find_one({"_id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="图片尚未生成完成")

    image_paths: list = task.get("image_paths", [])
    if index >= len(image_paths):
        raise HTTPException(status_code=404, detail=f"图片索引 {index} 不存在，共 {len(image_paths)} 张")

    filepath = image_paths[index].lstrip("/")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="图片文件不存在")

    return FileResponse(filepath, media_type="image/png")


@router.get("/history")
async def get_image_history(
    limit: int = 20,
    offset: int = 0,
    current_user: dict | None = Depends(get_current_user),
):
    """获取用户的图片生成历史"""
    user_id = current_user["user_id"] if current_user else None
    query = {"user_id": user_id} if user_id else {}

    cursor = image_tasks_collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
    tasks = await cursor.to_list(length=limit)

    return {
        "tasks": [
            {
                "task_id": task["_id"],
                "prompt": task.get("prompt"),
                "status": task["status"],
                "image_paths": task.get("image_paths", []),
                "error_message": task.get("error_message"),
                "size": task.get("size"),
                "quality": task.get("quality"),
                "n": task.get("n"),
                "created_at": task.get("created_at").isoformat() if task.get("created_at") else None,
            }
            for task in tasks
        ],
        "total": await image_tasks_collection.count_documents(query),
    }


@router.delete("/{task_id}")
async def delete_image_task(
    task_id: str,
    current_user: dict | None = Depends(get_current_user),
):
    """删除图片生成任务及相关文件"""
    task = await image_tasks_collection.find_one({"_id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 删除本地图片文件
    for path in task.get("image_paths", []):
        filepath = path.lstrip("/")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"  [删除图片失败] {filepath}: {e}")

    await image_tasks_collection.delete_one({"_id": task_id})
    return {"message": "任务已删除"}
