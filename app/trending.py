from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import GITHUB_TOKEN, TRENDING_LANGUAGE, TRENDING_SINCE, TRENDING_TOP_N
from app.models import TrendingRepo

# findmio/github-trending-api — JSON archived by GitHub Actions (stable for low-spec servers)
FINDMIO_BASE = "https://raw.githubusercontent.com/findmio/github-trending-api/main/raw"

USER_AGENT = "github-trending-workbench/0.1 (+local; educational)"


def _http_get_json(url: str, headers: Optional[dict] = None, timeout: int = 30) -> Any:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = Request(url, headers=req_headers)
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_stars(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    # e.g. "12.3k"
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([kKmM])?", text)
    if not m:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0
    num = float(m.group(1))
    suffix = (m.group(2) or "").lower()
    if suffix == "k":
        num *= 1_000
    elif suffix == "m":
        num *= 1_000_000
    return int(num)


def _findmio_url(since: str, language: str) -> str:
    since_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    period = since_map.get(since, "day")
    if language:
        # e.g. Python.day.json — capitalize first letter as findmio uses
        lang = language[0].upper() + language[1:] if language else ""
        return f"{FINDMIO_BASE}/{lang}.{period}.json"
    return f"{FINDMIO_BASE}/{period}.json"


def fetch_from_findmio(
    since: str = TRENDING_SINCE,
    language: str = TRENDING_LANGUAGE,
    top_n: int = TRENDING_TOP_N,
    board_date: Optional[str] = None,
) -> List[TrendingRepo]:
    url = _findmio_url(since, language)
    data = _http_get_json(url)
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"findmio returned empty/invalid list from {url}")

    day = board_date or date.today().isoformat()
    repos: List[TrendingRepo] = []
    for i, item in enumerate(data[:top_n], start=1):
        author = (item.get("author") or "").strip()
        name = (item.get("name") or "").strip()
        if not author or not name:
            continue
        full_name = f"{author}/{name}"
        repo_url = (item.get("url") or f"https://github.com/{full_name}").strip()
        repos.append(
            TrendingRepo(
                date=day,
                rank=i,
                full_name=full_name,
                url=repo_url,
                stars=_parse_stars(item.get("stars")),
                github_desc=(item.get("description") or "").strip(),
            )
        )
    if not repos:
        raise RuntimeError("findmio payload had no usable repositories")
    return repos


def fetch_from_github_search(
    top_n: int = TRENDING_TOP_N,
    board_date: Optional[str] = None,
) -> List[TrendingRepo]:
    """Approximate board via Search API (created in last 7 days, sort by stars)."""
    day = board_date or date.today().isoformat()
    # rolling ~7 days
    from datetime import timedelta

    since = (date.today() - timedelta(days=7)).isoformat()
    q = f"created:>{since}"
    if TRENDING_LANGUAGE:
        q += f" language:{TRENDING_LANGUAGE}"
    params = urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": str(top_n)})
    url = f"https://api.github.com/search/repositories?{params}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    data = _http_get_json(url, headers=headers)
    items = data.get("items") or []
    if not items:
        raise RuntimeError("GitHub Search API returned no items")

    repos: List[TrendingRepo] = []
    for i, item in enumerate(items[:top_n], start=1):
        full_name = item.get("full_name") or ""
        if not full_name:
            continue
        repos.append(
            TrendingRepo(
                date=day,
                rank=i,
                full_name=full_name,
                url=item.get("html_url") or f"https://github.com/{full_name}",
                stars=int(item.get("stargazers_count") or 0),
                github_desc=(item.get("description") or "").strip(),
            )
        )
    if not repos:
        raise RuntimeError("GitHub Search payload had no usable repositories")
    return repos


def fetch_trending_top10(
    since: str = TRENDING_SINCE,
    language: str = TRENDING_LANGUAGE,
    top_n: int = TRENDING_TOP_N,
    board_date: Optional[str] = None,
) -> tuple[List[TrendingRepo], str]:
    """
    Fetch Top N trending repos.
    Returns (repos, source_name).
    Primary: findmio JSON; fallback: GitHub Search API.
    """
    try:
        return (
            fetch_from_findmio(since=since, language=language, top_n=top_n, board_date=board_date),
            "findmio",
        )
    except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as primary_err:
        try:
            return (
                fetch_from_github_search(top_n=top_n, board_date=board_date),
                "github_search",
            )
        except Exception as fallback_err:
            raise RuntimeError(
                f"All trending sources failed. findmio={primary_err!r}; search={fallback_err!r}"
            ) from fallback_err
