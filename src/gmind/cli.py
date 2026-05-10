"""CLI entry point for gmind."""

from __future__ import annotations

import typer

from gmind import add, config, db, export, graph, ingest, lint, merge, query, search, stats, sync

app = typer.Typer(help="GMind — Knowledge graph and vector search engine")

ARG_CONTENT = typer.Argument(..., help="Note content")
ARG_QUESTION = typer.Argument(..., help="Question to ask")
ARG_KEYWORD = typer.Argument(..., help="Search keyword")


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
) -> None:
    """Add a note to the knowledge base."""
    text = " ".join(content)
    add.add_page(
        text, page_type=type_, title=title, slug=slug,
        source=source, on_duplicate=on_duplicate,
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


if __name__ == "__main__":
    app()
