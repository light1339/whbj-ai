from fastapi import APIRouter

from app.api.routes import items, login, private, users, utils, knowledge, admin, auth, feedback, video, image, tools
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(video.router, prefix="/video", tags=["video"])
api_router.include_router(image.router, prefix="/image", tags=["image"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(auth.router)
api_router.include_router(feedback.router, prefix="/feedback")
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
