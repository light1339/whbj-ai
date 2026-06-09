import os
from datetime import datetime, timedelta
import sentry_sdk
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.routing import APIRoute
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from starlette.middleware.cors import CORSMiddleware
import bcrypt

from app.core.mdb import (
    client, feedback_collection, users_collection, tokens_collection,
    FeedbackModel, MongoUserModel, TokenModel,
)
from app.core.auth import create_jwt_token, get_current_user, require_user
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


# --- 启动检查 MongoDB ---
@app.on_event("startup")
async def server_on_start():
    try:
        await client.admin.command('ping')
        print("====== ✅ 成功连接到本地 MongoDB 数据库！ ======")
    except Exception as e:
        print(f"====== ❌ MongoDB 连接失败！请检查服务是否开启。错误: {e} ======")


# --- 模板引擎 ---
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


# =====================================================================
# 📬 反馈接口 —— 已登录用户自动带 user_id
# =====================================================================

@app.post("/api/v1/feedback")
async def save_feedback(feedback: FeedbackModel, current_user: dict | None = Depends(get_current_user)):
    try:
        feedback_dict = feedback.model_dump()
        feedback_dict["created_at"] = datetime.now()
        if current_user:
            feedback_dict["user_id"] = current_user["user_id"]

        result = await feedback_collection.insert_one(feedback_dict)
        if result.inserted_id:
            user_tag = f"用户: {current_user['username']} | " if current_user else ""
            print(f"📊 [反馈] {user_tag}ID: {feedback.msg_id} 分数: {feedback.score}")
            return {"status": "success", "message": "反馈已成功同步至本地数据库"}

        raise HTTPException(status_code=500, detail="数据未能成功写入")
    except Exception as e:
        print(f"❌ [反馈写入异常]: {str(e)}")
        raise HTTPException(status_code=500, detail=f"MongoDB 写入异常: {str(e)}")


# =====================================================================
# 🎨 页面路由
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def get_chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# =====================================================================
# 🔓 退出登录 —— 删除 token
# =====================================================================

@app.post("/api/v1/logout")
async def logout(current_user: dict | None = Depends(get_current_user)):
    if current_user:
        await tokens_collection.delete_many({"user_id": current_user["user_id"]})
    return {"status": "success", "message": "已退出"}


# =====================================================================
# 🔐 登录接口 —— JWT + token 表
# =====================================================================

@app.post("/api/v1/login/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_collection.find_one({"username": form_data.username})
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    password_bytes = form_data.password.encode('utf-8')
    hashed_bytes = user["password_hash"].encode('utf-8')
    if not bcrypt.checkpw(password_bytes, hashed_bytes):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    user_id = user.get("user_id")
    # 兼容旧数据：老用户可能没有 user_id，自动补上
    if not user_id:
        import uuid
        user_id = str(uuid.uuid4())
        await users_collection.update_one(
            {"_id": user["_id"]}, {"$set": {"user_id": user_id}}
        )

    # 生成 JWT
    access_token = create_jwt_token(user_id, user["username"])

    # 写入 tokens 表
    token_doc = TokenModel(
        user_id=user_id,
        access_token=access_token,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    await tokens_collection.insert_one(token_doc.model_dump())

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {
            "user_id": user_id,
            "username": user["username"],
            "role": user.get("role", "employee"),
        },
    }
