"""
TOS（火山引擎对象存储）客户端工具模块。
使用火山引擎原生 TOS SDK（非 boto3 S3 兼容接口）。
"""
import uuid
from tos import TosClientV2

from app.core.volc_config import (
    TOS_ACCESS_KEY_ID,
    TOS_SECRET_ACCESS_KEY,
    TOS_BUCKET,
    TOS_REGION,
    TOS_ENDPOINT,
)


def _get_client() -> TosClientV2:
    """获取 TOS 原生客户端"""
    return TosClientV2(
        ak=TOS_ACCESS_KEY_ID,
        sk=TOS_SECRET_ACCESS_KEY,
        endpoint=TOS_ENDPOINT,
        region=TOS_REGION,
    )


def upload_bytes(
    data: bytes,
    key: str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    上传字节数据到 TOS，返回公网访问 URL。

    Args:
        data: 文件字节数据
        key: TOS 对象路径（如 videos/xxx.mp4）
        content_type: 文件的 MIME 类型
    Returns:
        公网 URL，如 https://whbj-video-2026.tos-cn-shanghai.volces.com/videos/xxx.mp4
    """
    client = _get_client()
    client.put_object(
        bucket=TOS_BUCKET,
        key=key,
        content=data,
        content_type=content_type,
    )
    return f"https://{TOS_BUCKET}.tos-{TOS_REGION}.volces.com/{key}"


def upload_file_bytes(
    file_data: bytes,
    filename: str,
    folder: str = "videos",
) -> str:
    """
    上传文件字节数据到 TOS，自动生成路径。

    Args:
        file_data: 文件字节数据
        filename: 原始文件名（只取扩展名）
        folder: TOS 上的文件夹路径
    Returns:
        公网 URL
    """
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "mp4"
    key = f"{folder}/{uuid.uuid4()}.{ext}"

    content_type_map = {
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "webm": "video/webm",
        "avi": "video/x-msvideo",
        "mkv": "video/x-matroska",
    }
    content_type = content_type_map.get(ext.lower(), "application/octet-stream")

    return upload_bytes(file_data, key, content_type)
