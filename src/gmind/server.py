"""HTTP server for GMind browser integrations."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from gmind import add, config, db, utils


@asynccontextmanager
async def lifespan(app: Starlette):
    """Initialize database pool on startup."""
    cfg = config.load_config()
    db.init_pool(cfg.database_url)
    yield
    db.close_pool()


async def add_endpoint(request: Request) -> JSONResponse:
    """POST /add — save a page to the knowledge base."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"status": "error", "message": "Invalid JSON"}, status_code=400
        )

    title = data.get("title", "")
    content = data.get("content", "")
    page_type = data.get("type", "source")
    source = data.get("source", "")
    slug = data.get("slug")

    if not content:
        return JSONResponse(
            {"status": "error", "message": "content is required"}, status_code=400
        )

    page_slug = slug or utils.slugify(title or content[:50])

    try:
        await run_in_threadpool(
            add.add_page,
            content,
            page_type=page_type,
            title=title or None,
            slug=page_slug,
            source=source or None,
            on_duplicate="append",
        )
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )

    return JSONResponse({"status": "ok", "slug": page_slug})


async def check_endpoint(request: Request) -> JSONResponse:
    """GET /check?source=... — check whether a source URL already exists."""
    source = request.query_params.get("source", "")
    if not source:
        return JSONResponse({"exists": False})

    try:
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT slug, title FROM pages WHERE %s = ANY(sources) LIMIT 1",
                (source,),
            ).fetchone()
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )

    if row:
        return JSONResponse({"exists": True, "slug": row[0], "title": row[1]})
    return JSONResponse({"exists": False})


routes = [
    Route("/add", add_endpoint, methods=["POST"]),
    Route("/check", check_endpoint, methods=["GET"]),
]

app = Starlette(debug=False, routes=routes, lifespan=lifespan)

# Allow Chrome extension (or any origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
