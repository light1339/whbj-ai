from typing import Any
from fastapi import APIRouter, Query
from app.core.database import search_logs_collection

router = APIRouter()


@router.get("/logs")
async def get_search_logs(limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
    """
    查看最近 N 条搜索日志
    访问: http://localhost:8000/api/v1/admin/logs?limit=50
    """
    logs: list[dict[str, Any]] = []
    cursor = search_logs_collection.find().sort("created_at", -1).limit(limit)
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        logs.append(doc)

    total = await search_logs_collection.estimated_document_count()
    return {"total": total, "count": len(logs), "logs": logs}
