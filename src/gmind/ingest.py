"""Batch ingest files and directories into the knowledge base."""

from __future__ import annotations

from pathlib import Path

import typer

from gmind import add, config, db, utils


def run_ingest(
    path: str,
    *,
    recursive: bool = False,
    source: str | None = None,
) -> None:
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    target = Path(path)
    if target.is_file():
        files = [target]
    elif target.is_dir():
        pattern = "**/*" if recursive else "*"
        files = [
            f for f in target.glob(pattern)
            if f.is_file() and f.suffix.lower() in (".md", ".txt", ".pdf")
        ]
    else:
        typer.echo(f"Path not found: {path}")
        raise typer.Exit(1)

    if not files:
        typer.echo("No supported files found (.md, .txt, .pdf)")
        return

    typer.echo(f"Found {len(files)} file(s) to ingest\n")
    success = 0
    skipped = 0

    for file_path in files:
        result = _ingest_file(file_path, cfg, source)
        if result == "ok":
            success += 1
        elif result == "skip":
            skipped += 1

    typer.echo(f"\nDone: {success} ingested, {skipped} skipped")


def _ingest_file(file_path: Path, cfg: config.Config, source: str | None) -> str:
    typer.echo(f"📄 {file_path}")

    content = _extract_text(file_path)
    if not content or not content.strip():
        typer.echo("   ⚠️  Empty content, skipped")
        return "skip"

    # Simple heuristic extraction (no LLM)
    title = _extract_title_heuristic(content, file_path.stem)

    # Combine title + content for storage
    full_content = f"# {title}\n\n{content}"

    page_type = _infer_type(title, content)
    slug = utils.slugify(title)
    try:
        add.add_page(
            full_content,
            page_type=page_type,
            title=title,
            slug=slug,
            source=source or f"ingest:{file_path}",
            on_duplicate="a",
        )
        typer.echo(f"   ✅ [[{slug}]]")
        return "ok"
    except Exception as exc:
        typer.echo(f"   ❌ {exc}")
        return "skip"


def _infer_type(title: str, content: str) -> str:
    """Infer page type from title/content keywords (heuristic, no LLM)."""
    text = (title + " " + content[:500]).lower()
    if any(k in text for k in ("公司", "集团", "科技", "有限", "corp", "inc", "ltd", "company")):
        return "company"
    if any(k in text for k in ("项目", "工程", "系统", "platform", "project")):
        return "project"
    if any(k in text for k in ("教授", "博士", "先生", "女士", "founder", "ceo", "author")):
        return "person"
    if any(k in text for k in ("产品", "工具", "app", "软件", "product", "tool")):
        return "product"
    return "source"


def _extract_title_heuristic(content: str, fallback: str) -> str:
    lines = content.strip().splitlines()
    i = 0
    # Skip YAML frontmatter
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            i += 1
        i += 1  # skip closing ---
    # Find first markdown heading
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line and not line.startswith("---"):
            # First non-empty non-frontmatter line
            return line[:80]
        i += 1
    return fallback


def _extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in (".md", ".txt"):
        return file_path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            typer.echo(f"   ⚠️  PDF read error: {exc}")
            return ""
    return ""
