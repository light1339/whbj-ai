import os
import uuid
import time
import asyncio
import requests
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from app.core.database import db
from app.core.auth import get_current_user
from app.core.volc_config import VOLC_VIDEO_API_KEY, VOLC_VIDEO_BASE_URL, VOLC_VIDEO_MODEL

router = APIRouter()

# MongoDB 集合
video_tasks_collection = db["video_tasks"]
volc_requests_collection = db["volc_requests"]  # 火山引擎原始请求记录

# 测试模式配置
TEST_MODE = False  # 设置为 True 启用测试模式，False 启用正常模式
TEST_VOLC_TASK_ID = "cgt-20260630180300-j75n7"  # 固定的火山引擎任务 ID（仅测试模式使用）

def get_volc_video_url(task_id: str) -> dict | None:
    """调用火山引擎 API 获取视频信息（只在 succeeded 时返回数据）"""
    try:
        # 使用官方 API 端点：contents/generations/tasks
        response = requests.get(
            f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}",
            headers={
                "Authorization": f"Bearer {VOLC_VIDEO_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        print(f"📊 火山引擎响应状态码：{response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"📦 火山引擎响应数据：{data}")
            # 只在 succeeded 时返回数据
            if data.get("status") == "succeeded":
                video_url = data.get("content", {}).get("video_url")
                if video_url:
                    print(f"✅ 获取到视频 URL: {video_url[:100]}...")
                    return {
                        "status": "succeeded",
                        "video_url": video_url,
                        "volc_status": "succeeded",
                    }
            print(f"⏳ 任务状态：{data.get('status')}，未完成")
        return None
    except Exception as e:
        print(f"❌ 获取火山视频 URL 失败：{e}")
        return None


@router.post("/generate")
async def generate_video(
    request: Request,
    current_user: dict | None = Depends(get_current_user),
):
    """提交视频生成任务"""
    
    # 测试模式：查询火山引擎，只在 succeeded 时写入数据库
    if TEST_MODE:
        user_id = current_user["user_id"] if current_user else None
        
        # 调用火山引擎 API 查询任务状态
        volc_data = get_volc_video_url(TEST_VOLC_TASK_ID)
        
        if volc_data:
            # succeeded：写入数据库并返回
            task_id = f"test-{uuid.uuid4()}"
            task_doc = {
                "_id": task_id,
                "user_id": user_id,
                "prompt": "测试视频生成（固定任务 ID）",
                "duration": 5,
                "resolution": "720p",
                "seed": -1,
                "status": "completed",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "error_message": None,
                "video_url": volc_data["video_url"],
                "video_path": None,
                "task_request_id": TEST_VOLC_TASK_ID,
                "volc_status": volc_data["volc_status"],
            }
            await video_tasks_collection.insert_one(task_doc)
            
            return {
                "task_id": task_id, 
                "status": "completed", 
                "message": "测试模式：任务已完成",
                "video_url": volc_data["video_url"]
            }
        else:
            # 未完成：返回处理中状态
            return {
                "task_id": f"test-{uuid.uuid4()}",
                "status": "pending",
                "message": "测试模式：任务尚未完成，请稍后查询"
            }
    
    # 正常模式：不预先写入数据库，等 succeeded 时才写入
    try:
        body = await request.json()
        prompt = body.get("prompt", "").strip()
        duration = body.get("duration", 5)  # 默认 5 秒
        resolution = body.get("resolution", "720p")
        ratio = body.get("ratio", "16:9")  # 默认 16:9 横屏
        seed = body.get("seed", -1)
        reference_images = body.get("reference_images", None)  # 参考角色图片（base64 列表）
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误，必须为 JSON")

    if not prompt:
        raise HTTPException(status_code=400, detail="提示词不能为空")
    if reference_images and not isinstance(reference_images, list):
        raise HTTPException(status_code=400, detail="参考图片格式错误，必须为数组")
    if reference_images and len(reference_images) > 3:
        raise HTTPException(status_code=400, detail="参考图片最多 3 张")

    # 生成任务 ID（仅用于前端追踪）
    task_id = str(uuid.uuid4())
    user_id = current_user["user_id"] if current_user else None

    # 先写入数据库（pending 状态），让前端可以查询
    task_doc = {
        "_id": task_id,
        "user_id": user_id,
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
        "ratio": ratio,
        "seed": seed,
        "has_reference": bool(reference_images),
        "reference_count": len(reference_images) if reference_images else 0,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "error_message": None,
        "video_url": None,
        "video_path": None,
        "task_request_id": None,
        "volc_status": None,
    }
    await video_tasks_collection.insert_one(task_doc)

    # 异步调用火山引擎视频生成 API
    asyncio.create_task(_call_volc_video_api(task_id, user_id, prompt, duration, resolution, ratio, seed, reference_images))

    return {"task_id": task_id, "status": "pending", "message": "视频生成任务已提交"}


async def _call_volc_video_api(
    task_id: str,
    user_id: str | None,
    prompt: str,
    duration: int,
    resolution: str,
    ratio: str,
    seed: int,
    reference_images: list[str] | None = None,
):
    """异步调用火山引擎视频生成 API"""
    try:
        # 更新状态为 processing
        await video_tasks_collection.update_one(
            {"_id": task_id},
            {"$set": {"status": "processing", "updated_at": datetime.utcnow()}},
        )

        api_key = VOLC_VIDEO_API_KEY
        model = VOLC_VIDEO_MODEL

        if not api_key:
            raise Exception("未配置 VOLC_VIDEO_API_KEY")

        # 火山引擎内容生成 API（官方推荐）
        # API 文档：https://www.volcengine.com/docs/6791/1346646
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 构造 content 数组：参考图片在前，文本提示词在后
        content = []
        if reference_images:
            for img_url in reference_images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img_url},
                    "role": "reference_image",
                })

        # 使用官方 content 格式
        payload = {
            "model": model,
            "content": content + [
                {
                    "type": "text",
                    "text": prompt,
                }
            ],
            "generate_audio": True,  # 生成音频
            "ratio": ratio,          # 视频比例（用户选择）
            "duration": duration,
            "watermark": False,      # 不加水印
        }

        # 提交异步任务 - 使用官方 API 端点
        print(f"🚀 [提交视频生成任务] task_id={task_id}")
        print(f"📤 请求 URL: https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks")
        print(f"📤 完整请求参数 (payload):")
        import json
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        
        response = requests.post(
            "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            headers=headers,
            json=payload,
            timeout=30,
        )
        print(f"📥 响应状态码: {response.status_code}")
        if response.status_code != 200:
            print(f"📥 错误响应体: {response.text[:1000]}")
        response.raise_for_status()
        result = response.json()
        print(f"📥 响应数据: {result}")

        # 获取火山引擎返回的 task_id（格式：cgt-xxx）
        volc_task_id = result.get("id")
        if not volc_task_id:
            raise Exception(f"未获取到任务 ID，响应：{result}")
        
        print(f"📋 火山引擎任务 ID: {volc_task_id}")
        
        # 保存 volc_task_id 到数据库
        await video_tasks_collection.update_one(
            {"_id": task_id},
            {"$set": {"task_request_id": volc_task_id, "updated_at": datetime.utcnow()}},
        )

        # 保存火山引擎原始请求响应到独立集合（唯一请求记录）
        volc_request_doc = {
            "task_id": task_id,  # 关联到 video_tasks 的 task_id
            "volc_task_id": volc_task_id,  # 火山引擎返回的 cgt-xxx
            "request_payload": payload,  # 发送的完整请求参数
            "response_data": result,  # 火山引擎返回的完整响应
            "status": "submitted",  # submitted, running, succeeded, failed
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        await volc_requests_collection.insert_one(volc_request_doc)
        print(f"💾 已保存火山引擎请求记录到 volc_requests 集合")

        # 轮询任务状态 - 使用官方 API 端点
        await _poll_video_status(task_id, volc_task_id, headers)

    except Exception as e:
        print(f"❌ [视频生成失败] {task_id}: {e}")
        await video_tasks_collection.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e),
                    "updated_at": datetime.utcnow(),
                }
            },
        )


async def _poll_video_status(task_id: str, volc_task_id: str, headers: dict):
    """轮询视频生成状态"""
    max_retries = 60  # 最多轮询 60 次
    retry_interval = 30  # 每 30 秒轮询一次（官方建议）

    for i in range(max_retries):
        try:
            # 使用官方 API 端点查询任务状态
            query_url = f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{volc_task_id}"
            print(f"🔍 [轮询 {i+1}/{max_retries}] 查询 URL: {query_url}")
            
            response = requests.get(
                query_url,
                headers=headers,
                timeout=30,
            )
            print(f"📥 响应状态码: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            print(f"📥 响应数据: {result}")

            status = result.get("status")
            print(f"📊 当前状态: {status}")

            if status == "succeeded":
                # 获取视频 URL（官方返回结构）
                video_url = None
                content = result.get("content", {})
                if isinstance(content, dict):
                    video_url = content.get("video_url")

                # 下载视频并保存
                video_path = None
                if video_url:
                    video_path = await _download_video(task_id, video_url)

                # 更新数据库为 completed
                await video_tasks_collection.update_one(
                    {"_id": task_id},
                    {
                        "$set": {
                            "status": "completed",
                            "video_url": video_url,
                            "video_path": video_path,
                            "volc_status": "succeeded",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                
                print(f"✅ [视频生成完成并已保存] {task_id}")
                return

            elif status == "failed":
                error_msg = "视频生成失败"
                error_info = result.get("error", {})
                if isinstance(error_info, dict):
                    error_msg = error_info.get("message", error_msg)
                
                # 更新数据库为 failed
                await video_tasks_collection.update_one(
                    {"_id": task_id},
                    {
                        "$set": {
                            "status": "failed",
                            "error_message": error_msg,
                            "volc_status": "failed",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                print(f"❌ [视频生成失败] {task_id}: {error_msg}")
                return

            # 继续轮询（running 或 pending 状态）
            print(f"📊 任务状态：{status}，30秒后重试...")
            await asyncio.sleep(retry_interval)

        except Exception as e:
            print(f"⚠️ [轮询视频状态异常] {task_id}: {e}")
            await asyncio.sleep(retry_interval)

    # 超时：更新数据库为 failed
    await video_tasks_collection.update_one(
        {"_id": task_id},
        {
            "$set": {
                "status": "failed",
                "error_message": "视频生成超时，请稍后重试",
                "volc_status": "timeout",
                "updated_at": datetime.utcnow(),
            }
        },
    )
    print(f"⏰ [视频生成超时] {task_id}")


async def _download_video(task_id: str, video_url: str) -> str | None:
    """下载视频到本地"""
    try:
        # 创建视频存储目录
        video_dir = os.path.join("app", "static", "videos")
        os.makedirs(video_dir, exist_ok=True)

        video_filename = f"{task_id}.mp4"
        video_path = os.path.join(video_dir, video_filename)

        response = requests.get(video_url, timeout=60)
        response.raise_for_status()

        with open(video_path, "wb") as f:
            f.write(response.content)

        return f"/static/videos/{video_filename}"

    except Exception as e:
        print(f"⚠️ [视频下载失败] {task_id}: {e}")
        return None


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: dict | None = Depends(get_current_user),
):
    """查询视频生成任务状态"""
    task = await video_tasks_collection.find_one({"_id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 测试模式：直接查询火山引擎获取最新状态
    if TEST_MODE and task.get("task_request_id"):
        try:
            volc_response = requests.get(
                f"{VOLC_VIDEO_BASE_URL}/contents/generations/tasks/{task['task_request_id']}",
                headers={
                    "Authorization": f"Bearer {VOLC_VIDEO_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if volc_response.status_code == 200:
                volc_data = volc_response.json()
                # 更新 MongoDB 中的状态
                volc_status = volc_data.get("status")
                video_url = volc_data.get("content", {}).get("video_url")
                
                if video_url:
                    await video_tasks_collection.update_one(
                        {"_id": task_id},
                        {"$set": {"video_url": video_url, "volc_status": volc_status}}
                    )
                    task["video_url"] = video_url
                    task["volc_status"] = volc_status
        except Exception as e:
            print(f"⚠️ 查询火山引擎失败：{e}")
            # 失败不影响返回，继续使用 MongoDB 数据

    return {
        "task_id": task["_id"],
        "status": task["status"],
        "prompt": task.get("prompt"),
        "video_url": task.get("video_url"),
        "video_path": task.get("video_path"),
        "error_message": task.get("error_message"),
        "volc_status": task.get("volc_status"),
        "created_at": task.get("created_at").isoformat() if task.get("created_at") else None,
        "updated_at": task.get("updated_at").isoformat() if task.get("updated_at") else None,
    }


@router.get("/result/{task_id}")
async def get_video_result(
    task_id: str,
    current_user: dict | None = Depends(get_current_user),
):
    """获取生成的视频文件"""
    task = await video_tasks_collection.find_one({"_id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="视频尚未生成完成")

    video_path = task.get("video_path")
    if not video_path or not os.path.exists(video_path.lstrip("/")):
        raise HTTPException(status_code=404, detail="视频文件不存在")

    return FileResponse(video_path.lstrip("/"), media_type="video/mp4")


@router.get("/history")
async def get_video_history(
    limit: int = 20,
    offset: int = 0,
    current_user: dict | None = Depends(get_current_user),
):
    """获取用户的视频生成历史"""
    user_id = current_user["user_id"] if current_user else None

    query = {"user_id": user_id} if user_id else {}

    cursor = video_tasks_collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
    tasks = await cursor.to_list(length=limit)

    return {
        "tasks": [
            {
                "task_id": task["_id"],
                "prompt": task.get("prompt"),
                "status": task["status"],
                "video_url": task.get("video_url"),
                "video_path": task.get("video_path"),
                "error_message": task.get("error_message"),
                "duration": task.get("duration"),
                "resolution": task.get("resolution"),
                "created_at": task.get("created_at").isoformat() if task.get("created_at") else None,
            }
            for task in tasks
        ],
        "total": await video_tasks_collection.count_documents(query),
    }


@router.delete("/{task_id}")
async def delete_video_task(
    task_id: str,
    current_user: dict | None = Depends(get_current_user),
):
    """删除视频生成任务"""
    task = await video_tasks_collection.find_one({"_id": task_id})

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 删除本地视频文件
    video_path = task.get("video_path")
    if video_path and os.path.exists(video_path.lstrip("/")):
        try:
            os.remove(video_path.lstrip("/"))
        except Exception as e:
            print(f"⚠️ [删除视频文件失败] {video_path}: {e}")

    await video_tasks_collection.delete_one({"_id": task_id})

    return {"message": "任务已删除"}
