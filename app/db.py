from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

from app.models import TrendingRepo

# Project root: .../workplace
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "workbench.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trending_repos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,          -- YYYY-MM-DD
    rank            INTEGER NOT NULL,          -- 1..10
    full_name       TEXT    NOT NULL,          -- owner/repo
    url             TEXT    NOT NULL,
    stars           INTEGER NOT NULL DEFAULT 0,
    github_desc     TEXT    NOT NULL DEFAULT '',
    readme_excerpt  TEXT    NOT NULL DEFAULT '',
    summary_zh      TEXT    NOT NULL DEFAULT '',
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (date, rank),
    UNIQUE (date, full_name)
);

CREATE INDEX IF NOT EXISTS idx_trending_repos_date
    ON trending_repos (date);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    """Create data dir + tables. Safe to call repeatedly."""
    path = Path(db_path)
    with get_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    return path


def upsert_trending(repos: Iterable[TrendingRepo], db_path: Path | str = DEFAULT_DB_PATH) -> int:
    """Insert or update rows by (date, full_name). Keeps existing README/summary if new empty."""
    rows = list(repos)
    if not rows:
        return 0

    sql = """
    INSERT INTO trending_repos (
        date, rank, full_name, url, stars,
        github_desc, readme_excerpt, summary_zh, fetched_at
    ) VALUES (
        ?, ?, ?, ?, ?,
        ?, ?, ?, COALESCE(?, datetime('now', 'localtime'))
    )
    ON CONFLICT (date, full_name) DO UPDATE SET
        rank           = excluded.rank,
        url            = excluded.url,
        stars          = excluded.stars,
        github_desc    = excluded.github_desc,
        readme_excerpt = CASE
            WHEN excluded.readme_excerpt != '' THEN excluded.readme_excerpt
            ELSE trending_repos.readme_excerpt
        END,
        summary_zh     = CASE
            WHEN excluded.summary_zh != '' THEN excluded.summary_zh
            ELSE trending_repos.summary_zh
        END,
        fetched_at     = excluded.fetched_at
    """
    with get_connection(db_path) as conn:
        conn.executemany(
            sql,
            [
                (
                    r.date,
                    r.rank,
                    r.full_name,
                    r.url,
                    r.stars,
                    r.github_desc,
                    r.readme_excerpt,
                    r.summary_zh,
                    r.fetched_at,
                )
                for r in rows
            ],
        )
        conn.commit()
    return len(rows)


def save_day_board(repos: Iterable[TrendingRepo], db_path: Path | str = DEFAULT_DB_PATH) -> int:
    """
    Replace one day's board with the given Top N list.
    Removes same-day repos that fell off the board; preserves README/summary on upsert.
    """
    rows = list(repos)
    if not rows:
        return 0

    board_date = rows[0].date
    names = [r.full_name for r in rows]

    with get_connection(db_path) as conn:
        # Park ranks on -id so UNIQUE(date, rank) cannot clash while reshuffling 1..N
        conn.execute(
            "UPDATE trending_repos SET rank = -id WHERE date = ?",
            (board_date,),
        )
        placeholders = ",".join("?" for _ in names)
        conn.execute(
            f"DELETE FROM trending_repos WHERE date = ? AND full_name NOT IN ({placeholders})",
            (board_date, *names),
        )
        conn.commit()

    return upsert_trending(rows, db_path=db_path)


def list_by_date(date: str, db_path: Path | str = DEFAULT_DB_PATH) -> List[TrendingRepo]:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT id, date, rank, full_name, url, stars,
                   github_desc, readme_excerpt, summary_zh, fetched_at
            FROM trending_repos
            WHERE date = ?
            ORDER BY rank ASC
            """,
            (date,),
        )
        return [_row_to_model(row) for row in cur.fetchall()]


def latest_date(db_path: Path | str = DEFAULT_DB_PATH) -> Optional[str]:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT MAX(date) AS d FROM trending_repos")
        row = cur.fetchone()
        return row["d"] if row and row["d"] else None


def list_dates(db_path: Path | str = DEFAULT_DB_PATH) -> List[str]:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT DISTINCT date FROM trending_repos ORDER BY date DESC"
        )
        return [row["date"] for row in cur.fetchall()]


def update_readme_and_summary(
    date: str,
    full_name: str,
    readme_excerpt: str,
    summary_zh: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE trending_repos
            SET readme_excerpt = ?,
                summary_zh = ?,
                fetched_at = datetime('now', 'localtime')
            WHERE date = ? AND full_name = ?
            """,
            (readme_excerpt, summary_zh, date, full_name),
        )
        conn.commit()


def _row_to_model(row: sqlite3.Row) -> TrendingRepo:
    return TrendingRepo(
        id=row["id"],
        date=row["date"],
        rank=row["rank"],
        full_name=row["full_name"],
        url=row["url"],
        stars=row["stars"],
        github_desc=row["github_desc"] or "",
        readme_excerpt=row["readme_excerpt"] or "",
        summary_zh=row["summary_zh"] or "",
        fetched_at=row["fetched_at"],
    )


if __name__ == "__main__":
    db = init_db()
    print(f"SQLite ready: {db}")
