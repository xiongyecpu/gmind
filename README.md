# GMind -- Knowledge Graph & Vector Search Engine

[![CI](https://github.com/xiongyecpu/gmind/actions/workflows/ci.yml/badge.svg)](https://github.com/xiongyecpu/gmind/actions/workflows/ci.yml)

> A personal knowledge base backed by PostgreSQL + pgvector. Semantic search, multi-node sync, knowledge graph, batch file ingestion, and optional built-in LLM reasoning.
>
> Desktop direction: GMind is now moving to an Electron-based menu bar app. The app registers the `gmind` CLI and manages the local HTTP server automatically.

## Features

| Feature | Command | Description |
|---------|---------|-------------|
| Add note | `gmind add "content"` | Auto-embedding, deduplication |
| Vector search | `gmind search "keyword" --json` | Pure semantic search, JSON output for agents |
| Semantic query | `gmind query "question"` | Vector search with human-readable output |
| Batch ingest | `gmind ingest ./docs/` | Import .md / .txt / .pdf |
| Auto-extract | `gmind add "..." --auto-extract` | Opt-in from CLI: LLM entities, relations, tags |
| Enrich | `gmind enrich <slug> / --all` | LLM knowledge enhancement |
| Ask | `gmind ask "question"` | RAG Q&A over knowledge base |
| Capture | `gmind capture hermes --latest` | Import agent session history |
| Stats | `gmind stats` | Knowledge base overview |
| Sync | `gmind sync` | Draft → published, conflict detection |
| Graph | `gmind graph <slug>` | Link extraction, orphans, hubs |
| Lint | `gmind lint` | Health check |
| Export | `gmind export ./backup/` | Markdown + YAML frontmatter |
| Merge | `gmind merge <slug> --list` | Version history, revert, edit |
| Taotie | `gmind taotie scan` | Full-computer scan, classification, ingest queue |
| HTTP server | `gmind serve --port 8765` | Local API for browser extensions |
| Chrome clipper | (extension) | Reader-mode → Markdown → one-click save |

## Quick Start

GMind supports both the developer/CLI workflow below and the new desktop app workflow. The product direction is `GMind.app`: launch the app, let it register the CLI, and let it start the local HTTP server.

### Requirements

- Python 3.12+
- PostgreSQL 14+ with [pgvector](https://github.com/pgvector/pgvector) extension
- [uv](https://docs.astral.sh/uv/) (recommended)
- Embedding API key ([SiliconFlow](https://siliconflow.cn/) 或任意 OpenAI-compatible)
- Optional LLM provider for `ask`, `enrich`, and `--auto-extract` (Ollama or OpenAI-compatible)

#### 1. 启动 PostgreSQL + pgvector

**Docker（推荐，一键启动）：**
```bash
docker run -d \
  --name gmind-postgres \
  -e POSTGRES_USER=gbrain \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=gmind \
  -p 5432:5432 \
  ankane/pgvector:latest
```

**本地安装（macOS）：**
```bash
brew install postgresql@16
brew install pgvector
brew services start postgresql@16
# 创建数据库
createdb gmind
psql gmind -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 2. 安装 GMind CLI（当前开发者方式）

**一键安装（推荐）：**
```bash
git clone https://github.com/xiongyecpu/gmind.git
cd gmind
./install.sh
```

**手动安装：**
```bash
git clone https://github.com/xiongyecpu/gmind.git
cd gmind
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

**加到 PATH（不然打 `gmind` 会报 command not found）：**
```bash
# 临时（当前终端）
export PATH="$PWD/.venv/bin:$PATH"

# 永久（推荐）
ln -s "$PWD/.venv/bin/gmind" ~/.local/bin/gmind
# 确保 ~/.local/bin 在 PATH 中
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc  # 或 ~/.zshrc
```

#### 3. 初始化配置

```bash
gmind init --node home
```

交互式询问三项：
- PostgreSQL URL（如 `postgresql://gbrain:your_password@localhost:5432/gmind`）
- Embedding API key（SiliconFlow 的 key）
- Embedding model（默认 `BAAI/bge-m3`，1024 维）

配置保存到 `~/.gmind/config.toml`，示例：

```toml
database_url = "postgresql://gbrain:your_password@localhost:5432/gmind"
node_name = "home"
embedding_api_key = "sk-xxxxx"
embedding_model = "BAAI/bge-m3"
embedding_base_url = "https://api.siliconflow.cn/v1"
```

### Usage

```bash
# Add a note
gmind add "Vector databases store high-dimensional embeddings" --title "Vector DB"

# Add a note and run LLM extraction
gmind add "Vector databases store high-dimensional embeddings" --title "Vector DB" --auto-extract

# Search (agent-friendly JSON)
gmind search "vector database" --json

# Query (human-friendly)
gmind query "What is a vector database?"

# Batch ingest
gmind ingest ./papers/ --recursive

# Capture latest agent session (hermes / openclaw / claude / kimi / codex)
gmind capture hermes --latest

# Full-computer knowledge discovery
gmind taotie scan
gmind taotie start

# Knowledge base overview
gmind stats

# Publish drafts + detect conflicts
gmind sync

# Rebuild knowledge graph from [[links]]
gmind graph --rebuild

# Health check
gmind lint

# Export all pages
gmind export ./backup/

# Start HTTP server for Chrome extension
gmind serve --port 8765
```

## Architecture

All nodes share one PostgreSQL database. Visibility is controlled by `origin_node` + `status` columns (`draft` / `published` / `merge_review`). No bidirectional push/pull needed — sync is a simple state machine.

### Desktop App Direction

The product shape is:

```text
Install GMind.app
→ Launch GMind.app
→ App checks ~/.gmind/config.toml
→ App registers the gmind CLI
→ App starts the local HTTP server
→ App, CLI, Chrome Extension, and agent skills share localhost APIs
```

In this model, `GMind.app` is the product entry point. The CLI remains first-class for agents and terminal workflows, but it is installed and repaired by the app instead of requiring a manual `uv` or editable Python install.

Target runtime architecture:

```text
┌─────────────────────────────────────────────────────────┐
│                     GMind.app                            │
│                                                         │
│  Electron UI                                            │
│  - Tray/menu bar entry / panels / settings              │
│                                                         │
│  App services                                           │
│  - ServerManager                                        │
│  - CLIRegistrationManager                               │
│  - Config and diagnostics                               │
│                                                         │
│  Bundled backend                                        │
│  - Python CLI                                           │
│  - Starlette HTTP server                                │
└─────────────────────────────────────────────────────────┘
             ▲
             │
      ~/.local/bin/gmind
      CLI shim managed by GMind.app
```

The Electron app currently registers a managed CLI shim, starts `gmind serve`, exposes settings/diagnostics, and keeps the app as the primary local product entry. Release packaging will move the backend from a development CLI path to an app-bundled backend runtime.

macOS remains a menu bar app. The cross-platform concept is a tray/status app: macOS maps to the menu bar extra, Windows maps to the notification area, and Linux maps to the available desktop tray implementation. Electron is the selected desktop shell.

### Memory-First, Optional LLM

GMind started as an agent-first memory system, but current versions also include optional built-in LLM features:

- **Always on**: store, embed, retrieve, sync, export, graph lookup.
- **Optional LLM**: `gmind ask`, `gmind enrich`, and `gmind add --auto-extract`.
- **Agent workflow**: agents can still use `gmind search --json` and synthesize answers themselves.

If no `[llm]` provider is configured, GMind remains a pure retrieval and memory tool.

## Database Schema

| Table | Purpose |
|-------|---------|
| pages | Global pages with 1024-dim vector embeddings |
| page_history | Change history with full JSONB snapshots |
| edges | Knowledge graph relationships (`link_type`, `weight`, `confidence`, `evidence`, `created_by`) |
| sync_log | Sync audit log with request_id dedup |

Current `edges` schema does not include an `edges.source` column. Source-like provenance should use a schema migration or existing `created_by` / `evidence` fields.

## Tech Stack

- Python 3.12+, Typer, psycopg, pgvector
- Embeddings: SiliconFlow / OpenAI-compatible APIs (BAAI/bge-m3)
- LLM: Ollama or OpenAI-compatible providers, with SQLite response cache
- HTTP API: Starlette + uvicorn
- Browser: Chrome Extension (Manifest V3, Defuddle + Turndown)
- Desktop app: Electron tray/status app with Node process management and HTML/CSS/JS UI
- Packaging: uv + pyproject.toml for backend development; Electron app bundle for desktop
- Testing: pytest + GitHub Actions CI

## Repository Layout

```text
.
├── src/gmind/                  # Python backend, CLI, HTTP API, core knowledge logic
│   ├── cli.py                  # Typer CLI entrypoint
│   ├── server.py               # Starlette HTTP server
│   ├── db.py                   # PostgreSQL + pgvector access
│   ├── config.py               # ~/.gmind/config.toml loading/saving
│   ├── llm/                    # LLM providers, cache, extraction, reasoning
│   └── taotie/                 # File scan, classification, ingest queue, watcher config
├── gmind-desktop/              # Electron tray app, selected cross-platform desktop shell
│   ├── src/                    # Web UI for tray panels and settings
│   └── src/electron/           # Electron app shell, tray, server/CLI management
├── chrome-extension/           # Chrome extension that talks to localhost:8765
├── docs/                       # Design notes and migration plans
├── skills/                     # Agent skill definitions
├── tests/                      # pytest suite
└── pyproject.toml              # Python package and CLI metadata
```

Planned App packaging layout:

```text
GMind.app/
  Contents/
    MacOS/
      GMind                    # Electron app executable
      gmind                    # App-bundled CLI launcher
    Resources/
      backend/                 # Bundled Python backend/runtime artifacts
      cli-shim-template        # Template for ~/.local/bin/gmind

User runtime files:
  ~/.gmind/config.toml
  ~/.local/bin/gmind
  ~/Library/Application Support/GMind/
  ~/Library/Logs/GMind/server.log
```

## Agent Integration

GMind provides a `gmind-cli` skill for AI agents following the [agentskills.io](https://agentskills.io/) standard. Supported agents: **Hermes**, **OpenClaw**, **Kimi Code CLI**.

### Install Skill

```bash
# Auto-detect agents and install everywhere
./install-skill.sh

# Install to specific agents
./install-skill.sh hermes,openclaw

# Install to all detected agents
./install-skill.sh --all

# Check what agents are detected
./install-skill.sh --check
```

The skill file is at `skills/gmind-cli/SKILL.md` in this repo. It defines:
- Core commands and their JSON output format
- Agent design principles for retrieval, synthesis, and optional `gmind ask`
- Writing rules (`--source`, `[[slug]]` references, entity types)
- Prohibited actions (no raw dumps, no unconfirmed overwrites)

### Key Principle: GMind is Memory, LLM is Optional

| Task | Who |
|------|-----|
| Store, retrieve, sync, export | **GMind CLI** |
| Generate embeddings | **GMind CLI** |
| Reason, summarize, answer | **GMind CLI via `ask`** or **you (the agent)** |
| Entity/relation extraction | **GMind CLI via `enrich` / `--auto-extract`** |
| Merge conflict judgment | **You (the agent)** |

## Development

```bash
uv run ruff check src/ tests/
uv run pytest -v
```

## Chrome Extension

A companion browser extension lives in `chrome-extension/`:

- **Reader Mode** extraction via Defuddle (removes ads, nav, sidebars)
- **Auto-converts** extracted HTML to Markdown via Turndown.js
- **One-click save** sends `POST /add` to `localhost:8765`
- **URL deduplication**: already-saved pages show a greyed-out "Saved" button

### Install the extension

1. Start GMind:
   - Current developer flow: `gmind serve --port 8765`
   - App flow: launch `GMind.app`
2. Chrome → **Extensions** → Enable **Developer mode**
3. **Load unpacked** → select the `chrome-extension/` folder in this repo
4. Open any web page and click the GMind icon in the toolbar

## Roadmap

| Phase | Status | Commands |
|-------|--------|----------|
| P0 Core | ✅ Done | init, add, search, query |
| P1 Sync | ✅ Done | sync, merge |
| P2 Ingest | ✅ Done | ingest |
| P3 Graph | ✅ Done | graph |
| P4 Maintenance | ✅ Done | stats, lint, export |
| P5 Open Source | ✅ Done | docs, CI/CD, skill install |
| P6 Browser | ✅ Done | gmind serve, Chrome extension |
| P7 LLM Engine | ✅ Done | ask, enrich, auto-extract, capture |
| P9 Taotie | ✅ Done | Scan, classification, queue, history, watcher config |
| P10 Electron desktop app | In progress | Tray app installs CLI, bundles backend, manages serve |

Implementation notes:
- CLI `gmind add` only runs LLM extraction when `--auto-extract` is passed.
- HTTP `/add` currently uses the lower-level add flow and may auto-enrich when LLM is configured.
- Taotie can scan `.docx` files and classify previews, but `gmind ingest` currently imports `.md`, `.txt`, and `.pdf` only.
- Watcher support currently stores folder configuration and the desktop radar scan uses those folders when configured; a standalone background watcher daemon is not part of the current implementation.
- Electron is the desktop mainline.

## LLM Integration (v3)

GMind now supports built-in LLM for knowledge extraction and reasoning.

### Configuration

Add to `~/.gmind/config.toml`:

```toml
[llm]
provider = "ollama"  # or "openai"

[llm.ollama]
model = "qwen2.5:7b"
base_url = "http://localhost:11434"

[llm.openai]
api_key = "sk-..."
model = "gpt-4o-mini"
base_url = "https://api.openai.com/v1"
```

### Commands

```bash
# LLM-enhanced Q&A over your knowledge base
gmind ask "What do I know about vector databases?"

# Enrich a page with auto-extracted entities, relations, tags
gmind enrich vector-databases

# Auto-extract when adding a note from CLI
gmind add "Some content..." --auto-extract
```

### HTTP API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Desktop/server health check |
| `/ask` | POST | LLM Q&A with citations |
| `/enrich` | POST | Auto-extract entities & relations |
| `/search` | GET | Vector search (JSON) |
| `/taotie/scan` | GET | Full-computer file scan |
| `/taotie/queue` | GET | Ingest queue state |
| `/taotie/queue/start` | POST | Start ingest queue |
| `/taotie/queue/pause` | POST | Pause ingest queue |
| `/taotie/queue/clear` | POST | Clear ingest queue |
| `/taotie/queue/add` | POST | Add files to ingest queue |
| `/taotie/queue/select` | POST | Select or unselect a queued file |
| `/taotie/queue/remove` | POST | Remove a queued file and blacklist it |
| `/taotie/history` | GET | Import history |
| `/taotie/watcher` | GET | Watched folder configuration |
| `/taotie/watcher/add` | POST | Add watched folder configuration |
| `/taotie/watcher/remove` | POST | Remove watched folder configuration |

## Desktop Tray App

The cross-platform desktop app lives in `gmind-desktop/`. It is the selected direction for macOS menu bar, Windows notification area, and future Linux tray builds:

- `GMind.app` starts and monitors the local HTTP server.
- `GMind.app` registers `~/.local/bin/gmind`.
- Development builds can use the repo `.venv/bin/gmind`; release builds should use the app-bundled backend runtime.
- Product shape remains menu bar first; auxiliary windows are for settings, diagnostics, Knowledge Radar, and deeper workflows.

```bash
cd gmind-desktop
npm install
npm run build
npm run electron:build
```

Features:
- Tray/menu bar entry
- Quick Add panel
- Ask AI panel
- Knowledge Radar full-computer scan and ingest queue
- Model config
- Auto-starts the local GMind server

Electron is now the only desktop app implementation kept in the repository.

## License

MIT
