from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.database import feedback_collection
from app.core.schemas import FeedbackModel

router = APIRouter(tags=["feedback"])


@router.post("")
async def save_feedback(
    feedback: FeedbackModel,
    current_user: dict | None = Depends(get_current_user),
):
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
        print(f"❌ [反馈写入异常]: {e}")
        raise HTTPException(status_code=500, detail=f"MongoDB 写入异常: {e}")
