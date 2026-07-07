import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["pages"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def read_template(filename: str) -> str:
    """读取模板文件内容"""
    filepath = os.path.join(TEMPLATES_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


@router.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return HTMLResponse(content=read_template("chat.html"))


@router.get("/video", response_class=HTMLResponse)
async def video_page(request: Request):
    return HTMLResponse(content=read_template("video.html"))


@router.get("/image", response_class=HTMLResponse)
async def image_page(request: Request):
    return HTMLResponse(content=read_template("image.html"))


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return HTMLResponse(content=read_template("login.html"))
