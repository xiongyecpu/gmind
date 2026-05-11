"""Capture agent session histories into GMind."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from gmind import add, config, db, utils

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

AGENTS = ("hermes", "claude", "codex", "kimi", "openclaw")


def run_capture(
    agent: str,
    *,
    session_id: str | None = None,
    latest: bool = False,
    all_sessions: bool = False,
    all_agents: bool = False,
) -> None:
    """Capture sessions from an agent."""
    cfg = config.load_config()
    db.init_pool(cfg.database_url)

    if all_agents:
        _capture_all_agents(cfg, latest=latest, all_sessions=all_sessions)
        return

    name = agent.lower()
    if name not in AGENTS:
        typer.echo(f"❌ Unsupported agent: {agent}. Supported: {', '.join(AGENTS)}")
        raise typer.Exit(1)

    if all_sessions:
        _capture_all(name, cfg)
    elif latest:
        _capture_latest(name, cfg)
    elif session_id:
        _capture_by_id(name, cfg, session_id)
    else:
        typer.echo("❌ Specify --session, --latest, or --all")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _capture_all_agents(
    cfg: config.Config, *, latest: bool = False, all_sessions: bool = False
) -> None:
    """Capture sessions from all supported agents."""
    for name in AGENTS:
        typer.echo(f"\n=== {name.upper()} ===")
        if all_sessions:
            _capture_all(name, cfg)
        elif latest:
            _capture_latest(name, cfg)
        else:
            _capture_latest(name, cfg)


def _capture_all(agent: str, cfg: config.Config) -> None:
    files = _list_sessions(agent)
    typer.echo(f"Found {len(files)} session files for {agent}")
    success = 0
    for path in files:
        if _import_file(agent, path, cfg):
            success += 1
    typer.echo(f"\nDone: {success}/{len(files)} imported")


def _capture_latest(agent: str, cfg: config.Config) -> None:
    files = _list_sessions(agent)
    if not files:
        typer.echo(f"❌ No {agent} sessions found")
        raise typer.Exit(1)
    latest_file = files[0]
    typer.echo(f"Latest: {latest_file.name}")
    if _import_file(agent, latest_file, cfg):
        typer.echo("✅ Imported")
    else:
        typer.echo("❌ Failed")


def _capture_by_id(agent: str, cfg: config.Config, session_id: str) -> None:
    files = _list_sessions(agent)
    for path in files:
        if session_id in path.name:
            if _import_file(agent, path, cfg):
                typer.echo("✅ Imported")
            return
    typer.echo(f"❌ Session not found: {session_id}")
    raise typer.Exit(1)


def _import_file(agent: str, path: Path, cfg: config.Config) -> bool:
    """Import a single session file. Returns True on success."""
    try:
        messages = _parse_session(agent, path)
    except Exception as exc:
        typer.echo(f"   ❌ Parse error ({path.name}): {exc}")
        return False

    if not messages:
        typer.echo(f"   ⚠️  No messages ({path.name})")
        return False

    lines = [f"# {agent.title()} Session: {path.stem}\n"]
    for role, content in messages:
        lines.append(f"## {role.title()}\n\n{content}\n")

    content = "\n".join(lines)
    slug = utils.slugify(f"{agent}-session-{path.stem}")
    source = f"{agent}:{path.stem}"

    try:
        add.add_page(
            content,
            page_type="capture",
            title=f"{agent.title()} Session: {path.stem}",
            slug=slug,
            source=source,
            on_duplicate="a",
        )
        typer.echo(f"   ✅ [[{slug}]]")
        return True
    except Exception as exc:
        typer.echo(f"   ❌ Import error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Agent-specific: list sessions
# ---------------------------------------------------------------------------


def _list_sessions(agent: str) -> list[Path]:
    """Return session files sorted by mtime (newest first)."""
    if agent == "hermes":
        d = Path.home() / ".hermes" / "sessions"
        files = list(d.glob("session_*.json")) + list(d.glob("*.jsonl"))
    elif agent == "claude":
        d = Path.home() / ".claude" / "projects"
        files = []
        for proj in d.glob("*"):
            if proj.is_dir():
                files.extend(proj.glob("*.jsonl"))
    elif agent == "codex":
        d = Path.home() / ".codex" / "archived_sessions"
        files = list(d.glob("*.jsonl"))
    elif agent == "kimi":
        d = Path.home() / ".kimi" / "sessions"
        files = []
        for workspace in d.glob("*"):
            if workspace.is_dir() and not workspace.name.startswith("."):
                for sess in workspace.glob("*"):
                    if sess.is_dir():
                        wire = sess / "wire.jsonl"
                        if wire.exists():
                            files.append(wire)
    elif agent == "openclaw":
        d = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
        files = list(d.glob("*.jsonl"))
        # Exclude sessions.json (metadata index)
        files = [f for f in files if f.name != "sessions.json"]
    else:
        files = []
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


# ---------------------------------------------------------------------------
# Agent-specific: parse session
# ---------------------------------------------------------------------------


def _parse_session(agent: str, path: Path) -> list[tuple[str, str]]:
    if agent == "hermes":
        return _parse_hermes(path)
    elif agent == "claude":
        return _parse_claude(path)
    elif agent == "codex":
        return _parse_codex(path)
    elif agent == "kimi":
        return _parse_kimi(path)
    elif agent == "openclaw":
        return _parse_openclaw(path)
    return []


# --- Hermes ---


def _parse_hermes(path: Path) -> list[tuple[str, str]]:
    if path.suffix == ".jsonl":
        return _parse_hermes_jsonl(path)
    with path.open() as f:
        data = json.load(f)
    result = []
    for m in data.get("messages", []):
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


# --- Claude Code ---


def _parse_claude(path: Path) -> list[tuple[str, str]]:
    """Claude Code project sessions: JSON Lines with role + message."""
    result = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            # Skip meta/system entries
            if data.get("isMeta"):
                continue
            role = data.get("role", "")
            msg = data.get("message", {})
            msg_role = msg.get("role", "")
            effective_role = role or msg_role
            if effective_role not in ("user", "assistant"):
                continue
            content = msg.get("content", "")
            text = ""
            if isinstance(content, list) and content:
                parts = []
                for part in content:
                    if isinstance(part, dict):
                        parts.append(part.get("text", ""))
                    else:
                        parts.append(str(part))
                text = "\n".join(parts)
            elif isinstance(content, str):
                text = content
            if text and not text.startswith("<local-command"):
                result.append((effective_role, text))
    return result


# --- Codex ---


def _parse_codex(path: Path) -> list[tuple[str, str]]:
    """Codex archived_sessions: JSON Lines with type + payload."""
    result = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("type") != "response_item":
                continue
            payload = data.get("payload", {})
            role = payload.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = payload.get("content", [])
            text = ""
            if isinstance(content, list) and content:
                parts = []
                for part in content:
                    if isinstance(part, dict):
                        parts.append(part.get("text", ""))
                    else:
                        parts.append(str(part))
                text = "\n".join(parts)
            elif isinstance(content, str):
                text = content
            if text:
                result.append((role, text))
    return result


# --- Kimi ---


def _parse_kimi(path: Path) -> list[tuple[str, str]]:
    """Kimi wire.jsonl: TurnBegin (user) + ContentPart text (assistant)."""
    result = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            msg = data.get("message", {})
            msg_type = msg.get("type", "")
            payload = msg.get("payload", {})

            if msg_type == "TurnBegin":
                user_input = payload.get("user_input", "")
                if user_input:
                    result.append(("user", user_input))
            elif msg_type == "ContentPart":
                part_type = payload.get("type", "")
                if part_type == "text":
                    text = payload.get("text", "")
                    if text:
                        result.append(("assistant", text))
                elif part_type == "think":
                    think = payload.get("think", "")
                    if think:
                        result.append(("assistant", f"*(thinking)*\n\n{think}"))
    return result


# --- OpenClaw ---


def _parse_openclaw(path: Path) -> list[tuple[str, str]]:
    """OpenClaw session JSONL: type=user/assistant/message with content."""
    result = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            msg_type = data.get("type", "")
            if msg_type in ("user", "assistant"):
                text = _extract_text_from_content(data.get("content", ""))
                if text:
                    result.append((msg_type, text))
            elif msg_type == "message":
                msg = data.get("message", {})
                role = msg.get("role", "")
                if role in ("user", "assistant"):
                    text = _extract_text_from_content(msg.get("content", ""))
                    if text:
                        result.append((role, text))
    return result


def _extract_text_from_content(content) -> str:
    """Extract plain text from various content formats (str, list of dicts, etc.)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content:
        parts = []
        for part in content:
            if isinstance(part, dict):
                if "text" in part:
                    parts.append(part["text"])
                elif "thinking" in part:
                    parts.append(f"*(thinking)*\n\n{part['thinking']}")
            else:
                parts.append(str(part))
        return "\n".join(parts)
    return ""
