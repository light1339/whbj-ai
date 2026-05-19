import json
import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from app.core.volc_engine_retriever import knowledge_service_chat_stream

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
    
    # 定义标准的 Server-Sent Events (SSE) 异步流生成包装器
    async def event_generator():
        try:
            # 1. 循环遍历火山大模型一个个吐出来的字块
            for text_chunk in knowledge_service_chat_stream(user_query):
                # 2. 把每个字打包成符合前端解析的标准 JSON SSE 格式
                yield f"data: {json.dumps({'text': text_chunk})}\n\n"
                # 极其微小的延迟确保流传输在网络中更稳定丝滑
                await asyncio.sleep(0.001)
                
            # 3. 大模型全部吐字结束，发送 [DONE] 信号
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            # 异常信息也以流的形式通知前端
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    # 使用 StreamingResponse 抛出流式响应，必须声明 media_type 为 text/event-stream
    return StreamingResponse(event_generator(), media_type="text/event-stream")