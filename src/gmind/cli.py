"""CLI entry point for gmind."""

from __future__ import annotations

import typer

from gmind import add, config, db, merge, query, sync

app = typer.Typer(help="GMind — Knowledge graph and vector search engine")

ARG_CONTENT = typer.Argument(..., help="Note content")
ARG_QUESTION = typer.Argument(..., help="Question to ask")


@app.command()
def init(
    node: str = typer.Option("default", "--node", "-n", help="Node name"),
) -> None:
    """Initialize gmind configuration and database."""
    typer.echo("🔧 GMind initialization")
    database_url = typer.prompt("PostgreSQL connection URL")
    embedding_api_key = typer.prompt("Embedding API key (SiliconFlow)", hide_input=True)
    embedding_model = typer.prompt("Embedding model", default="BAAI/bge-m3")
    llm_api_key = typer.prompt("LLM API key (SiliconFlow)", hide_input=True)
    llm_model = typer.prompt("LLM model", default="deepseek-ai/DeepSeek-V3")

    cfg = config.Config(
        database_url=database_url,
        node_name=node,
        embedding_api_key=embedding_api_key,
        embedding_model=embedding_model,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
    )
    config.save_config(cfg)
    typer.echo(f"✅ Config saved to {config.DEFAULT_CONFIG_PATH}")

    db.init_db(database_url)
    typer.echo("✅ Database initialized")


@app.command(name="add")
def add_cmd(
    content: list[str] = ARG_CONTENT,
    type_: str = typer.Option("note", "--type", "-t", help="Page type"),
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


@app.command(name="query")
def query_cmd(
    question: list[str] = ARG_QUESTION,
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
) -> None:
    """Query the knowledge base with semantic search."""
    text = " ".join(question)
    query.run_query(text, top_k=top_k)


@app.command()
def sync_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only"),
) -> None:
    """Sync local drafts to published state."""
    sync.run_sync(dry_run=dry_run)


@app.command()
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
