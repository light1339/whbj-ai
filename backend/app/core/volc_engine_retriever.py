#!/usr/bin/env python3
"""
火山引擎知识库检索器 + 豆包大模型智能润色 (RAG 完整体)

本文件实现了与火山引擎知识库的交互功能，提供以下特性：
1. 环境变量配置管理
2. 知识库精准检索功能 (Retrieve)
3. 联动豆包大模型进行智能 HR 语气润色 (Generation)
"""

import json
import re
import requests
import os
from dotenv import load_dotenv
from volcengine.base.Request import Request
from openai import OpenAI

# 加载环境变量（自动查找 .env 文件）
load_dotenv()
# 临时调试，确认后可删除
print(f"[DEBUG] 当前使用知识库ID: {os.getenv('VOLC_KNOWLEDGE_SERVICE_ID')}")
print(f"[DEBUG] 当前使用API Key前8位: {str(os.getenv('VOLC_KNOWLEDGE_API_KEY'))[:8]}")
# 火山引擎配置
g_knowledge_base_domain = "api-knowledgebase.mlp.cn-beijing.volces.com"

# 从环境变量动态读取
apikey = os.getenv("VOLC_KNOWLEDGE_API_KEY")
service_resource_id = os.getenv("VOLC_KNOWLEDGE_SERVICE_ID")

# 大模型相关配置
volc_ark_api_key = os.getenv("VOLC_ARK_API_KEY")
volc_ark_base_url = os.getenv("VOLC_ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
volc_ark_model = os.getenv("VOLC_ARK_MODEL")  # 使用你 env 里配的接入点名称（通常是 ep-xxx 形式的推理接入点）

# 强制校验：如果环境变量未设置，立即报错
if not apikey:
    raise ValueError("错误：未设置环境变量 VOLC_KNOWLEDGE_API_KEY，请在 .env 文件中配置")
if not service_resource_id:
    raise ValueError("错误：未设置环境变量 VOLC_KNOWLEDGE_SERVICE_ID，请在 .env 文件中配置")


def prepare_request(method, path, params=None, data=None, doseq=0):
    """
    准备 HTTP 请求对象
    """
    if params:
        for key in params:
            if isinstance(params[key], (int, float, bool)):
                params[key] = str(params[key])
            elif isinstance(params[key], list) and not doseq:
                params[key] = ",".join(params[key])
    
    r = Request()
    r.set_shema("https")
    r.set_method(method)
    r.set_connection_timeout(10)
    r.set_socket_timeout(10)
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json;charset=UTF-8",
        "Host": g_knowledge_base_domain,
        'Authorization': f'Bearer {apikey}'
    }
    r.set_headers(headers)
    
    if params:
        r.set_query(params)
    
    r.set_host(g_knowledge_base_domain)
    r.set_path(path)
    
    if data is not None:
        r.set_body(json.dumps(data))
    
    return r


def _get_raw_knowledge_context(query: str) -> str:
    """
    内部核心函数：仅负责去火山引擎知识库捞取最相关的原始文档干货
    """
    method = "POST"
    path = "/api/knowledge/service/chat"
    
    prompt = f"请提取出与用户问题相关的、完整的文档内容。用户问题：{query}"
    
    request_params = {
        "service_resource_id": service_resource_id,
        "messages": [
            {"role": "system", "content": "你是一个严谨的文档检索助手，只负责完整提取相关的原文条文。"},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    info_req = prepare_request(method=method, path=path, data=request_params)
    
    try:
        rsp = requests.request(
            method=info_req.method,
            url=f"https://{info_req.host}{info_req.path}",
            headers=info_req.headers,
            data=info_req.body,
            timeout=(30, 360)
        )
        rsp.encoding = "utf-8"
        result = rsp.json()
        
        if "data" in result and "generated_answer" in result["data"]:
            answer = result["data"]["generated_answer"]
            answer = re.sub(r'<reference\s+data-ref="[^"]+">.*?</reference>', '', answer, flags=re.DOTALL)
            answer = re.sub(r'<illustration.*?>.*?</illustration>', '', answer, flags=re.DOTALL)
            return answer.strip()
            
        elif "data" in result and "result" in result["data"]:
            chunks = []
            for chunk in result["data"]["result"]:
                content = chunk.get('content', '')
                content = re.sub(r'<reference\s+data-ref="[^"]+">.*?</reference>', '', content, flags=re.DOTALL)
                content = re.sub(r'<illustration.*?>.*?</illustration>', '', content, flags=re.DOTALL)
                if content:
                    chunks.append(content)
            return "\n".join(chunks)
    except Exception as e:
        print(f"[Warning] 知识库原生检索阶段发生异常: {str(e)}")
        
    return ""


# def knowledge_service_chat(query: str) -> str:
#     """
#     对外主入口：知识库纯检索 + 豆包大模型智能 HR 润色 (非流式一次性返回旧版本)
#     """
#     raw_context = _get_raw_knowledge_context(query)
#     if not raw_context or "未获取到有效回答" in raw_context:
#         raw_context = "（暂无相关内容参考，待补充）"

#     llm_api_key = volc_ark_api_key or apikey
#     llm_base_url = volc_ark_base_url
    
#     if not volc_ark_model or volc_ark_model.startswith("gpt"):
#         print("\n📄 [高可用兜底] 未检测到有效的豆包模型 Endpoint，直接返回原始知识库内容。")
#         return raw_context

#     try:
#         client = OpenAI(api_key=llm_api_key, base_url=llm_base_url)
#         system_prompt = (
#         "你是一位非常专业、严谨、权威的智能政策问答专家及合规审查顾问。\n"
#         "请结合以下由官方提供的【政策法规、公司内部规章制度及安全生产合规标准参考材料】，来回答用户的业务或合规疑问。\n\n"
#         "【核心行为准则】:\n"
#         "1. 必须优先基于给定的【参考材料】进行回答。回答要条理分明、逻辑清晰，尽可能保留原条文的结构（如一、1、等）。\n"
#         "2. 语气要保持客观、专业、严谨且富有耐心，多使用'您'、'根据相关政策规定'等职场表述，符合政策专家的形象。\n"
#         "3. 如果材料中有明确的时间节点、执行标准、法律责任或处罚力度（例如：2020年4月1日启动，处以特定罚款等），请务必极其准确、全面地告知用户。\n"
#         "4. 如果参考材料里【完全没有】提到用户询问的政策或制度细节，请委婉且专业地回应：'您好，目前的政策库与规章制度库中暂未查到相关细节说明。"
#         "为了不误导您，建议您直接联系合规专家团队或查看内部最新公告哦。'，绝对不能凭空瞎编或捏造政策法条与制度。\n"
#         "5. 本次对话可能包含用户的历史连续追问，请深刻结合上下文理解其真实的合规意图，确保前后政策与制度解读的一致性与连贯性。\n\n"
#         f"【政策法规及内部规章制度参考材料】:\n{raw_context}"
#         )
        
#         completion = client.chat.completions.create(
#             model=volc_ark_model,
#             messages=[
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": query}
#             ],
#             temperature=0.3,
#         )
#         return completion.choices[0].message.content.strip()
#     except Exception as e:
#         print(f"\n⚠️ [大模型润色异常]: {str(e)} -> 触发高可用兜底，直接返回原始知识库。")
#         return raw_context


def knowledge_service_chat_stream(query: str, deep_think: bool = False):
    """
    RAG 流式打字机输出

    deep_think=False: 只做知识库检索，直接返回原文（快）
    deep_think=True:  检索 + 豆包 LLM 语义加工润色（慢但更专业）
    """
    # 1. 召回原始知识库干货
    raw_context = _get_raw_knowledge_context(query)

    if not raw_context or "未获取到有效回答" in raw_context:
        raw_context = "（暂无相关内容参考）"

    # ── 不深度思考：直接流式返回原文 ──
    if not deep_think:
        print("[深度思考关闭] 跳过 LLM 加工，直接返回知识库原文")
        for char in raw_context:
            yield char
        return

    # ── 深度思考模式：LLM 语义加工 ──
    llm_api_key = volc_ark_api_key or apikey
    llm_base_url = volc_ark_base_url
    
    # 健全性检查：如果没有配模型接入点，则直接将原始知识库切字流式返回进行兜底
    if not volc_ark_model or volc_ark_model.startswith("gpt"):
        print("\n📄 [高可用流式兜底] 未检测到有效的豆包模型 Endpoint，流式返回原始知识库内容。")
        for char in raw_context:
            yield char
        return

    try:
        # 2. 初始化大模型客户端
        client = OpenAI(
            api_key=llm_api_key,
            base_url=llm_base_url
        )
        
        system_prompt = (
        "你是一位非常专业、严谨、权威的智能政策问答专家及合规审查顾问。\n"
        "请结合以下由官方提供的【政策法规、公司内部规章制度及安全生产合规标准参考材料】，来回答用户的业务或合规疑问。\n\n"
        "【核心行为准则】:\n"
        "1. 必须优先基于给定的【参考材料】进行回答。回答要条理分明、逻辑清晰，尽可能保留原条文的结构（如一、1、等）。\n"
        "2. 语气要保持客观、专业、严谨且富有耐心，多使用'您'、'根据相关政策规定'等职场表述，符合政策专家的形象。\n"
        "3. 如果材料中有明确的时间节点、执行标准、法律责任或处罚力度（例如：2020年4月1日启动，处以特定罚款等），请务必极其准确、全面地告知用户。\n"
        "4. 如果参考材料里【完全没有】提到用户询问的政策或制度细节，请委婉且专业地回应：'您好，目前的政策库与规章制度库中暂未查到相关细节说明。"
        "为了不误导您，建议您直接联系合规专家团队或查看内部最新公告哦。'，绝对不能凭空瞎编或捏造政策法条与制度。\n"
        "5. 本次对话可能包含用户的历史连续追问，请深刻结合上下文理解其真实的合规意图，确保前后政策与制度解读的一致性与连贯性。\n\n"
        f"【政策法规及内部规章制度参考材料】:\n{raw_context}"
        )
        
        # 3. 🔥 开启 stream=True
        response = client.chat.completions.create(
            model=volc_ark_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            stream=True  # 开启大模型流式返回
        )
        
        # 4. 🔥 源源不断地把吐出来的字 yield 出去
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        print(f"\n⚠️ [大模型流式润色异常]: {str(e)} -> 触发流式兜底。")
        for char in raw_context:
            yield char


if __name__ == "__main__":
    query = "12月份淘宝营业额度是多少？"
    for text in knowledge_service_chat_stream(query):
        print(text, end="", flush=True)