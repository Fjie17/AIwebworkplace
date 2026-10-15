from __future__ import annotations

import base64
import json
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import GITHUB_TOKEN, README_MAX_CHARS

USER_AGENT = "github-trending-workbench/0.1 (+local; educational)"


def _headers() -> dict:
    h = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def fetch_readme(full_name: str, max_chars: int = README_MAX_CHARS) -> str:
    """
    Fetch README text for owner/repo. Returns truncated plain text, or "".
    """
    url = f"https://api.github.com/repos/{full_name}/readme"
    req = Request(url, headers=_headers())
    try:
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            return ""
        raise RuntimeError(f"GitHub README HTTP {e.code} for {full_name}") from e
    except URLError as e:
        raise RuntimeError(f"GitHub README network error for {full_name}: {e}") from e

    encoding = (payload.get("encoding") or "").lower()
    content = payload.get("content") or ""
    if encoding == "base64" and content:
        raw = base64.b64decode(content)
    else:
        # Fallback: try download_url
        download_url = payload.get("download_url")
        if not download_url:
            return ""
        req2 = Request(download_url, headers={"User-Agent": USER_AGENT})
        with urlopen(req2, timeout=30) as resp2:
            raw = resp2.read()

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")

    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n...[truncated]..."
    return text


def try_fetch_readme(full_name: str) -> tuple[str, Optional[str]]:
    """Returns (excerpt, error_message). error_message is None on success (even if empty)."""
    try:
        return fetch_readme(full_name), None
    except Exception as e:
        return "", str(e)
