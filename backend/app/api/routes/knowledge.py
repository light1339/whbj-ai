import json
import asyncio
import time
import os
from typing import Any
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.core.volc_engine_retriever import knowledge_service_chat_stream
from app.core.mdb import search_logs_collection, SearchLogModel

router = APIRouter()

@router.post("/chat")
async def chat_with_knowledge_base(request: Request):
    """
    🔥 完美修正版：火山引擎知识库专属流式（打字机）检索接口
    """
    try:
        # 使用 request.json() 显式解析，确保全链路流式网络管道完美畅通
        body = await request.json()
        user_query = body.get("query", "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误，必须为 JSON")
    
    if not user_query:
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    
    start_time = time.time()
    full_response = ""
    search_status = "success"
    error_detail = None

    async def event_generator():
        nonlocal full_response, search_status, error_detail
        try:
            for text_chunk in knowledge_service_chat_stream(user_query):
                full_response += text_chunk
                yield f"data: {json.dumps({'text': text_chunk})}\n\n"
                await asyncio.sleep(0.001)

            yield "data: [DONE]\n\n"

        except Exception as e:
            search_status = "error"
            error_detail = str(e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = StreamingResponse(event_generator(), media_type="text/event-stream")

    async def save_log_background():
        await asyncio.sleep(0.5)
        try:
            elapsed_ms = int((time.time() - start_time) * 1000)
            client_ip = request.client.host if request.client else None

            log_entry = SearchLogModel(
                query=user_query,
                response_length=len(full_response),
                source="volc_knowledge_base",
                model=os.getenv("VOLC_ARK_MODEL", ""),
                response_time_ms=elapsed_ms,
                user_ip=client_ip,
                status=search_status,
                error_message=error_detail,
            )
            await search_logs_collection.insert_one(log_entry.model_dump())
            print(f"📝 [搜索日志] 已保存: {user_query[:30]}... | 回复{len(full_response)}字 | 耗时: {elapsed_ms}ms")
        except Exception as e:
            print(f"⚠️ [搜索日志保存失败]: {e}")

    asyncio.create_task(save_log_background())

    return response


@router.get("/logs")
async def get_search_logs(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    """
    查看最近 N 条搜索日志（主要用来看用户都在搜什么/耗时/成功率）
    访问: http://localhost:8000/api/v1/knowledge/logs?limit=50
    """
    logs: list[dict[str, Any]] = []
    cursor = search_logs_collection.find().sort("created_at", -1).limit(limit)
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        logs.append(doc)

    total = await search_logs_collection.estimated_document_count()
    return {"total": total, "count": len(logs), "logs": logs}