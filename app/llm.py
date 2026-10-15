from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

SYSTEM_PROMPT = """你是技术编辑。根据 GitHub 仓库的短描述和 README 片段，用中文写简介。
要求：
1. 只依据给定材料，不编造未出现的功能或数据
2. 输出 3～5 句中文，总长约 150～350 字
3. 说明项目是做什么的、适合谁、核心特点
4. 不要输出标题、列表符号或 JSON，只输出正文段落
"""


def _chat_url() -> str:
    base = LLM_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def summarize_repo(full_name: str, github_desc: str, readme_excerpt: str) -> str:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY 未配置。请在项目根目录 .env 中填写（可参考 .env.example）。"
        )

    user_content = (
        f"仓库：{full_name}\n"
        f"GitHub 描述：{github_desc or '（无）'}\n\n"
        f"README 片段：\n{readme_excerpt or '（无 README）'}\n"
    )

    body: dict[str, Any] = {
        "model": LLM_MODEL,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }
    data = json.dumps(body).encode("utf-8")
    req = Request(
        _chat_url(),
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
            "User-Agent": "github-trending-workbench/0.1",
        },
    )
    try:
        with urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"LLM HTTP {e.code}: {detail[:300]}") from e
    except URLError as e:
        raise RuntimeError(f"LLM network error: {e}") from e

    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"LLM response unexpected: {payload!r}"[:400]) from e

    return (text or "").strip()
