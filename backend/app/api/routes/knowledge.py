import json
import asyncio
import time
import os
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from openai import OpenAI
from app.core.volc_engine_retriever import knowledge_service_chat_stream
from app.core.mdb import search_logs_collection, SearchLogModel
from app.core.auth import get_current_user

router = APIRouter()


# ──────────────────────────────────────────────
# POST /chat — SSE 流式回答 + 搜索日志（可选认证）
# ──────────────────────────────────────────────

@router.post("/chat")
async def chat_with_knowledge_base(request: Request, current_user: dict | None = Depends(get_current_user)):
    try:
        body = await request.json()
        user_query = body.get("query", "").strip()
        deep_think = body.get("deep_think", False)
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
            for text_chunk in knowledge_service_chat_stream(user_query, deep_think):
                full_response += text_chunk
                yield f"data: {json.dumps({'text': text_chunk})}\n\n"
                await asyncio.sleep(0.001)

            yield "data: [DONE]\n\n"

        except Exception as e:
            search_status = "error"
            error_detail = str(e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = StreamingResponse(event_generator(), media_type="text/event-stream")

    async def _save_log():
        await asyncio.sleep(0.5)
        try:
            elapsed_ms = int((time.time() - start_time) * 1000)
            client_ip = request.client.host if request.client else None
            log_entry = SearchLogModel(
                query=user_query,
                user_id=current_user["user_id"] if current_user else None,
                response_length=len(full_response),
                source="volc_knowledge_base",
                model=os.getenv("VOLC_ARK_MODEL", ""),
                response_time_ms=elapsed_ms,
                user_ip=client_ip,
                status=search_status,
                error_message=error_detail,
            )
            await search_logs_collection.insert_one(log_entry.model_dump())
            user_tag = f"用户: {current_user['username']} | " if current_user else ""
            print(f"📝 [搜索日志] {user_tag}{user_query[:30]}... | {len(full_response)}字 | {elapsed_ms}ms")
        except Exception as e:
            print(f"⚠️ [日志保存失败]: {e}")

    asyncio.create_task(_save_log())
    return response


# ──────────────────────────────────────────────
# POST /chat/extend — 追问生成（可选认证）
# ──────────────────────────────────────────────

@router.post("/chat/extend")
async def get_extend_questions(request: Request, current_user: dict | None = Depends(get_current_user)):
    try:
        body = await request.json()
        query = body.get("query", "").strip()
        answer = body.get("answer", "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")

    if not query or not answer:
        return {"questions": []}

    model = os.getenv("VOLC_ARK_MODEL", "")
    api_key = os.getenv("VOLC_ARK_API_KEY", "") or os.getenv("VOLC_KNOWLEDGE_API_KEY", "")
    base_url = os.getenv("VOLC_ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    if not model or not api_key:
        return {"questions": []}

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        prompt = (
            f"用户刚刚问了一个问题：{query}\n"
            f"AI 已经给出了回答：{answer[:1200]}...\n\n"
            "请基于以上内容，生成 2-3 条用户接下来最可能追问的问题。\n"
            "要求：每条追问是一个完整问句，简洁有针对性，跟当前话题紧密相关。\n"
            "请直接返回纯 JSON 字符串数组，格式如：[\"问题1\", \"问题2\"]，不要带其他文字。"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=300,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        questions = json.loads(raw)
        return {"questions": questions if isinstance(questions, list) else []}
    except Exception as e:
        print(f"⚠️ [追问生成失败]: {e}")
        return {"questions": []}
