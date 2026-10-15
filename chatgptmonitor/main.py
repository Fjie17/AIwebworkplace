"""ChatGPT latency / connectivity monitor — background service + web UI."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from probe import DEFAULT_INTERVAL_SEC, MonitorService

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

monitor = MonitorService(interval_sec=DEFAULT_INTERVAL_SEC)
_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _task
    # First probe immediately so UI is not empty
    await monitor.run_once()
    _task = asyncio.create_task(monitor.loop())
    yield
    monitor.stop()
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="ChatGPT Monitor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
async def status():
    if monitor.latest is None:
        return {"overall": "down", "message": "尚无探测数据"}
    return monitor.latest.to_dict()


@app.get("/api/history")
async def history():
    return {
        "samples": [s.to_dict() for s in monitor.history],
        "stats": monitor.latest.stats if monitor.latest else {},
    }


@app.post("/api/probe")
async def probe_now():
    snap = await monitor.run_once()
    return snap.to_dict()


@app.get("/api/stream")
async def stream():
    async def event_gen():
        last_ts = None
        while True:
            snap = monitor.latest
            if snap and snap.checked_at != last_ts:
                last_ts = snap.checked_at
                payload = json.dumps(snap.to_dict(), ensure_ascii=False)
                yield f"data: {payload}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> None:
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
