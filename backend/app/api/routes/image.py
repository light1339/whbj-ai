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

# DeepSeek 翻译配置（复用已有的 DeepSeek Key）
TRANSLATE_API_KEY = os.getenv("OPENAI_API_KEY")
TRANSLATE_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
TRANSLATE_MODEL = os.getenv("OPENAI_MODEL", "deepseek-v4-flash")

# gpt-image-2 支持的分辨率选项
SIZE_OPTIONS = [
    "1024x1024", "1024x1536", "1536x1024",
    "2000x1000", "1000x2000", "2000x667", "667x2000",
]
QUALITY_OPTIONS = ["low", "medium", "high"]
THINKING_OPTIONS = ["off", "low", "medium", "high"]
BACKGROUND_OPTIONS = ["auto", "transparent", "opaque"]


def _translate_prompt(chinese_text: str) -> str:
    """使用 DeepSeek 将中文提示词翻译为英文"""
    client = OpenAI(
        api_key=TRANSLATE_API_KEY,
        base_url=TRANSLATE_BASE_URL,
    )
    response = client.chat.completions.create(
        model=TRANSLATE_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a professional translator specializing in AI image generation prompts. "
                           "Translate the user's Chinese prompt into natural, descriptive English. "
                           "Preserve all visual details, style requirements, composition descriptions, "
                           "lighting, colors, and mood. Output ONLY the English translation, no explanations.",
            },
            {"role": "user", "content": chinese_text},
        ],
        temperature=0.3,
        max_tokens=1024,
    )
    translated = response.choices[0].message.content.strip()
    print(f"  [翻译] {chinese_text[:40]}... → {translated[:40]}...")
    return translated


@router.post("/translate")
async def translate_prompt(
    request: Request,
    current_user: dict | None = Depends(get_current_user),
):
    """翻译中文提示词为英文"""
    try:
        body = await request.json()
        text = body.get("text", "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")

    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")
    if not TRANSLATE_API_KEY:
        raise HTTPException(status_code=500, detail="未配置 OPENAI_API_KEY")

    try:
        loop = asyncio.get_running_loop()
        translated = await loop.run_in_executor(None, _translate_prompt, text)
        return {"original": text, "translated": translated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译失败: {str(e)}")


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
        translate = body.get("translate", False)
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

    # 翻译处理
    original_prompt = prompt
    en_prompt = None
    if translate and prompt:
        if not TRANSLATE_API_KEY:
            raise HTTPException(status_code=500, detail="未配置翻译 API Key")
        try:
            en_prompt = _translate_prompt(prompt)
            prompt = en_prompt  # 用英文 prompt 生图
        except Exception as e:
            print(f"  [翻译失败] 继续使用中文 prompt: {e}")

    # 写入 pending 状态
    task_doc = {
        "_id": task_id,
        "user_id": user_id,
        "prompt": prompt,  # 实际用于生图的 prompt（可能是英文）
        "original_prompt": original_prompt if en_prompt else None,  # 中文原始 prompt
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


# ========== 图片编辑（inpainting） ==========

def _call_openai_edit_api(
    task_id: str,
    image_b64: str,
    mask_b64: str,
    prompt: str,
    size: str,
) -> dict | None:
    """使用 OpenAI SDK 调用 /v1/images/edits"""
    def _clean(b64: str) -> bytes:
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        return base64.b64decode(b64)

    client = OpenAI(
        api_key=OPENAI_IMAGE_API_KEY,
        base_url=OPENAI_IMAGE_BASE_URL,
        timeout=300.0,
    )

    response = client.images.edit(
        model=OPENAI_IMAGE_MODEL,
        image=("image.png", _clean(image_b64), "image/png"),
        mask=("mask.png", _clean(mask_b64), "image/png"),
        prompt=prompt,
        n=1,
        size=size,
    )

    return response.model_dump()


def _save_edit_result(task_id: str, response: dict) -> str:
    """保存编辑结果图片，返回路径"""
    image_dir = Path("app/static/images")
    image_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{task_id}_edit.png"
    filepath = image_dir / filename

    data_list = response.get("data", [])
    if not data_list:
        raise Exception("OpenAI 未返回图片数据")

    first = data_list[0]
    if first.get("b64_json"):
        filepath.write_bytes(base64.b64decode(first["b64_json"]))
    elif first.get("url"):
        r = requests.get(first["url"], timeout=60)
        r.raise_for_status()
        filepath.write_bytes(r.content)
    else:
        raise Exception("图片数据为空")

    return f"/static/images/{filename}"


@router.post("/edit")
async def edit_image(
    request: Request,
    current_user: dict | None = Depends(get_current_user),
):
    """提交图片编辑（微调）任务"""
    try:
        body = await request.json()
        image_base64 = body.get("image_base64", "").strip()
        mask_base64 = body.get("mask_base64", "").strip()
        prompt = body.get("prompt", "").strip()
        size = body.get("size", "1024x1024")
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误，必须为 JSON")

    if not image_base64:
        raise HTTPException(status_code=400, detail="原图不能为空")
    if not mask_base64:
        raise HTTPException(status_code=400, detail="蒙版不能为空（请在图上涂抹要修改的区域）")
    if not prompt:
        raise HTTPException(status_code=400, detail="修改描述不能为空")
    if size not in SIZE_OPTIONS:
        raise HTTPException(status_code=400, detail=f"无效的分辨率，可选: {SIZE_OPTIONS}")

    task_id = str(uuid.uuid4())
    user_id = current_user["user_id"] if current_user else None

    task_doc = {
        "_id": task_id,
        "user_id": user_id,
        "prompt": prompt,
        "size": size,
        "status": "pending",
        "task_type": "edit",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "error_message": None,
        "image_paths": [],
    }
    await image_tasks_collection.insert_one(task_doc)

    asyncio.create_task(_run_edit_generation(task_id, user_id, image_base64, mask_base64, prompt, size))

    return {"task_id": task_id, "status": "pending", "message": "图片微调任务已提交"}


async def _run_edit_generation(
    task_id: str,
    user_id: str | None,
    image_b64: str,
    mask_b64: str,
    prompt: str,
    size: str,
):
    try:
        await image_tasks_collection.update_one(
            {"_id": task_id},
            {"$set": {"status": "processing", "updated_at": datetime.utcnow()}},
        )

        if not OPENAI_IMAGE_API_KEY:
            raise Exception("未配置 OPENAI_IMAGE_API_KEY")

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, _call_openai_edit_api, task_id, image_b64, mask_b64, prompt, size,
        )

        image_path = _save_edit_result(task_id, response)

        await image_tasks_collection.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "status": "completed",
                    "image_paths": [image_path],
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        print(f"  [图片编辑完成] {task_id}")

    except Exception as e:
        print(f"  [图片编辑失败] {task_id}: {e}")
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
        "original_prompt": task.get("original_prompt"),
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
