import jwt
import os
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from app.core.mdb import tokens_collection, users_collection

SECRET_KEY = os.getenv("SECRET_KEY", "changethis")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login/token", auto_error=False)


def create_jwt_token(user_id: str, username: str) -> str:
    """生成 JWT token"""
    payload = {
        "sub": user_id,
        "username": username,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt_token(token: str) -> dict | None:
    """解码 JWT，不抛异常，失败返回 None"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict | None:
    """
    认证依赖注入 —— 放路由参数里即可校验身份。
    校验通过返回 user 文档（含 user_id, username, role），
    未登录返回 None（不报 401，方便接口兼容未登录场景）。
    """
    if not token:
        return None

    payload = decode_jwt_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    # 从 DB 查用户确保存在（tokens 表只存 token，user 表管用户状态）
    user = await users_collection.find_one({"user_id": user_id})
    if not user:
        return None

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user.get("role", "employee"),
    }


async def require_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    严格认证依赖 —— 必须登录，否则 401。
    给需要强制认证的接口使用。
    """
    user = await get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user
