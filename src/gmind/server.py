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

from gmind import add, config, db, embed, enrich, ingest, utils
from gmind.llm import engine as llm_engine, reason as llm_reason
from gmind.taotie import Blacklist, IngestHistory, IngestQueue, IngestTask, WatcherConfig, scan_computer
from gmind.taotie.classifier import classify_file
from gmind.taotie.scanner import FileInfo


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


async def recent_endpoint(request: Request) -> JSONResponse:
    """GET /recent?limit=5 — recently updated pages."""
    try:
        limit = int(request.query_params.get("limit", "5"))
        cfg = config.load_config()
        with db.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT slug, title
                FROM pages
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return JSONResponse({
            "results": [{"slug": slug, "title": title} for slug, title in rows]
        })
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def stats_endpoint(request: Request) -> JSONResponse:
    """GET /stats — knowledge base statistics."""
    try:
        with db.get_conn() as conn:
            page_count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            enriched_count = conn.execute(
                "SELECT COUNT(*) FROM pages WHERE llm_enriched = TRUE"
            ).fetchone()[0]
        return JSONResponse({
            "pages": page_count,
            "edges": edge_count,
            "llm_enriched": enriched_count,
        })
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


# ─── Taotie endpoints ─────────────────────────────────────────────

async def taotie_scan_endpoint(request: Request) -> JSONResponse:
    """GET /taotie/scan — scan the computer for knowledge files."""
    try:
        files, folders = scan_computer()
        # Quick heuristic classification (no LLM in scan endpoint for speed)
        from gmind.taotie.classifier import _heuristic_classify
        classified = []
        for f in files:
            cf = _heuristic_classify(f)
            classified.append({
                "path": cf.path,
                "size": cf.size,
                "ext": cf.ext,
                "should_ingest": cf.should_ingest,
                "reason": cf.reason,
                "privacy_level": cf.privacy_level,
                "contains_passwords": cf.contains_passwords,
                "contains_pii": cf.contains_pii,
                "is_knowledge": cf.is_knowledge,
            })

        return JSONResponse({
            "status": "ok",
            "files": classified,
            "folders": [
                {
                    "path": f.path,
                    "file_count": f.file_count,
                    "knowledge_file_count": f.knowledge_file_count,
                    "total_size": f.total_size,
                    "is_agent_session": f.is_agent_session,
                    "is_wechat": f.is_wechat,
                    "checked": f.checked,
                }
                for f in folders
            ],
            "total_files": len(classified),
        })
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_queue_endpoint(request: Request) -> JSONResponse:
    """GET /taotie/queue — get current queue state."""
    try:
        q = IngestQueue()
        return JSONResponse({"status": "ok", **q.get_state()})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_queue_start_endpoint(request: Request) -> JSONResponse:
    """POST /taotie/queue/start — start processing the queue."""
    try:
        q = IngestQueue()
        q.start()
        return JSONResponse({"status": "ok", "message": "Queue started"})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_queue_pause_endpoint(request: Request) -> JSONResponse:
    """POST /taotie/queue/pause — pause the queue."""
    try:
        q = IngestQueue()
        q.pause()
        return JSONResponse({"status": "ok", "message": "Queue paused"})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_queue_clear_endpoint(request: Request) -> JSONResponse:
    """POST /taotie/queue/clear — clear all tasks."""
    try:
        q = IngestQueue()
        q.clear()
        return JSONResponse({"status": "ok", "message": "Queue cleared"})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_queue_select_endpoint(request: Request) -> JSONResponse:
    """POST /taotie/queue/select — set selection state for a task."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"status": "error", "message": "Invalid JSON"}, status_code=400
        )

    path = data.get("path", "")
    selected = data.get("selected", True)
    if not path:
        return JSONResponse(
            {"status": "error", "message": "path is required"}, status_code=400
        )

    try:
        q = IngestQueue()
        q.set_selected(path, selected)
        return JSONResponse({"status": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_queue_remove_endpoint(request: Request) -> JSONResponse:
    """POST /taotie/queue/remove — remove a task from queue."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"status": "error", "message": "Invalid JSON"}, status_code=400
        )

    path = data.get("path", "")
    if not path:
        return JSONResponse(
            {"status": "error", "message": "path is required"}, status_code=400
        )

    try:
        q = IngestQueue()
        q.remove_task(path)
        # Also add to blacklist so it won't be scanned again
        bl = Blacklist()
        bl.add_file(path)
        return JSONResponse({"status": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_queue_add_endpoint(request: Request) -> JSONResponse:
    """POST /taotie/queue/add — add files to the queue."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"status": "error", "message": "Invalid JSON"}, status_code=400
        )

    files = data.get("files", [])
    if not files:
        return JSONResponse(
            {"status": "error", "message": "files is required"}, status_code=400
        )

    try:
        q = IngestQueue()
        tasks = [IngestTask(path=f["path"], size=f.get("size", 0), ext=f.get("ext", "")) for f in files]
        q.add_tasks(tasks)
        return JSONResponse({"status": "ok", "added": len(tasks)})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_blacklist_endpoint(request: Request) -> JSONResponse:
    """GET /taotie/blacklist — get blacklist."""
    try:
        bl = Blacklist()
        return JSONResponse({"status": "ok", **bl.list_all()})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_history_endpoint(request: Request) -> JSONResponse:
    """GET /taotie/history?limit=20 — get import history."""
    try:
        limit = int(request.query_params.get("limit", "20"))
        h = IngestHistory()
        records = h.get_records(limit=limit)
        return JSONResponse({"status": "ok", "records": records})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_watcher_endpoint(request: Request) -> JSONResponse:
    """GET /taotie/watcher — get watched folders."""
    try:
        wc = WatcherConfig()
        return JSONResponse({"status": "ok", "folders": wc.list_all()})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_watcher_add_endpoint(request: Request) -> JSONResponse:
    """POST /taotie/watcher/add — add a watched folder."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"status": "error", "message": "Invalid JSON"}, status_code=400
        )

    path = data.get("path", "")
    if not path:
        return JSONResponse(
            {"status": "error", "message": "path is required"}, status_code=400
        )

    try:
        wc = WatcherConfig()
        wc.add(
            path,
            scan_mode=data.get("scan_mode", "interval"),
            interval_hours=data.get("interval_hours", 1),
            daily_time=data.get("daily_time", "02:00"),
            weekly_day=data.get("weekly_day", 0),
            weekly_time=data.get("weekly_time", "02:00"),
        )
        return JSONResponse({"status": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "message": str(exc)}, status_code=500
        )


async def taotie_watcher_remove_endpoint(request: Request) -> JSONResponse:
    """POST /taotie/watcher/remove — remove a watched folder."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            {"status": "error", "message": "Invalid JSON"}, status_code=400
        )

    path = data.get("path", "")
    if not path:
        return JSONResponse(
            {"status": "error", "message": "path is required"}, status_code=400
        )

    try:
        wc = WatcherConfig()
        wc.remove(path)
        return JSONResponse({"status": "ok"})
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
    Route("/recent", recent_endpoint, methods=["GET"]),
    Route("/stats", stats_endpoint, methods=["GET"]),
    # Taotie
    Route("/taotie/scan", taotie_scan_endpoint, methods=["GET"]),
    Route("/taotie/queue", taotie_queue_endpoint, methods=["GET"]),
    Route("/taotie/queue/start", taotie_queue_start_endpoint, methods=["POST"]),
    Route("/taotie/queue/pause", taotie_queue_pause_endpoint, methods=["POST"]),
    Route("/taotie/queue/clear", taotie_queue_clear_endpoint, methods=["POST"]),
    Route("/taotie/queue/select", taotie_queue_select_endpoint, methods=["POST"]),
    Route("/taotie/queue/remove", taotie_queue_remove_endpoint, methods=["POST"]),
    Route("/taotie/queue/add", taotie_queue_add_endpoint, methods=["POST"]),
    Route("/taotie/blacklist", taotie_blacklist_endpoint, methods=["GET"]),
    Route("/taotie/history", taotie_history_endpoint, methods=["GET"]),
    Route("/taotie/watcher", taotie_watcher_endpoint, methods=["GET"]),
    Route("/taotie/watcher/add", taotie_watcher_add_endpoint, methods=["POST"]),
    Route("/taotie/watcher/remove", taotie_watcher_remove_endpoint, methods=["POST"]),
]

app = Starlette(debug=False, routes=routes, lifespan=lifespan)

# Allow Chrome extension (or any origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
