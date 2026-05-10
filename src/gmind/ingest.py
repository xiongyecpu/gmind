"""Batch ingest files and directories into the knowledge base."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from gmind import add, config, db, llm, utils

MAX_LLM_CHARS = 8000


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

    # 1. Extract text
    content = _extract_text(file_path)
    if not content or not content.strip():
        typer.echo("   ⚠️  Empty content, skipped")
        return "skip"

    # 2. LLM extraction (truncate if too long)
    llm_input = content[:MAX_LLM_CHARS]
    extracted = _llm_extract(llm_input, cfg)
    if extracted is None:
        typer.echo("   ❌ LLM extraction failed, skipped")
        return "skip"

    title = extracted.get("title", file_path.stem)
    summary = extracted.get("summary", content[:500])
    page_type = extracted.get("page_type", "note")

    # Combine summary + full content for storage
    full_content = f"# {title}\n\n{summary}\n\n## Full Content\n\n{content}"

    # 3. Write to DB (bypass interactive dedup for batch ingest)
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


def _llm_extract(content: str, cfg: config.Config) -> dict[str, str] | None:
    if not cfg.llm_api_key:
        # Fallback: use filename heuristics
        return {
            "title": content[:50].strip(),
            "summary": content[:300].strip(),
            "keywords": "",
            "page_type": "source",
        }

    prompt = (
        "请分析以下文档，提取结构化信息。\n\n"
        "1. 标题（简短，一行）\n"
        "2. 摘要（3-5 句话）\n"
        "3. 关键词（5-10 个，逗号分隔）\n"
        "4. 页面类型（note/entity/concept/source 之一）\n\n"
        f"文档内容：\n---\n{content}\n---\n\n"
        "请以纯 JSON 输出，不要 Markdown 代码块：\n"
        '{"title": "...", "summary": "...", "keywords": "...", "page_type": "..."}'
    )

    try:
        raw = llm.chat(prompt, cfg, temperature=0.2)
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)
        return json.loads(raw)
    except Exception:
        return None
