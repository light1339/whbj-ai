import uuid
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.core.auth import create_jwt_token, get_current_user
from app.core.database import users_collection, tokens_collection
from app.core.schemas import TokenModel

router = APIRouter(tags=["auth"])


@router.post("/login/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_collection.find_one({"username": form_data.username})
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    if not bcrypt.checkpw(form_data.password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    user_id = user.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        await users_collection.update_one({"_id": user["_id"]}, {"$set": {"user_id": user_id}})

    access_token = create_jwt_token(user_id, user["username"])

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
            "kb_access": user.get("kb_access", ["default"]),
        },
    }


@router.post("/logout")
async def logout(current_user: dict | None = Depends(get_current_user)):
    if current_user:
        await tokens_collection.delete_many({"user_id": current_user["user_id"]})
    return {"status": "success", "message": "已退出"}
