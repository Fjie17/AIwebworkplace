"""Fetch GitHub Trending Top N and save into SQLite.

Usage (from project root):
    python -m jobs.fetch_trending
    python -m jobs.fetch_trending --date 2026-10-15
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python jobs/fetch_trending.py` as well as `python -m jobs.fetch_trending`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import TRENDING_LANGUAGE, TRENDING_SINCE, TRENDING_TOP_N
from app.db import init_db, list_by_date, save_day_board
from app.trending import fetch_trending_top10


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch GitHub trending Top N into SQLite")
    parser.add_argument("--date", help="Board date YYYY-MM-DD (default: today)")
    parser.add_argument("--since", default=TRENDING_SINCE, choices=["daily", "weekly", "monthly"])
    parser.add_argument("--language", default=TRENDING_LANGUAGE, help="e.g. python; empty = all")
    parser.add_argument("--top", type=int, default=TRENDING_TOP_N, help="How many repos (default 10)")
    args = parser.parse_args()

    init_db()
    repos, source = fetch_trending_top10(
        since=args.since,
        language=args.language,
        top_n=args.top,
        board_date=args.date,
    )
    n = save_day_board(repos)
    board_date = repos[0].date

    print(f"source={source} date={board_date} saved={n}")
    for r in list_by_date(board_date):
        desc = (r.github_desc[:60] + "…") if len(r.github_desc) > 60 else r.github_desc
        print(f"  #{r.rank:02d} {r.full_name} stars={r.stars}  {desc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
