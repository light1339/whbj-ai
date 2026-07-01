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

if not VOLC_KB_API_KEY:
    print("⚠️ 警告: 未设置 VOLC_KNOWLEDGE_API_KEY，知识库功能将不可用")
if not KB_POOL["default"]:
    print("⚠️ 警告: 未设置 VOLC_KNOWLEDGE_SERVICE_ID，知识库功能将不可用")
