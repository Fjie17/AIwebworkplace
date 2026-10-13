from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TrendingRepo:
    """One row in the daily GitHub trending board."""

    date: str  # YYYY-MM-DD
    rank: int
    full_name: str  # owner/repo
    url: str
    stars: int
    github_desc: str = ""
    readme_excerpt: str = ""
    summary_zh: str = ""
    fetched_at: Optional[str] = None  # ISO datetime, set by DB on insert if omitted
    id: Optional[int] = None
