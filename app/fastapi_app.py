"""Optional FastAPI app. Requires: pip install fastapi uvicorn jinja2"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.db import init_db, latest_date, list_by_date, list_dates
from app.models import TrendingRepo
from app.web import _render_page


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="GitHub 热门工作台", version="0.1.0", lifespan=lifespan)


def _repo_to_dict(r: TrendingRepo) -> dict[str, Any]:
    return {
        "id": r.id,
        "date": r.date,
        "rank": r.rank,
        "full_name": r.full_name,
        "url": r.url,
        "stars": r.stars,
        "github_desc": r.github_desc,
        "readme_excerpt": r.readme_excerpt,
        "summary_zh": r.summary_zh,
        "fetched_at": r.fetched_at,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dates")
def api_dates() -> dict[str, Any]:
    dates = list_dates()
    return {"dates": dates, "latest": dates[0] if dates else None}


@app.get("/api/trending")
def api_trending(date: Optional[str] = Query(None)) -> dict[str, Any]:
    board_date = date or latest_date()
    if not board_date:
        return {"date": None, "items": []}
    items = list_by_date(board_date)
    if date and not items:
        raise HTTPException(status_code=404, detail=f"No data for date={date}")
    return {"date": board_date, "items": [_repo_to_dict(r) for r in items]}


@app.get("/api/trending/latest")
def api_trending_latest() -> dict[str, Any]:
    return api_trending(date=None)


@app.get("/", response_class=HTMLResponse)
def index(date: Optional[str] = None) -> HTMLResponse:
    return HTMLResponse(_render_page(date))
