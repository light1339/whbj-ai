import json
import asyncio
import time
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from openai import OpenAI
from app.core.volc_config import KB_POOL, VOLC_ARK_API_KEY, VOLC_ARK_BASE_URL, VOLC_ARK_MODEL, VOLC_KB_API_KEY
from app.core.volc_retriever import retrieve_multi, check_broad_query
from app.core.database import search_logs_collection
from app.core.schemas import SearchLogModel
from app.core.auth import get_current_user

router = APIRouter()


def _resolve_kb_ids(user: dict | None) -> list[str]:
    kb_ids = []
    if user:
        for label in user.get("kb_access", ["default"]):
            kid = KB_POOL.get(label)
            if kid:
                kb_ids.append(kid)
    return kb_ids or [KB_POOL["default"]]


def _stream_knowledge_response(query: str, deep_think: bool, kb_ids: list[str]):
    # 宽泛提问拦截已禁用
    # clarify_msg = check_broad_query(query)
    # if clarify_msg:
    #     yield clarify_msg
    #     return

    kb_ids = [k for k in kb_ids if k]
    print(f"[检索] 查询 {len(kb_ids)} 个库: {[k[:25]+'...' for k in kb_ids]}")

    raw_context, timed_out = retrieve_multi(query, kb_ids)

    if timed_out and raw_context:
        raw_context += (
            "\n\n⚠️ 搜索时间较长，以上为已检索到的部分内容。"
            "\n💡 建议您缩小问题范围或补充更具体的关键词，以获得更完整的答案。"
        )

    # ── 默认模式：直接返回知识库结果，无内容就提示 ──
    if not deep_think:
        print("[深度思考关闭] 跳过 LLM 加工，直接返回原文")
        if not raw_context:
            yield "抱歉，在知识库中未找到与该问题相关的内容，请您联系合规专家团队进一步咨询。"
        else:
            for char in raw_context:
                yield char
        return

    # ── 深度思考模式：直接将用户问题交给大模型回答 ──
    llm_api_key = VOLC_ARK_API_KEY or VOLC_KB_API_KEY
    if not VOLC_ARK_MODEL:
        print("[深度思考] 未配置 VOLC_ARK_MODEL，跳过 LLM 加工")
        if not raw_context:
            yield "抱歉，在知识库中未找到与该问题相关的内容，请您联系合规专家团队进一步咨询。"
        else:
            for char in raw_context:
                yield char
        return

    try:
        client = OpenAI(api_key=llm_api_key, base_url=VOLC_ARK_BASE_URL)
        system_prompt = (
            "你是一位知识渊博、耐心友善的智能助手。\n"
            "请用通俗易懂、条理清晰的方式回答用户的问题。\n"
            "回答要简洁实用，避免冗长啰嗦。如果不确定，可以坦诚说明。"
        )
        response = client.chat.completions.create(
            model=VOLC_ARK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.7,
            stream=True,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        print(f"⚠️ [大模型流式回答异常]: {e}")
        if not raw_context:
            yield "抱歉，在知识库中未找到与该问题相关的内容，请您联系合规专家团队进一步咨询。"
        else:
            for char in raw_context:
                yield char


@router.post("/chat")
async def chat_with_knowledge_base(
    request: Request, current_user: dict | None = Depends(get_current_user)
):
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
    kb_ids = _resolve_kb_ids(current_user)

    async def event_generator():
        nonlocal full_response, search_status, error_detail
        try:
            for text_chunk in _stream_knowledge_response(user_query, deep_think, kb_ids):
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
                model=VOLC_ARK_MODEL or "",
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


@router.post("/chat/extend")
async def get_extend_questions(
    request: Request, current_user: dict | None = Depends(get_current_user)
):
    try:
        body = await request.json()
        query = body.get("query", "").strip()
        answer = body.get("answer", "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")

    if not query or not answer:
        return {"questions": []}

    if not VOLC_ARK_MODEL or not (VOLC_ARK_API_KEY or VOLC_KB_API_KEY):
        return {"questions": []}

    try:
        client = OpenAI(
            api_key=VOLC_ARK_API_KEY or VOLC_KB_API_KEY,
            base_url=VOLC_ARK_BASE_URL,
        )
        prompt = (
            f"用户刚刚问了一个问题：{query}\n"
            f"AI 已经给出了回答：{answer[:1200]}...\n\n"
            "请基于以上内容，生成 2-3 条用户接下来最可能追问的问题。\n"
            "要求：每条追问是一个完整问句，简洁有针对性，跟当前话题紧密相关。\n"
            '请直接返回纯 JSON 字符串数组，格式如：["问题1", "问题2"]，不要带其他文字。'
        )
        resp = client.chat.completions.create(
            model=VOLC_ARK_MODEL,
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
