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

app = typer.Typer(help="GMind — Knowledge graph and vector search engine")

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
    slug: str = typer.Argument(..., help="Page slug to enrich"),
) -> None:
    """Enrich a page with LLM-extracted entities, relations, summary, and tags."""
    enrich.run_enrich(slug)


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
