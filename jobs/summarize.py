"""Fetch README + LLM Chinese summary for a day's trending board.

Usage (from project root):
    python -m jobs.summarize
    python -m jobs.summarize --date 2026-10-15
    python -m jobs.summarize --force          # rewrite even if summary exists
    python -m jobs.summarize --limit 2       # only first N rows (smoke test)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.db import init_db, latest_date, list_by_date, update_readme_and_summary
from app.github_readme import try_fetch_readme
from app.llm import summarize_repo


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize trending repos with LLM")
    parser.add_argument("--date", help="Board date YYYY-MM-DD (default: latest in DB)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing summary_zh")
    parser.add_argument("--limit", type=int, default=0, help="Only process first N repos (0=all)")
    parser.add_argument("--sleep", type=float, default=0.5, help="Pause seconds between LLM calls")
    args = parser.parse_args()

    init_db()
    board_date = args.date or latest_date()
    if not board_date:
        print("No trending data in DB. Run: python -m jobs.fetch_trending")
        return 1

    if not LLM_API_KEY:
        print("Missing LLM_API_KEY.")
        print(f"Create/edit: {ROOT / '.env'}")
        print("Copy from .env.example and fill LLM_API_KEY (and optionally LLM_BASE_URL / LLM_MODEL).")
        return 1

    repos = list_by_date(board_date)
    if not repos:
        print(f"No rows for date={board_date}")
        return 1

    if args.limit and args.limit > 0:
        repos = repos[: args.limit]

    print(f"date={board_date} model={LLM_MODEL} base={LLM_BASE_URL} count={len(repos)}")

    ok = 0
    skipped = 0
    failed = 0

    for r in repos:
        if r.summary_zh and not args.force:
            print(f"  skip #{r.rank:02d} {r.full_name} (summary exists)")
            skipped += 1
            continue

        excerpt, err = try_fetch_readme(r.full_name)
        if err:
            print(f"  warn #{r.rank:02d} {r.full_name} README: {err}")

        try:
            summary = summarize_repo(r.full_name, r.github_desc, excerpt)
            if not summary:
                raise RuntimeError("empty summary from LLM")
            update_readme_and_summary(board_date, r.full_name, excerpt, summary)
            preview = summary.replace("\n", " ")
            if len(preview) > 80:
                preview = preview[:80] + "..."
            print(f"  ok   #{r.rank:02d} {r.full_name}  {preview}")
            ok += 1
        except Exception as e:
            print(f"  fail #{r.rank:02d} {r.full_name}  {e}")
            failed += 1

        if args.sleep > 0:
            time.sleep(args.sleep)

    print(f"done ok={ok} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
