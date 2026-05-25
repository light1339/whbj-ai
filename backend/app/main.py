import os
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
import bcrypt
from datetime import datetime
import sentry_sdk
from fastapi import FastAPI, Request, HTTPException
from fastapi.routing import APIRoute
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
# 🚀 把它修改成这样，把模型和需要的集合全部从 core.db 拿过来
from .core.mdb import client, feedback_collection, users_collection, search_logs_collection, FeedbackModel,MongoUserModel
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


# --- 🔍 新增：启动时强制检查 MongoDB 连接是否真的通了 ---
@app.on_event("startup")
async def server_on_start():
    try:
        # 发送一个 ping 命令测试连接
        await client.admin.command('ping')
        print("====== 🎉 成功连接到本地 MongoDB 数据库！ ======")
    except Exception as e:
        print(f"====== ❌ MongoDB 连接失败！请检查服务是否开启。错误: {e} ======")


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


# --- 📬 3. 接收前端反馈并写入 MongoDB 的接口 ---
@app.post("/api/v1/feedback")
async def save_feedback(feedback: FeedbackModel):
    try:
        # 1. 将 Pydantic 模型转为原生 Python 字典
        # 使用你 main.py 里的 model_dump() 
        feedback_dict = feedback.model_dump()
        
        # 2. 在这里单独追加服务器标准时间戳，存入 MongoDB，完美避开 Pydantic 校验冲突
        feedback_dict["created_at"] = datetime.now()
        
        # 3. 异步插入到 MongoDB 数据库中
        result = await feedback_collection.insert_one(feedback_dict)
        
        if result.inserted_id:
            print(f"📊 [MongoDB 成功写入] 收到新反馈！ID: {feedback.msg_id}，分数: {feedback.score}")
            return {"status": "success", "message": "反馈已成功同步至本地数据库"}
            
        raise HTTPException(status_code=500, detail="数据未能成功写入")
    except Exception as e:
        print(f"❌ [MongoDB 写入异常]: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MongoDB 写入异常: {str(e)}")


# --- 🎨 根路径路由返回聊天页面 ---
@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

# =====================================================================
# backend/app/main.py 追加页面跳转与标准登录路由
# =====================================================================
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
import bcrypt

# 1. 🎨 路由：访问 /login 返回登录页面
@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# 2. 🔐 API：标准的 JWT 登录认证接口 (供前端表单异步调用)
@app.post("/api/v1/login/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # 🔍 去 MongoDB 查用户名是否存在
    user = await users_collection.find_one({"username": form_data.username})
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    # 🔍 校验密码（利用原生 bcrypt 的 checkpw 验证明文和哈希密文）
    password_bytes = form_data.password.encode('utf-8')
    hashed_bytes = user["password_hash"].encode('utf-8')
    
    if not bcrypt.checkpw(password_bytes, hashed_bytes):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    
    # 🎟️ 验证成功！返回标准的 Token 数据结构
    # （这里暂用 mock 令牌，后续加解密算法直接替换字符串即可，不影响前后端联调）
    return {
        "access_token": f"mock_token_for_{user['username']}",
        "token_type": "bearer",
        "user_info": {                    # 👈 补上前端期待的嵌套结构
            "username": user["username"],
            "role": user.get("role", "employee")
        }
    }