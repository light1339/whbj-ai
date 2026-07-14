import os
from dotenv import load_dotenv

load_dotenv()

VOLC_KB_DOMAIN = "api-knowledgebase.mlp.cn-beijing.volces.com"

VOLC_KB_API_KEY = os.getenv("VOLC_KNOWLEDGE_API_KEY")

KB_POOL: dict[str, str] = {
    "default": os.getenv("VOLC_KNOWLEDGE_SERVICE_ID", ""),
    "manage": os.getenv("VOLC_KNOWLEDGE_SERVICE_ID_2", ""),
}

VOLC_ARK_API_KEY = os.getenv("VOLC_ARK_API_KEY")
VOLC_ARK_BASE_URL = os.getenv("VOLC_ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
VOLC_ARK_MODEL = os.getenv("VOLC_ARK_MODEL")

# 视频生成配置
VOLC_VIDEO_API_KEY = os.getenv("VOLC_VIDEO_API_KEY")
VOLC_VIDEO_BASE_URL = os.getenv("VOLC_VIDEO_BASE_URL", "https://video.cn-beijing.volces.com/api/v1")
VOLC_VIDEO_MODEL = os.getenv("VOLC_VIDEO_MODEL", "doubao-seedance-2-0-260128")

# TOS 对象存储配置
TOS_ACCESS_KEY_ID = os.getenv("TOS_ACCESS_KEY_ID")
TOS_SECRET_ACCESS_KEY = os.getenv("TOS_SECRET_ACCESS_KEY")
TOS_BUCKET = os.getenv("TOS_BUCKET")
TOS_REGION = os.getenv("TOS_REGION", "cn-shanghai")
TOS_ENDPOINT = os.getenv("TOS_ENDPOINT", "https://tos-cn-shanghai.volces.com")

# OpenAI 图片生成配置
OPENAI_IMAGE_API_KEY = os.getenv("OPENAI_IMAGE_API_KEY")
OPENAI_IMAGE_BASE_URL = os.getenv("OPENAI_IMAGE_BASE_URL", "https://api.openai.com/v1")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

if not VOLC_KB_API_KEY:
    print("⚠️ 警告: 未设置 VOLC_KNOWLEDGE_API_KEY，知识库功能将不可用")
if not KB_POOL["default"]:
    print("⚠️ 警告: 未设置 VOLC_KNOWLEDGE_SERVICE_ID，知识库功能将不可用")
