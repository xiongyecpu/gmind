# GMind -- Knowledge Graph & Vector Search Engine

[![CI](https://github.com/xiongyecpu/gmind/actions/workflows/ci.yml/badge.svg)](https://github.com/xiongyecpu/gmind/actions/workflows/ci.yml)

> A personal knowledge base backed by PostgreSQL + pgvector. Semantic search, multi-node sync, knowledge graph, and batch file ingestion. **Agent-first**: GMind stores and retrieves; reasoning is the agent's job.

## Features

| Feature | Command | Description |
|---------|---------|-------------|
| Add note | `gmind add "content"` | Auto-embedding, deduplication |
| Vector search | `gmind search "keyword" --json` | Pure semantic search, JSON output for agents |
| Semantic query | `gmind query "question"` | Vector search with human-readable output |
| Batch ingest | `gmind ingest ./docs/` | Import .md / .txt / .pdf |
| Stats | `gmind stats` | Dashboard |
| Sync | `gmind sync` | Draft → published, conflict detection |
| Graph | `gmind graph <slug>` | Link extraction, orphans, hubs |
| Lint | `gmind lint` | Health check |
| Export | `gmind export ./backup/` | Markdown + YAML frontmatter |
| Merge | `gmind merge <slug> --list` | Version history, revert, edit |

## Quick Start

### Requirements

- Python 3.12+
- PostgreSQL 14+ with [pgvector](https://github.com/pgvector/pgvector) extension
- [uv](https://docs.astral.sh/uv/) (recommended)
- Embedding API key ([SiliconFlow](https://siliconflow.cn/) 或任意 OpenAI-compatible)

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

#### 2. 安装 GMind CLI

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

# Search (agent-friendly JSON)
gmind search "vector database" --json

# Query (human-friendly)
gmind query "What is a vector database?"

# Batch ingest
gmind ingest ./papers/ --recursive

# Dashboard
gmind stats

# Publish drafts + detect conflicts
gmind sync

# Rebuild knowledge graph from [[links]]
gmind graph --rebuild

# Health check
gmind lint

# Export all pages
gmind export ./backup/
```

## Architecture

All nodes share one PostgreSQL database. Visibility is controlled by `origin_node` + `status` columns (`draft` / `published` / `merge_review`). No bidirectional push/pull needed — sync is a simple state machine.

### Agent-First Design

GMind does **not** call LLMs. This is intentional:

- **GMind** = memory (store, retrieve, sync, search)
- **Agent** = brain (reason, summarize, merge, answer)

Agents use `gmind search --json` to retrieve raw data, then synthesize answers with their own model. This eliminates redundant LLM calls and lets the agent control the reasoning chain.

## Database Schema

| Table | Purpose |
|-------|---------|
| pages | Global pages with 1024-dim vector embeddings |
| page_history | Change history with full JSONB snapshots |
| edges | Knowledge graph relationships |
| sync_log | Sync audit log with request_id dedup |

## Tech Stack

- Python 3.12+, Typer, psycopg, pgvector
- Embeddings: SiliconFlow / OpenAI-compatible APIs (BAAI/bge-m3)
- Packaging: uv + pyproject.toml
- Testing: pytest + GitHub Actions CI

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
- Agent design principles ("You ARE the LLM")
- Writing rules (`--source`, `[[slug]]` references, entity types)
- Prohibited actions (no raw dumps, no unconfirmed overwrites)

### Key Principle: Agent is the Brain, GMind is the Memory

| Task | Who |
|------|-----|
| Store, retrieve, sync, export | **GMind CLI** |
| Generate embeddings | **GMind CLI** |
| Reason, summarize, answer | **You (the agent)** |
| Merge conflict judgment | **You (the agent)** |

## Development

```bash
ruff check src/ tests/
pytest -v
```

## Roadmap

| Phase | Status | Commands |
|-------|--------|----------|
| P0 Core | ✅ Done | init, add, search, query |
| P1 Sync | ✅ Done | sync, merge |
| P2 Ingest | ✅ Done | ingest |
| P3 Graph | ✅ Done | graph |
| P4 Maintenance | ✅ Done | stats, lint, export |
| P5 Open Source | ✅ Done | docs, CI/CD, skill install |

## License

MIT
