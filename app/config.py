from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load .env into os.environ. Uses python-dotenv if present, else a tiny parser."""
    env_path = ROOT_DIR / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

TRENDING_SINCE = os.getenv("TRENDING_SINCE", "daily").strip() or "daily"
TRENDING_LANGUAGE = os.getenv("TRENDING_LANGUAGE", "").strip()
TRENDING_TOP_N = int(os.getenv("TRENDING_TOP_N", "10"))

# OpenAI-compatible LLM (DeepSeek / 通义 compatible mode / OpenAI ...)
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat").strip() or "deepseek-chat"

README_MAX_CHARS = int(os.getenv("README_MAX_CHARS", "12000"))

HOST = os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.getenv("PORT", "8000"))
