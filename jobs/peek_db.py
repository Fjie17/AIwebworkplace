"""Print trending rows from SQLite (no Web needed).

Usage:
    python -m jobs.peek_db
    python -m jobs.peek_db --date 2026-10-15
    python -m jobs.peek_db --full
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import DEFAULT_DB_PATH, init_db, latest_date, list_by_date, list_dates


def main() -> int:
    parser = argparse.ArgumentParser(description="Peek SQLite trending data")
    parser.add_argument("--date", help="YYYY-MM-DD (default: latest)")
    parser.add_argument("--full", action="store_true", help="Print full summary/readme")
    args = parser.parse_args()

    init_db()
    print(f"db={DEFAULT_DB_PATH}")
    dates = list_dates()
    print(f"dates={dates or '(none)'}")

    board_date = args.date or latest_date()
    if not board_date:
        print("No data. Run: python -m jobs.fetch_trending")
        return 1

    rows = list_by_date(board_date)
    print(f"date={board_date} count={len(rows)}")
    for r in rows:
        print("-" * 60)
        print(f"#{r.rank:02d} {r.full_name}")
        print(f"url: {r.url}")
        print(f"stars: {r.stars}")
        print(f"desc: {r.github_desc}")
        summary = r.summary_zh or "(empty)"
        if not args.full and len(summary) > 120:
            summary = summary[:120] + "..."
        print(f"summary_zh: {summary}")
        if args.full:
            print(f"readme_excerpt:\n{r.readme_excerpt or '(empty)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
