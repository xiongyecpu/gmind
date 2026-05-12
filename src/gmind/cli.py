"""CLI entry point for gmind."""

from __future__ import annotations

import typer

from gmind import (
    add,
    capture,
    config,
    db,
    enrich,
    export,
    graph,
    ingest,
    lint,
    mark,
    merge,
    pending,
    query,
    search,
    server,
    stats,
    sync,
)
from gmind.llm import engine as llm_engine, reason as llm_reason
from gmind.taotie import (
    Blacklist,
    IngestHistory,
    IngestQueue,
    IngestTask,
    WatcherConfig,
    scan_computer,
)
from gmind.taotie.classifier import classify_file

app = typer.Typer(help="GMind — Knowledge graph and vector search engine")

taotie_app = typer.Typer(help="饕餮盛宴 — 全电脑知识自动发现与入库")
app.add_typer(taotie_app, name="taotie")

ARG_CONTENT = typer.Argument(..., help="Note content")
ARG_QUESTION = typer.Argument(..., help="Question to ask")
ARG_KEYWORD = typer.Argument(..., help="Search keyword")
ARG_ASK = typer.Argument(..., help="Question to ask the knowledge base")


@app.command()
def init(
    node: str = typer.Option("default", "--node", "-n", help="Node name"),
) -> None:
    """Initialize gmind configuration and database."""
    typer.echo("🔧 GMind initialization")
    database_url = typer.prompt("PostgreSQL connection URL")
    embedding_api_key = typer.prompt("Embedding API key (SiliconFlow)", hide_input=True)
    embedding_model = typer.prompt("Embedding model", default="BAAI/bge-m3")

    cfg = config.Config(
        database_url=database_url,
        node_name=node,
        embedding_api_key=embedding_api_key,
        embedding_model=embedding_model,
    )
    config.save_config(cfg)
    typer.echo(f"✅ Config saved to {config.DEFAULT_CONFIG_PATH}")

    db.init_db(database_url)
    typer.echo("✅ Database initialized")


@app.command(name="add")
def add_cmd(
    content: list[str] = ARG_CONTENT,
    type_: str = typer.Option(
        "note", "--type", "-t",
        help="Type: note, source, capture, concept, project, "
             "person, company, product, synthesis, query, entity",
    ),
    title: str | None = typer.Option(None, "--title", help="Page title"),
    slug: str | None = typer.Option(None, "--slug", "-s", help="URL slug"),
    source: str | None = typer.Option(None, "--source", help="Source reference"),
    on_duplicate: str | None = typer.Option(
        None, "--on-duplicate", help="[a]ppend / [o]verwrite / [i]gnore"
    ),
    auto_extract: bool = typer.Option(
        False, "--auto-extract", "-x",
        help="Auto-extract entities, relations, and tags via LLM",
    ),
) -> None:
    """Add a note to the knowledge base."""
    text = " ".join(content)
    add.add_page(
        text, page_type=type_, title=title, slug=slug,
        source=source, on_duplicate=on_duplicate,
        auto_extract=auto_extract,
    )


@app.command(name="search")
def search_cmd(
    keyword: list[str] = ARG_KEYWORD,
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
    json_output: bool = typer.Option(False, "--json", help="JSON output for agents"),
) -> None:
    """Search the knowledge base via vector similarity (no LLM)."""
    text = " ".join(keyword)
    search.run_search(text, top_k=top_k, json_output=json_output)


@app.command(name="query")
def query_cmd(
    question: list[str] = ARG_QUESTION,
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
) -> None:
    """Query with semantic search (retrieval only, no LLM summary)."""
    text = " ".join(question)
    query.run_query(text, top_k=top_k)


@app.command(name="enrich")
def enrich_cmd(
    slug: str = typer.Argument(None, help="Page slug to enrich"),
    all_pages: bool = typer.Option(False, "--all", "-a", help="Enrich all un-enriched pages"),
) -> None:
    """Enrich a page with LLM-extracted entities, relations, summary, and tags."""
    if all_pages:
        enrich.run_enrich_all()
    elif slug:
        enrich.run_enrich(slug)
    else:
        typer.echo("❌ Provide a slug or use --all")
        raise typer.Exit(1)


@app.command(name="ask")
def ask_cmd(
    question: list[str] = ARG_ASK,
    top_k: int = typer.Option(8, "--top-k", "-k", help="Number of context pages"),
    temperature: float = typer.Option(0.3, "--temperature", "-t", help="LLM temperature"),
) -> None:
    """Ask a question with LLM-enhanced reasoning over the knowledge base."""
    text = " ".join(question)
    cfg = config.load_config()

    llm_cfg = cfg.llm
    if not llm_cfg or not llm_cfg.get("provider"):
        typer.echo("❌ LLM not configured. Add [llm] section to ~/.gmind/config.toml")
        typer.echo("")
        typer.echo("Example:")
        typer.echo('  [llm]')
        typer.echo('  provider = "ollama"')
        typer.echo('  [llm.ollama]')
        typer.echo('  model = "qwen2.5:7b"')
        typer.echo('  base_url = "http://localhost:11434"')
        raise typer.Exit(1)

    engine = llm_engine.load_llm_engine(llm_cfg)
    if engine is None:
        typer.echo("❌ Failed to initialize LLM engine.")
        raise typer.Exit(1)

    if not engine.is_available():
        typer.echo("❌ LLM provider is not available.")
        if llm_cfg.get("provider") == "ollama":
            typer.echo("   Make sure Ollama is running: ollama serve")
        raise typer.Exit(1)

    db.init_pool(cfg.database_url)
    typer.echo(f"🤔 Thinking: {text}\n")

    try:
        result = llm_reason.reasoned_query(text, engine, cfg, top_k=top_k, temperature=temperature)
    except Exception as exc:
        typer.echo(f"❌ Error: {exc}")
        raise typer.Exit(1)

    typer.echo(result["answer"])
    typer.echo("")
    if result["sources"]:
        typer.echo("Sources:")
        for src in result["sources"]:
            typer.echo(f"  • [[{src['slug']}]] {src['title']} ({src['relevance']})")


@app.command(name="sync")
def sync_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only"),
) -> None:
    """Sync local drafts to published state."""
    sync.run_sync(dry_run=dry_run)


@app.command(name="stats")
def stats_cmd() -> None:
    """Show knowledge base statistics."""
    stats.run_stats()


@app.command(name="ingest")
def ingest_cmd(
    path: str = typer.Argument(..., help="File or directory to ingest"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recurse into directories"),
    source: str | None = typer.Option(None, "--source", help="Source reference"),
) -> None:
    """Batch ingest files (.md, .txt, .pdf) into the knowledge base."""
    ingest.run_ingest(path, recursive=recursive, source=source)


@app.command(name="graph")
def graph_cmd(
    slug: str | None = typer.Argument(None, help="Page slug to explore"),
    depth: int = typer.Option(1, "--depth", "-d", help="Graph depth"),
    orphans: bool = typer.Option(False, "--orphans", help="List orphan pages"),
    hubs: bool = typer.Option(False, "--hubs", help="List hub pages"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Rebuild edges from [[links]]"),
) -> None:
    """Query the knowledge graph."""
    if rebuild:
        graph.run_rebuild()
    else:
        graph.run_graph(slug, depth=depth, orphans=orphans, hubs=hubs)


@app.command(name="lint")
def lint_cmd() -> None:
    """Run health checks on the knowledge base."""
    lint.run_lint()


@app.command(name="export")
def export_cmd(
    output_dir: str = typer.Argument(..., help="Output directory"),
) -> None:
    """Export all pages to markdown files."""
    export.run_export(output_dir)


@app.command(name="merge")
def merge_cmd(
    slug: str = typer.Argument(..., help="Page slug to resolve"),
    list_versions: bool = typer.Option(False, "--list", help="List history versions"),
    pick: int | None = typer.Option(None, "--pick", help="Revert to version"),
    edit: bool = typer.Option(False, "--edit", help="Open editor"),
    version: int | None = typer.Option(None, "--version", help="Revert to version"),
) -> None:
    """Manually resolve merge conflicts."""
    merge.run_manual_merge(
        slug,
        list_versions=list_versions,
        pick_version=pick or version,
        edit=edit,
    )


@app.command(name="pending")
def pending_cmd(
    limit: int = typer.Option(1, "--limit", "-l", help="Number of items to return"),
    offset: int = typer.Option(0, "--offset", help="Offset for pagination"),
    json_output: bool = typer.Option(False, "--json", help="JSON output for agents"),
    count: bool = typer.Option(False, "--count", "-c", help="Show count only"),
) -> None:
    """List pending (unprocessed) raw materials."""
    pending.run_pending(limit=limit, offset=offset, json_output=json_output, count_only=count)


@app.command(name="mark")
def mark_cmd(
    slug: str = typer.Argument(..., help="Page slug to mark"),
    state: str = typer.Option("processed", "--state", "-s", help="State: raw or processed"),
) -> None:
    """Mark a page as processed or raw."""
    mark.run_mark(slug, state=state)


@app.command(name="capture")
def capture_cmd(
    agent: str = typer.Argument("hermes", help="Agent name: hermes, claude, codex, kimi, openclaw"),
    session_id: str | None = typer.Option(None, "--session", help="Specific session ID"),
    latest: bool = typer.Option(False, "--latest", "-l", help="Capture latest session"),
    all_sessions: bool = typer.Option(False, "--all", "-a", help="Capture all sessions"),
    all_agents: bool = typer.Option(False, "--all-agents", help="Capture all agents"),
) -> None:
    """Capture agent session history into GMind."""
    capture.run_capture(
        agent,
        session_id=session_id,
        latest=latest,
        all_sessions=all_sessions,
        all_agents=all_agents,
    )


# ─── Taotie commands ──────────────────────────────────────────────

@taotie_app.command(name="scan")
def taotie_scan_cmd(
    classify: bool = typer.Option(True, "--classify", help="Use LLM to classify files"),
) -> None:
    """Scan the computer for knowledge files."""
    typer.echo("🔍 扫描中...")
    files, folders = scan_computer()
    typer.echo(f"发现 {len(files)} 个候选文件")
    typer.echo(f"推荐 {len(folders)} 个监控文件夹")

    if classify:
        typer.echo("🤖 LLM 分类中...")
        from gmind.llm import engine as llm_engine
        cfg = config.load_config()
        engine = None
        if cfg.llm and cfg.llm.get("provider"):
            engine = llm_engine.load_llm_engine(cfg.llm)
        for f in files:
            classify_file(f, engine=engine)

    safe = [f for f in files if f.privacy_level == "safe"]
    sensitive = [f for f in files if f.privacy_level == "sensitive"]
    private = [f for f in files if f.privacy_level == "private"]

    typer.echo(f"  ✅ 安全: {len(safe)}")
    typer.echo(f"  ⚠️  敏感: {len(sensitive)}")
    typer.echo(f"  ⛔ 隐私: {len(private)}")


@taotie_app.command(name="queue")
def taotie_queue_cmd() -> None:
    """Show current ingest queue status."""
    q = IngestQueue()
    state = q.get_state()
    typer.echo(f"队列状态: {'暂停' if state['paused'] else '运行中'}")
    typer.echo(f"总计: {state['total']} 个文件")
    typer.echo(f"待处理: {len(state['pending'])}")
    typer.echo(f"已完成: {len(state['done'])}")
    typer.echo(f"错误: {len(state['error'])}")


@taotie_app.command(name="start")
def taotie_start_cmd() -> None:
    """Start processing the ingest queue."""
    q = IngestQueue()
    q.start()
    typer.echo("🚀 开始入库...")


@taotie_app.command(name="pause")
def taotie_pause_cmd() -> None:
    """Pause the ingest queue."""
    q = IngestQueue()
    q.pause()
    typer.echo("⏸️ 已暂停")


@taotie_app.command(name="resume")
def taotie_resume_cmd() -> None:
    """Resume the ingest queue."""
    q = IngestQueue()
    q.resume()
    typer.echo("▶️ 已恢复")


@taotie_app.command(name="blacklist")
def taotie_blacklist_cmd(
    action: str = typer.Argument("list", help="add / remove / list / clear"),
    path: str = typer.Argument(None, help="File or pattern path"),
) -> None:
    """Manage the blacklist."""
    bl = Blacklist()
    if action == "list":
        data = bl.list_all()
        typer.echo(f"文件: {len(data.get('files', []))}")
        for f in data.get("files", []):
            typer.echo(f"  {f}")
        typer.echo(f"模式: {len(data.get('patterns', []))}")
        typer.echo(f"文件夹: {len(data.get('folders', []))}")
    elif action == "add" and path:
        bl.add_file(path)
        typer.echo(f"✅ 已添加: {path}")
    elif action == "remove" and path:
        bl.remove_file(path)
        typer.echo(f"✅ 已移除: {path}")
    elif action == "clear":
        bl.clear()
        typer.echo("✅ 已清空")
    else:
        typer.echo("用法: gmind taotie blacklist [add|remove|list|clear] [path]")


@taotie_app.command(name="watch")
def taotie_watch_cmd(
    action: str = typer.Argument("list", help="add / remove / list / clear"),
    folder: str = typer.Argument(None, help="Folder path"),
) -> None:
    """Manage watched folders."""
    wc = WatcherConfig()
    if action == "list":
        for f in wc.list_all():
            mode = f"{f['scan_mode']}"
            if f["scan_mode"] == "interval":
                mode = f"每 {f['interval_hours']} 小时"
            elif f["scan_mode"] == "daily":
                mode = f"每天 {f['daily_time']}"
            elif f["scan_mode"] == "weekly":
                days = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
                mode = f"每周{days[f['weekly_day']]} {f['weekly_time']}"
            status = "✅" if f["enabled"] else "⏸️"
            typer.echo(f"  {status} {f['path']} ({mode})")
    elif action == "add" and folder:
        wc.add(folder)
        typer.echo(f"✅ 已添加监控: {folder}")
    elif action == "remove" and folder:
        wc.remove(folder)
        typer.echo(f"✅ 已移除监控: {folder}")
    elif action == "clear":
        wc.clear()
        typer.echo("✅ 已清空")
    else:
        typer.echo("用法: gmind taotie watch [add|remove|list|clear] [folder]")


@taotie_app.command(name="history")
def taotie_history_cmd(
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """Show import history."""
    h = IngestHistory()
    records = h.get_records(limit=limit)
    for r in records:
        icon = "✅" if r["status"] == "ok" else "❌"
        typer.echo(f"{icon} {r['timestamp'][:16]}  {r['path']} → {r['slug']}")


# ─── Server ───────────────────────────────────────────────────────

@app.command(name="serve")
def serve_cmd(
    port: int = typer.Option(8765, "--port", "-p", help="HTTP server port"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
) -> None:
    """Start the GMind HTTP server for browser integrations."""
    import uvicorn

    typer.echo(f"🚀 GMind server running at http://{host}:{port}")
    uvicorn.run(
        server.app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    app()
