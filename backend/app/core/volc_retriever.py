import json
import re
import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from volcengine.base.Request import Request

from app.core.volc_config import VOLC_KB_DOMAIN, VOLC_KB_API_KEY, KB_POOL


def _build_request(method: str, path: str, params: dict | None = None, data: dict | None = None) -> Request:
    if params:
        for key in params:
            if isinstance(params[key], (int, float, bool)):
                params[key] = str(params[key])
            elif isinstance(params[key], list):
                params[key] = ",".join(params[key])

    r = Request()
    r.set_shema("https")
    r.set_method(method)
    r.set_connection_timeout(10)
    r.set_socket_timeout(10)
    r.set_headers({
        "Accept": "application/json",
        "Content-Type": "application/json;charset=UTF-8",
        "Host": VOLC_KB_DOMAIN,
        "Authorization": f"Bearer {VOLC_KB_API_KEY}",
    })
    if params:
        r.set_query(params)
    r.set_host(VOLC_KB_DOMAIN)
    r.set_path(path)
    if data is not None:
        r.set_body(json.dumps(data))
    return r


def _clean_tags(text: str) -> str:
    text = re.sub(r'<reference\s+data-ref="[^"]+">.*?</reference>', '', text, flags=re.DOTALL)
    text = re.sub(r'<illustration.*?>.*?</illustration>', '', text, flags=re.DOTALL)
    return text


def retrieve_single(query: str, kb_id: str) -> str:
    req = _build_request(
        method="POST",
        path="/api/knowledge/service/chat",
        data={
            "service_resource_id": kb_id,
            "messages": [
                {"role": "system", "content": "你是一个严谨的文档检索助手，只负责完整提取相关的原文条文。"},
                {"role": "user", "content": f"请提取出与用户问题相关的、完整的文档内容。用户问题：{query}"},
            ],
            "stream": False,
        },
    )
    try:
        rsp = requests.request(
            method=req.method,
            url=f"https://{req.host}{req.path}",
            headers=req.headers,
            data=req.body,
            timeout=(30, 360),
        )
        rsp.encoding = "utf-8"

        # 检查 HTTP 状态码
        if rsp.status_code != 200:
            print(f"[Error] 知识库 API 返回 {rsp.status_code}: {rsp.text}")
            return ""

        result = rsp.json()

        if "data" in result and "generated_answer" in result["data"]:
            return _clean_tags(result["data"]["generated_answer"]).strip()

        if "data" in result and "result" in result["data"]:
            chunks = [_clean_tags(c.get("content", "")) for c in result["data"]["result"]]
            return "\n".join(c for c in chunks if c)
    except Exception as e:
        print(f"[Warning] 知识库检索异常: {e}")
    return ""


def retrieve_multi(query: str, kb_ids: list[str]) -> tuple[str, bool]:
    if len(kb_ids) == 1:
        return retrieve_single(query, kb_ids[0]), False

    results: dict[str, str] = {}
    timed_out = False
    SEARCH_TIMEOUT = 60

    with ThreadPoolExecutor(max_workers=len(kb_ids)) as pool:
        futures = {pool.submit(retrieve_single, query, kid): kid for kid in kb_ids}
        done, not_done = concurrent.futures.wait(
            futures, timeout=SEARCH_TIMEOUT, return_when=concurrent.futures.ALL_COMPLETED
        )
        if not_done:
            timed_out = True
            print(f"[搜索超时] {len(not_done)}/{len(futures)} 个库超过 {SEARCH_TIMEOUT}s")
            for f in not_done:
                f.cancel()
        for f in done:
            try:
                results[futures[f]] = f.result()
            except Exception as e:
                print(f"[KB检索失败] {futures[f]}: {e}")

    parts = []
    for kid in kb_ids:
        if kid in results and results[kid]:
            label = "管理库" if kid == KB_POOL.get("manage") else "默认库"
            parts.append(f"【{label}】\n{results[kid]}")
    return ("\n\n---\n\n".join(parts) if parts else ""), timed_out


def check_broad_query(query: str) -> str | None:
    stripped = query.strip().rstrip("?？。. ")
    if len(stripped) <= 3:
        return (
            f"您好，您的问题「{query}」比较简短，可能涉及面很广。\n\n"
            "为了给您更精准、更有价值的回答，能否补充一下：\n"
            "• 您具体想了解哪条政策或制度？\n"
            "• 是和哪个业务场景、部门或岗位相关？\n"
            "• 有没有特定的时间范围或关键词？\n\n"
            "请提供更多细节，我会为您详细解答。"
        )
    return None
