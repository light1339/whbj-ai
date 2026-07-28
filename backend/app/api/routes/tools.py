from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId

from app.core.database import tools_collection

router = APIRouter()


# 默认工具配置
DEFAULT_TOOLS = [
    {
        "name": "法规解读助手",
        "prompt": "你是一位专业的危化品运输法规解读专家。请基于最新的《道路危险货物运输管理规定》、《危险化学品安全管理条例》等法规，用通俗易懂的语言解读法规条款，帮助用户理解合规要求。回答时请引用具体的法规名称和条款编号。"
    },
    {
        "name": "国标查询助手",
        "prompt": "你是一位熟悉危险货物运输国家标准（GB）的技术专家。请准确回答关于 GB 21668、GB 13392、JT/T 617 等技术标准的问题，包括技术要求、检测方法、实施时间等。回答时请标注标准号和具体条款。"
    },
    {
        "name": "安全合规检查",
        "prompt": "你是一位危化品运输企业的安全合规顾问。请帮助企业检查运输资质、车辆设备、人员培训、应急预案等方面是否符合法规要求。发现问题时请指出违反的具体条款，并给出整改建议。"
    },
    {
        "name": "事故应急指导",
        "prompt": "你是一位危化品事故应急处置专家。请根据事故类型（泄漏、火灾、中毒等）和危化品类别，提供应急处置步骤、人员防护要求、环境保护措施和报告流程。回答要简洁实用，便于现场快速参考。"
    },
    {
        "name": "运输资质咨询",
        "prompt": "你是一位熟悉危化品运输资质管理的专业人士。请回答关于经营许可证办理、车辆运输证申请、驾驶员和押运员资格认证、企业安全生产许可等问题。回答时请说明申请条件、所需材料和办理流程。"
    }
]


async def init_default_tools():
    """初始化默认工具（如果数据库为空）"""
    count = await tools_collection.count_documents({})
    if count == 0:
        print("[工具初始化] 数据库为空，正在创建 5 个默认工具...")
        now = datetime.utcnow()
        for tool in DEFAULT_TOOLS:
            await tools_collection.insert_one({
                "name": tool["name"],
                "prompt": tool["prompt"],
                "created_at": now
            })
        print(f"[工具初始化] ✅ 成功创建 {len(DEFAULT_TOOLS)} 个默认工具")


class ToolCreate(BaseModel):
    name: str
    prompt: str


class ToolUpdate(BaseModel):
    name: str | None = None
    prompt: str | None = None


def _tool_doc_to_dict(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("/")
async def list_tools():
    tools = []
    async for doc in tools_collection.find().sort("created_at", -1):
        tools.append(_tool_doc_to_dict(doc))
    return {"tools": tools}


@router.post("/")
async def create_tool(tool: ToolCreate):
    doc = {
        "name": tool.name.strip(),
        "prompt": tool.prompt.strip(),
        "created_at": datetime.utcnow(),
    }
    result = await tools_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _tool_doc_to_dict(doc)


@router.put("/{tool_id}")
async def update_tool(tool_id: str, tool: ToolUpdate):
    if not ObjectId.is_valid(tool_id):
        raise HTTPException(status_code=400, detail="无效的工具 ID")

    update_data = {}
    if tool.name is not None:
        update_data["name"] = tool.name.strip()
    if tool.prompt is not None:
        update_data["prompt"] = tool.prompt.strip()

    if not update_data:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    result = await tools_collection.update_one(
        {"_id": ObjectId(tool_id)}, {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="工具不存在")

    doc = await tools_collection.find_one({"_id": ObjectId(tool_id)})
    return _tool_doc_to_dict(doc)


@router.delete("/{tool_id}")
async def delete_tool(tool_id: str):
    if not ObjectId.is_valid(tool_id):
        raise HTTPException(status_code=400, detail="无效的工具 ID")

    result = await tools_collection.delete_one({"_id": ObjectId(tool_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="工具不存在")

    return {"message": "删除成功"}


@router.get("/{tool_id}")
async def get_tool(tool_id: str):
    if not ObjectId.is_valid(tool_id):
        raise HTTPException(status_code=400, detail="无效的工具 ID")

    doc = await tools_collection.find_one({"_id": ObjectId(tool_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="工具不存在")

    return _tool_doc_to_dict(doc)
