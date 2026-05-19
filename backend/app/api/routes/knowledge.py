from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
# 引入你刚才测试成功的核心检索函数
from app.core.volc_engine_retriever import knowledge_service_chat

router = APIRouter()

# 定义前端传过来的请求数据格式
class ChatRequest(BaseModel):
    query: str

@router.post("/chat")
async def chat_with_knowledge_base(payload: ChatRequest):
    """
    火山引擎知识库专属检索接口
    """
    user_query = payload.query.strip()
    
    if not user_query:
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    
    try:
        # 调用你写好的火山引擎核心函数
        answer = knowledge_service_chat(user_query)
        
        # 返回标准的 JSON 给前端
        return {
            "status": "success",
            "data": {
                "answer": answer
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识库检索失败: {str(e)}")