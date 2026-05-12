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

from gmind import add, config, db, embed, enrich, utils
from gmind.llm import engine as llm_engine, reason as llm_reason


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


async def search_endpoint(request: Request) -> JSONResponse:
    """GET /search?q=...&k=5 — vector search returning JSON."""
    query_text = request.query_params.get("q", "")
    top_k = int(request.query_params.get("k", "5"))
    if not query_text:
        return JSONResponse({"results": []})

    try:
        cfg = config.load_config()
        vectors = embed.embed_texts([query_text], cfg)
        vector = vectors[0]

        with db.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT slug, title, content,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM pages
                WHERE (
                    status IN ('published', 'merge_review')
                    OR (status = 'draft' AND origin_node = %s)
                )
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector, cfg.node_name, vector, top_k),
            ).fetchall()

        results = [
            {
                "slug": slug,
                "title": title,
                "similarity": round(float(similarity), 4),
                "preview": (content[:200] + "...") if len(content) > 200 else content,
            }
            for slug, title, content, similarity in rows
        ]
        return JSONResponse({"results": results})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def ask_endpoint(request: Request) -> JSONResponse:
    """POST /ask — LLM-enhanced Q&A over the knowledge base."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"status": "error", "message": "Invalid JSON"}, status_code=400
        )

    question = data.get("question", "")
    top_k = data.get("top_k", 8)
    if not question:
        return JSONResponse(
            {"status": "error", "message": "question is required"}, status_code=400
        )

    cfg = config.load_config()
    llm_cfg = cfg.llm
    if not llm_cfg or not llm_cfg.get("provider"):
        return JSONResponse(
            {"status": "error", "message": "LLM not configured. Add [llm] section to ~/.gmind/config.toml"},
            status_code=503,
        )

    engine = llm_engine.load_llm_engine(llm_cfg)
    if engine is None or not engine.is_available():
        return JSONResponse(
            {"status": "error", "message": "LLM provider not available"},
            status_code=503,
        )

    try:
        result = await run_in_threadpool(
            llm_reason.reasoned_query,
            question,
            engine,
            cfg,
            top_k=top_k,
        )
        return JSONResponse({
            "status": "ok",
            "answer": result["answer"],
            "sources": result["sources"],
        })
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def enrich_endpoint(request: Request) -> JSONResponse:
    """POST /enrich — enrich a page with LLM-extracted metadata."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"status": "error", "message": "Invalid JSON"}, status_code=400
        )

    slug = data.get("slug", "")
    if not slug:
        return JSONResponse(
            {"status": "error", "message": "slug is required"}, status_code=400
        )

    cfg = config.load_config()
    llm_cfg = cfg.llm
    if not llm_cfg or not llm_cfg.get("provider"):
        return JSONResponse(
            {"status": "error", "message": "LLM not configured"},
            status_code=503,
        )

    engine = llm_engine.load_llm_engine(llm_cfg)
    if engine is None or not engine.is_available():
        return JSONResponse(
            {"status": "error", "message": "LLM provider not available"},
            status_code=503,
        )

    try:
        result = await run_in_threadpool(
            enrich.enrich_page,
            slug,
            engine=engine,
            cfg=cfg,
        )
        return JSONResponse({
            "status": "ok",
            "slug": result["slug"],
            "entities_count": len(result["entities"]),
            "relations_count": len(result["relations"]),
            "tags": result["tags"],
        })
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


routes = [
    Route("/add", add_endpoint, methods=["POST"]),
    Route("/check", check_endpoint, methods=["GET"]),
    Route("/search", search_endpoint, methods=["GET"]),
    Route("/ask", ask_endpoint, methods=["POST"]),
    Route("/enrich", enrich_endpoint, methods=["POST"]),
]

app = Starlette(debug=False, routes=routes, lifespan=lifespan)

# Allow Chrome extension (or any origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
