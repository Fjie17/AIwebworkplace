"""Web entrypoint.

Primary (no extra deps):
    python -m app.web

Optional FastAPI (if installed):
    python -m app.main
"""

from __future__ import annotations


def main() -> None:
    try:
        import fastapi  # noqa: F401
        import uvicorn
    except ImportError:
        print("FastAPI not installed — starting stdlib server (python -m app.web)...")
        from app.web import main as web_main

        web_main()
        return

    from app.config import HOST, PORT

    uvicorn.run("app.fastapi_app:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
