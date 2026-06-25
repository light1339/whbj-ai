import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.core.database import client
from app.api.main import api_router
from app.api.routes.pages import router as pages_router
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


@app.on_event("startup")
async def startup_event():
    try:
        await client.admin.command("ping")
        print("====== ✅ 成功连接到 MongoDB Atlas 云数据库！ ======")
    except Exception as e:
        print(f"====== ❌ MongoDB 连接失败！请检查服务是否开启。错误: {e} ======")


if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(pages_router)
app.include_router(api_router, prefix=settings.API_V1_STR)
