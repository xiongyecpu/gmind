# GMind -- Knowledge Graph and Vector Search Engine

> A personal knowledge base backed by PostgreSQL + pgvector. Supports semantic search, multi-node sync, knowledge graph, and batch file ingestion.

## Features

| Feature | Command | Description |
|---------|---------|-------------|
| Add note | `gmind add "content"` | Auto-embedding, deduplication |
| Vector search | `gmind search "keyword" --json` | Pure semantic search, JSON output |
| Semantic query | `gmind query "question"` | Vector search + LLM summary |
| Batch ingest | `gmind ingest ./docs/` | Import .md / .txt / .pdf |
| Stats | `gmind stats` | Dashboard |
| Sync | `gmind sync` | Draft -> published, conflict detection |
| Graph | `gmind graph <slug>` | Link extraction, orphans, hubs |
| Lint | `gmind lint` | Health check |
| Export | `gmind export ./backup/` | Markdown + YAML frontmatter |
| Merge | `gmind merge <slug> --list` | Version history, revert, edit |

## Quick Start

### Requirements

- Python 3.12+
- PostgreSQL 14+ with [pgvector](https://github.com/pgvector/pgvector) extension
- [uv](https://docs.astral.sh/uv/) (recommended)

### Install

```bash
git clone https://github.com/xiongyecpu/gmind.git
cd gmind
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Init

```bash
gmind init --node home
```

### Usage

```bash
gmind add "Vector databases store high-dimensional embeddings" --title "Vector DB"
gmind search "vector database" --json
gmind query "What is a vector database?"
gmind ingest ./papers/ --recursive
gmind stats
gmind sync
gmind graph --rebuild
gmind lint
gmind export ./backup/
```

## Architecture

All nodes share one PostgreSQL database. Visibility controlled by `origin_node` + `status` (draft / published / merge_review). No bidirectional push/pull needed.

## Database Schema

| Table | Purpose |
|-------|---------|
| pages | Global pages with 1024-dim vector embeddings |
| page_history | Change history with full JSONB snapshots |
| edges | Knowledge graph relationships |
| sync_log | Sync audit log with request_id dedup |

## Tech Stack

- Python 3.12+, Typer, psycopg, pgvector
- Embeddings: SiliconFlow / OpenAI-compatible APIs
- Packaging: uv + pyproject.toml
- Testing: pytest

## Agent Integration

GMind provides a `gmind-cli` skill for AI agents. Key principle: **Agent is the brain, GMind is the memory**.

- Agents use `gmind search --json` to retrieve data, then synthesize answers with their own model
- No LLM API key needed for pure retrieval workflows
- Skill file: `skills/gmind-cli/SKILL.md`

## Roadmap

| Phase | Status | Commands |
|-------|--------|----------|
| P0 Core | Done | init, add, search, query |
| P1 Sync | Done | sync, merge |
| P2 Ingest | Done | ingest |
| P3 Graph | Done | graph |
| P4 Maintenance | Done | stats, lint, export |
| P5 Open Source | In Progress | CI/CD, docs |

## Development

```bash
ruff check src/ tests/
pytest
```

## License

MIT
