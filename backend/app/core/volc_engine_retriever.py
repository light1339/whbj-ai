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
    
    # 调整 Prompt：命令知识库的 Agent 尽可能完整、详细地吐出原始规章制度，不要做过多精简
    prompt = f"请提取出与用户问题相关的、完整的规章制度核心条文片段。用户问题：{query}"
    
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
        
        # 优先从检索生成的回答里拿，如果没有，从原始 chunks 拼接里拿
        if "data" in result and "generated_answer" in result["data"]:
            answer = result["data"]["generated_answer"]
            # 清理可能存在的标签
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


def knowledge_service_chat(query: str) -> str:
    """
    对外主入口：知识库纯检索 + 豆包大模型智能 HR 润色 (RAG 完整体)
    
    Args:
        query: 用户的问题
    
    Returns:
        str: 豆包大模型结合知识库规章，用 HR 语气润色后的完美大白话回答
    """
    # 1. 召回原始知识库干货
    raw_context = _get_raw_knowledge_context(query)
    
    # 2. 如果知识库完全没捞到有效东西，或者抛错，给个空兜底标识
    if not raw_context or "未获取到有效回答" in raw_context:
        raw_context = "（暂无相关公司内部规章制度参考）"

    # 3. 准备调用你在 .env 里配好的豆包大模型 (豆包完全兼容 OpenAI 协议)
    llm_api_key = volc_ark_api_key or apikey
    llm_base_url = volc_ark_base_url
    
    # 健全性检查：如果没有配模型接入点，则直接高可用降级，返回原始知识库内容
    if not volc_ark_model or volc_ark_model.startswith("gpt"):
        # 如果 env 里的 OPENAI_MODEL 是 gpt 或者是空的，为了防止报错，我们直接返回原始知识库
        print("\n📄 [高可用兜底] 未检测到有效的豆包模型 Endpoint，直接返回原始知识库内容。")
        return raw_context

    try:
        # 4. 初始化豆包大模型客户端
        client = OpenAI(
            api_key=llm_api_key,
            base_url=llm_base_url
        )
        
        # 5. 设计 RAG 核心灵魂：System Prompt
        system_prompt = (
            "你是一位非常专业、亲切、有温度的公司企业 HR 助手。\n"
            "请结合以下由公司官方提供的【内部规章制度参考材料】，来回答员工的问题。\n\n"
            "【核心行为准则】：\n"
            "1. 必须优先基于给定的【参考材料】进行回答。回答要清晰、准确、条理分明。\n"
            "2. 语气一定要温柔、有耐心、礼貌，多使用‘您’、‘祝您’等称呼，符合一个好 HR 的职场形象。\n"
            "3. 如果材料中有具体天数、福利或报销标准（例如：陪产假15个自然日，全额带薪），请极其明确地告知员工，不要说‘大概’或‘可能’。\n"
            "4. 如果参考材料里【完全没有】提到员工问的事情（比如员工问你写代码或者娱乐八卦），请委婉且礼貌地回应：\n"
            "   ‘您好，目前的制度库中暂未查到相关细节说明。为了不误导您，建议您直接联系 HR 团队或查看内部最新公告哦。’，绝对不要自己瞎编乱造。\n\n"
            f"【内部规章制度参考材料】：\n{raw_context}"
        )
        
        # 6. 请求大模型
        completion = client.chat.completions.create(
            model=volc_ark_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.3,  # 低随机性，确保严格靠谱
        )
        
        llm_answer = completion.choices[0].message.content.strip()
        print("\n✨ [豆包大模型润色回答]：")
        print(llm_answer)
        return llm_answer

    except Exception as e:
        # 高可用兜底：如果大模型欠费了、网络崩了或者接入点错了，直接把刚才测试成功的“原始纯干货”扔给前端，保证用户绝对不会看到报错！
        print(f"\n⚠️ [大模型润色异常]: {str(e)} -> 触发高可用兜底，直接返回原始知识库。")
        return raw_context


if __name__ == "__main__":
    """
    主测试入口
    """
    query = input("请输入你想测试的员工问题：").strip()
    if not query:
        query = "陪产假有多少天？"
    
    knowledge_service_chat(query)