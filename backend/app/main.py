import os
from datetime import datetime
import sentry_sdk
from fastapi import FastAPI, Request, HTTPException
from fastapi.routing import APIRoute
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.main import api_router
from app.core.config import settings


def custom_generate_unique_id(route: APIRoute) -> str:
    if not route.tags or not route.tags[0]:
        return route.name
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

# --- 🚀 1. 初始化 MongoDB 异步客户端（将 localhost 换成更稳妥的 127.0.0.1） ---
MONGO_DETAILS = "mongodb://127.0.0.1:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["hr_assistant_db"]          # 数据库名
feedback_collection = db["feedbacks"]   # 集合名


# --- 🔍 新增：启动时强制检查 MongoDB 连接是否真的通了 ---
@app.on_event("startup")
async def server_on_start():
    try:
        # 发送一个 ping 命令测试连接
        await client.admin.command('ping')
        print("====== 🎉 成功连接到本地 MongoDB 数据库！ ======")
    except Exception as e:
        print(f"====== ❌ MongoDB 连接失败！请检查服务是否开启。错误: {e} ======")


# --- 📝 2. 定义打分留言的数据结构 (Pydantic) ---
class FeedbackModel(BaseModel):
    msg_id: str = Field(..., description="消息的唯一ID")
    query: str = Field("", description="员工当时问的问题")
    score: int = Field(..., ge=1, le=5, description="1-5星打分")
    comment: str = Field("", description="员工填写的改进意见")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- ⚙️ 初始化模板引擎 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


# --- 📬 3. 新增：接收前端反馈并写入 MongoDB 的接口 ---
@app.post("/api/v1/feedback")
async def save_feedback(feedback: FeedbackModel):
    try:
        # 将 Pydantic 模型转为字典
        feedback_dict = feedback.model_dump()
        # 异步插入到 MongoDB
        result = await feedback_collection.insert_one(feedback_dict)
        return {"status": "success", "message": "反馈保存成功", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库写入失败: {str(e)}")


# --- 🎨 根路径路由返回聊天页面 ---
@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})