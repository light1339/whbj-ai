# backend/app/core/mdb.py
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from datetime import datetime

# 1. 🔌 统一连接本地 MongoDB
MONGO_DETAILS = "mongodb://127.0.0.1:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["hr_assistant_db"]

# 2. 🗂️ 统一挂载集合
feedback_collection = db["feedbacks"]
search_logs_collection = db["search_logs"]
users_collection = db["users"]
tokens_collection = db["tokens"]              # ← 新增 token 表


# 3. 📝 Pydantic 模型

class MongoUserModel(BaseModel):
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="用户唯一 ID")
    username: str = Field(..., description="登录用户名")
    password_hash: str = Field(..., description="加密后的密码哈希值")
    role: str = Field(default="employee", description="角色权限: hr / employee")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="注册时间")


class TokenModel(BaseModel):
    user_id: str = Field(..., description="关联用户 ID")
    access_token: str = Field(..., description="JWT 令牌")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="过期时间")


class FeedbackModel(BaseModel):
    msg_id: str = Field(..., description="消息的唯一ID")
    user_id: str | None = Field(default=None, description="操作人 ID")
    query: str = Field("", description="员工当时的问题")
    score: int = Field(..., ge=1, le=5, description="1-5 星打分")
    comment: str = Field("", description="员工填写的改进意见")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SearchLogModel(BaseModel):
    query: str = Field(..., description="用户的搜索问题")
    user_id: str | None = Field(default=None, description="操作人 ID")
    source: str = Field(default="volc_knowledge_base", description="知识库来源")
    model: str = Field(default="", description="使用的模型名称")
    response_time_ms: int = Field(default=0, description="响应耗时（毫秒）")
    user_ip: str | None = Field(default=None, description="用户 IP 地址")
    status: str = Field(default="success", description="请求状态: success / error")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="搜索时间")
