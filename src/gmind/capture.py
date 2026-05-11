"""Capture agent session histories into GMind."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from gmind import add, config, db, utils


def run_capture(
    agent: str,
    *,
    session_id: str | None = None,
    latest: bool = False,
    all_sessions: bool = False,
) -> None:
    """Capture sessions from an agent."""
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    if agent.lower() == "hermes":
        if all_sessions:
            _capture_hermes_all(cfg)
        elif latest:
            _capture_hermes_latest(cfg)
        elif session_id:
            _capture_hermes_session(cfg, session_id)
        else:
            typer.echo("❌ Specify --session, --latest, or --all")
            raise typer.Exit(1)
    else:
        typer.echo(f"❌ Unsupported agent: {agent}")
        raise typer.Exit(1)


def _capture_hermes_all(cfg: config.Config) -> None:
    sessions_dir = Path.home() / ".hermes" / "sessions"
    if not sessions_dir.exists():
        typer.echo("❌ Hermes sessions directory not found")
        raise typer.Exit(1)

    files = sorted(
        sessions_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    files += sorted(
        sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    typer.echo(f"Found {len(files)} session files")
    success = 0
    for path in files:
        if _import_hermes_file(path, cfg):
            success += 1
    typer.echo(f"\nDone: {success}/{len(files)} imported")


def _capture_hermes_latest(cfg: config.Config) -> None:
    sessions_dir = Path.home() / ".hermes" / "sessions"
    files = sorted(
        sessions_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    files += sorted(
        sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    if not files:
        typer.echo("❌ No Hermes sessions found")
        raise typer.Exit(1)

    latest = files[0]
    typer.echo(f"Latest: {latest.name}")
    if _import_hermes_file(latest, cfg):
        typer.echo("✅ Imported")
    else:
        typer.echo("❌ Failed")


def _capture_hermes_session(cfg: config.Config, session_id: str) -> None:
    sessions_dir = Path.home() / ".hermes" / "sessions"
    # Try multiple naming patterns
    candidates = [
        sessions_dir / f"session_{session_id}.json",
        sessions_dir / f"{session_id}.json",
        sessions_dir / f"{session_id}.jsonl",
    ]
    for path in candidates:
        if path.exists():
            if _import_hermes_file(path, cfg):
                typer.echo("✅ Imported")
            return

    typer.echo(f"❌ Session not found: {session_id}")
    raise typer.Exit(1)


def _import_hermes_file(path: Path, cfg: config.Config) -> bool:
    """Import a single Hermes session file. Returns True on success."""
    try:
        if path.suffix == ".jsonl":
            messages = _parse_hermes_jsonl(path)
        else:
            messages = _parse_hermes_json(path)
    except Exception as exc:
        typer.echo(f"   ❌ Parse error ({path.name}): {exc}")
        return False

    if not messages:
        typer.echo(f"   ⚠️  No messages ({path.name})")
        return False

    # Build markdown content
    lines = [f"# Hermes Session: {path.stem}\n"]
    for role, content in messages:
        if role == "user":
            lines.append(f"## User\n\n{content}\n")
        elif role == "assistant":
            lines.append(f"## Assistant\n\n{content}\n")

    content = "\n".join(lines)
    slug = utils.slugify(f"hermes-session-{path.stem}")
    source = f"hermes:{path.stem}"

    try:
        add.add_page(
            content,
            page_type="capture",
            title=f"Hermes Session: {path.stem}",
            slug=slug,
            source=source,
            on_duplicate="a",
        )
        typer.echo(f"   ✅ [[{slug}]]")
        return True
    except Exception as exc:
        typer.echo(f"   ❌ Import error: {exc}")
        return False


def _parse_hermes_json(path: Path) -> list[tuple[str, str]]:
    with path.open() as f:
        data = json.load(f)
    messages = data.get("messages", [])
    result = []
    for m in messages:
        role = m.get("role", "")
        if role in ("user", "assistant"):
            content = m.get("content", "")
            if content:
                result.append((role, content))
    return result


def _parse_hermes_jsonl(path: Path) -> list[tuple[str, str]]:
    result = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            role = m.get("role", "")
            if role in ("user", "assistant"):
                content = m.get("content", "")
                if content:
                    result.append((role, content))
    return result
