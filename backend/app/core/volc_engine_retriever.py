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
import concurrent.futures
import time
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from volcengine.base.Request import Request
from openai import OpenAI

load_dotenv()

g_knowledge_base_domain = "api-knowledgebase.mlp.cn-beijing.volces.com"

apikey = os.getenv("VOLC_KNOWLEDGE_API_KEY")

KB_POOL = {
    "default": os.getenv("VOLC_KNOWLEDGE_SERVICE_ID", ""),
    "manage":  os.getenv("VOLC_KNOWLEDGE_SERVICE_ID_2", ""),
}

volc_ark_api_key = os.getenv("VOLC_ARK_API_KEY")
volc_ark_base_url = os.getenv("VOLC_ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
volc_ark_model = os.getenv("VOLC_ARK_MODEL")

if not apikey:
    raise ValueError("未设置 VOLC_KNOWLEDGE_API_KEY")
if not KB_POOL["default"]:
    raise ValueError("未设置 VOLC_KNOWLEDGE_SERVICE_ID")

print(f"[DEBUG] KB池: default={KB_POOL['default'][:20]}... | manage={'OK' if KB_POOL['manage'] else '未配置'}")


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


def _get_raw_knowledge_context(query: str, kb_id: str) -> str:
    method = "POST"
    path = "/api/knowledge/service/chat"

    prompt = f"请提取出与用户问题相关的、完整的文档内容。用户问题：{query}"

    request_params = {
        "service_resource_id": kb_id,
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
        
        if "data" in result and "result" in result["data"]:
            chunks = []
            for chunk in result["data"]["result"]:
                content = chunk.get('content', '')
                content = re.sub(r'<reference\s+data-ref="[^"]+">.*?</reference>', '', content, flags=re.DOTALL)
                content = re.sub(r'<illustration.*?>.*?</illustration>', '', content, flags=re.DOTALL)
                if content:
                    chunks.append(content)
            if chunks:
                return "\n".join(chunks)

        if "data" in result and "generated_answer" in result["data"]:
            answer = result["data"]["generated_answer"]
            answer = re.sub(r'<reference\s+data-ref="[^"]+">.*?</reference>', '', answer, flags=re.DOTALL)
            answer = re.sub(r'<illustration.*?>.*?</illustration>', '', answer, flags=re.DOTALL)
            answer = answer.strip()
            low_confidence_phrases = ["抱歉", "无法回答", "未查到", "暂无", "请您提供更加详细的信息"]
            if any(phrase in answer for phrase in low_confidence_phrases):
                return ""
            return answer
    except Exception as e:
        print(f"[Warning] 知识库原生检索阶段发生异常: {str(e)}")
        
    return ""

def _get_multi_kb_context(query: str, kb_ids: list[str]) -> tuple[str, bool]:
    """并发检索多个知识库，合并结果。返回 (内容, 是否超时)"""
    if len(kb_ids) == 1:
        return _get_raw_knowledge_context(query, kb_ids[0]), False

    results: dict[str, str] = {}
    SEARCH_TIMEOUT = 60  # 总搜索超时 1 分钟    
    timed_out = False
    
    with ThreadPoolExecutor(max_workers=len(kb_ids)) as pool:
        futures = {pool.submit(_get_raw_knowledge_context, query, kid): kid for kid in kb_ids}
        done, not_done = concurrent.futures.wait(
            futures, timeout=SEARCH_TIMEOUT,
            return_when=concurrent.futures.ALL_COMPLETED
        )
        
        if not_done:
            timed_out = True
            print(f"[搜索超时] {len(not_done)}/{len(futures)} 个库超过 {SEARCH_TIMEOUT}s 未完成，返回已检索结果")
            for f in not_done:
                f.cancel()
        
        for f in done:
            kid = futures[f]
            try:
                results[kid] = f.result()
            except Exception as e:
                print(f"[KB检索失败] {kid}: {e}")

    parts = []
    for kid in kb_ids:
        if kid in results and results[kid]:
            label = "管理库" if kid == KB_POOL.get("manage") else "默认库"
            parts.append(f"【{label}】\n{results[kid]}")
    return ("\n\n---\n\n".join(parts) if parts else ""), timed_out


def _web_search_content(query: str, max_results: int = 5) -> tuple[str, list[str]]:
    """
    联网搜索（DuckDuckGo），返回 (拼接后的文本, 来源URL列表)
    """
    try:
        from ddgs import DDGS
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "", []

        sources = []
        chunks = []
        for i, r in enumerate(results, 1):
            href = r.get("href", "")
            title = r.get("title", "")
            body = r.get("body", "")
            if body:
                sources.append(href)
                chunks.append(f"[{i}] {title}\n{body}\n来源: {href}")

        return "\n\n".join(chunks), sources
    except Exception as e:
        print(f"[联网搜索异常]: {e}")
        return "", []



def knowledge_service_chat_stream(query: str, deep_think: bool = False, kb_ids: list[str] | None = None):
    """
    RAG 流式打字机输出

    deep_think=False: 只做检索直接返回原文（快）
    deep_think=True:  检索 + 豆包 LLM 润色（慢但更专业）
    kb_ids:            要检索的知识库 ID 列表，默认只查 default

    特殊元数据块 (dict): {"web_search": True, "sources": [...]}
    """
    if kb_ids is None:
        kb_ids = [KB_POOL["default"]]

    kb_ids = [k for k in kb_ids if k]  # 过滤空值
    print(f"[检索] 查询 {len(kb_ids)} 个库: {[k[:25]+'...' for k in kb_ids]}")

    raw_context, timed_out = _get_multi_kb_context(query, kb_ids)
    web_search_used = False
    web_sources: list[str] = []

    # 搜索超时时，追加引导提示让用户细化
    if timed_out and raw_context:
        raw_context += (
            "\n\n⚠️ 搜索时间较长，以上为已检索到的部分内容。"
            "\n💡 建议您缩小问题范围或补充更具体的关键词，以获得更完整的答案。"
        )

    # ── 知识库没查到 / 低置信度答复 → 联网搜索兜底 ──
    low_confidence_phrases = ["未获取到有效回答", "抱歉", "无法回答", "未查到", "暂无相关内容"]
    if (not raw_context) or any(phrase in raw_context for phrase in low_confidence_phrases):
        print(f"[联网兜底] 知识库未命中，尝试联网搜索: {query[:40]}...")
        web_context, web_sources = _web_search_content(query)
        if web_context:
            web_search_used = True
            raw_context = (
                "⚠️ 知识库中暂未查到相关内容，以下为互联网搜索结果，仅供参考，非官方审核内容：\n\n"
                + web_context
            )
        else:
            raw_context = "（暂无相关内容参考，联网搜索也未找到）"

    if not deep_think:
        print("[深度思考关闭] 跳过 LLM 加工，直接返回原文")
        for char in raw_context:
            yield char
        if web_search_used:
            yield {"web_search": True, "sources": web_sources}
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

        # 联网搜索结果标记
        if web_search_used:
            yield {"web_search": True, "sources": web_sources}

    except Exception as e:
        print(f"\n⚠️ [大模型流式润色异常]: {str(e)} -> 触发流式兜底。")
        for char in raw_context:
            yield char
        if web_search_used:
            yield {"web_search": True, "sources": web_sources}


if __name__ == "__main__":
    query = "12月份淘宝营业额度是多少？"
    for text in knowledge_service_chat_stream(query):
        print(text, end="", flush=True)