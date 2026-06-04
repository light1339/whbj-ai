# backend/app/core/db.py
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from datetime import datetime

# 1. 🔌 统一连接本地 MongoDB
MONGO_DETAILS = "mongodb://127.0.0.1:27017"
client = AsyncIOMotorClient(MONGO_DETAILS)
db = client["hr_assistant_db"]

# 2. 🗂️ 统一挂载集合（表名），让整个后端随时可以调用
feedback_collection = db["feedbacks"]       # 你原有的评价表
search_logs_collection = db["search_logs"]  # 审计日志表
users_collection = db["users"]              # 用户账户表


# 3. 📝 统一存放跟 MongoDB 挂钩的 Pydantic 模型
class FeedbackModel(BaseModel):
    msg_id: str = Field(..., description="消息的唯一ID")
    query: str = Field("", description="员工当时的问题")
    score: int = Field(..., ge=1, le=5, description="1-5星打分")
    comment: str = Field("", description="员工填写的改进意见")

class MongoUserModel(BaseModel):
    username: str = Field(..., description="登录用户名")
    password_hash: str = Field(..., description="加密后的密码哈希值")
    role: str = Field(default="employee", description="角色权限: hr / employee")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="注册时间")


class SearchLogModel(BaseModel):
    query: str = Field(..., description="用户的搜索问题")
    response_length: int = Field(default=0, description="AI 回复字数（不保存原文，太长无意义）")
    source: str = Field(default="volc_knowledge_base", description="知识库来源")
    model: str = Field(default="", description="使用的模型名称")
    response_time_ms: int = Field(default=0, description="响应耗时（毫秒）")
    user_ip: str | None = Field(default=None, description="用户 IP 地址")
    status: str = Field(default="success", description="请求状态: success / error")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="搜索时间")