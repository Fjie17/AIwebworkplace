"""Stdlib-only web workbench (no third-party packages required).

Usage:
    python -m app.web
Then open http://127.0.0.1:8000
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from app.config import HOST, PORT
from app.db import init_db, latest_date, list_by_date, list_dates
from app.models import TrendingRepo

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "index.html"


def _repo_dict(r: TrendingRepo) -> dict[str, Any]:
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


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_page(board_date: Optional[str]) -> str:
    dates = list_dates()
    day = board_date or (dates[0] if dates else None)
    items = list_by_date(day) if day else []

    if not dates:
        options = '<option value="">暂无数据</option>'
    else:
        parts = []
        for d in dates:
            sel = " selected" if d == day else ""
            parts.append(f'<option value="{_escape(d)}"{sel}>{_escape(d)}</option>')
        options = "".join(parts)

    if not items:
        body = (
            '<div class="empty">暂无榜单数据。请先运行：'
            "<code>python -m jobs.fetch_trending</code> 再运行 "
            "<code>python -m jobs.summarize</code></div>"
        )
        meta = ""
    else:
        cards = []
        for r in items:
            summary = (
                f'<p class="summary">{_escape(r.summary_zh)}</p>'
                if r.summary_zh
                else '<p class="desc">（尚无中文摘要，可运行 python -m jobs.summarize）</p>'
            )
            desc = f'<p class="desc">{_escape(r.github_desc)}</p>' if r.github_desc else ""
            readme = ""
            if r.readme_excerpt:
                readme = (
                    "<details><summary>查看 README 摘录</summary>"
                    f"<pre>{_escape(r.readme_excerpt)}</pre></details>"
                )
            cards.append(
                "<article>"
                f'<div class="row"><span class="rank">#{r.rank:02d}</span>'
                f'<span class="name"><a href="{_escape(r.url)}" target="_blank" rel="noopener">'
                f"{_escape(r.full_name)}</a></span>"
                f'<span class="stars">stars {r.stars}</span></div>'
                f"{desc}{summary}{readme}"
                "</article>"
            )
        body = '<div class="list">' + "".join(cards) + "</div>"
        meta = (
            f'<span class="meta">共 {len(items)} 条 · API: '
            f'<a href="/api/trending?date={_escape(day or "")}">/api/trending</a></span>'
        )

    html = TEMPLATE.read_text(encoding="utf-8")
    return (
        html.replace("__DATE_OPTIONS__", options)
        .replace("__META__", meta)
        .replace("__BODY__", body)
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, data, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        date = (qs.get("date") or [None])[0]

        if path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return
        if path == "/api/dates":
            dates = list_dates()
            self._send_json(200, {"dates": dates, "latest": dates[0] if dates else None})
            return
        if path in ("/api/trending", "/api/trending/latest"):
            board_date = None if path.endswith("/latest") else date
            board_date = board_date or latest_date()
            if not board_date:
                self._send_json(200, {"date": None, "items": []})
                return
            items = list_by_date(board_date)
            if date and path == "/api/trending" and not items:
                self._send_json(404, {"detail": f"No data for date={date}"})
                return
            self._send_json(200, {"date": board_date, "items": [_repo_dict(r) for r in items]})
            return
        if path in ("/", "/index.html"):
            page = _render_page(date)
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return

        self._send_json(404, {"detail": "Not Found"})


def main() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Workbench running at http://127.0.0.1:{PORT}  (bind {HOST}:{PORT})", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
