---
name: gmind-cli
description: "Interact with the GMind knowledge base via CLI. Use when the user asks to: (1) record a note or save knowledge, (2) query or search their personal knowledge base, (3) add an entity, concept, or source, (4) ask questions that require semantic search over stored notes, or (5) any task involving 'my knowledge base' or 'my notes'."
---

# GMind CLI Skill

GMind is a personal knowledge base backed by PostgreSQL + pgvector. It supports semantic search, automatic deduplication, and multi-node sync.

## Binary Location

`~/.local/bin/gmind` — linked to the project venv. If not in PATH, use full path.

## Core Commands

### Add a note

```bash
gmind add "<content>" [--type <type>] [--title <title>] [--slug <slug>] [--source <source>]
```

- `--type`: `note` (default), `entity`, `concept`, `source`, `query`, `synthesis`
- `--title`: Display title. Defaults to first 50 chars of content.
- `--slug`: URL-safe identifier. Auto-generated from title pinyin if omitted.
- `--source`: Mandatory for agent writes. Format: `agent-name:session-id`
- `--on-duplicate`: `[a]ppend` / `[o]verwrite` / `[i]gnore`. Use in non-interactive mode.

**Entity rule**: When adding people, companies, or named entities, always use `--type entity`.

**Deduplication**: Similarity > 0.92 triggers merge prompt. In non-interactive mode, default is append.

**File import**: Use `$(cat '/path/to/file.md')` to pipe file contents into add.

### Search (preferred for agents)

```bash
gmind search "<keyword>" [--top-k <n>] [--json]
```

- Pure vector semantic search, **no LLM call**
- `--json`: JSON output for agent consumption (saves tokens)
- Default top-k is 5
- Returns: slug, title, content, type, similarity

**Agent workflow**: Use `gmind search --json` to retrieve relevant notes, then use your own reasoning to answer or synthesize. Do NOT use `gmind query` (it calls an external LLM and wastes tokens).

### Query (semantic search + LLM summary)

```bash
gmind query "<question>" [--top-k <n>]
```

- Performs vector semantic search + LLM summarization
- Requires LLM API key configured
- Default top-k is 5
- Returns answer with cited sources in `[[slug]]` format

### Stats (knowledge base overview)

```bash
gmind stats
```

- Pages total / by type / embedding coverage
- Orphan pages (no edges) / graph edges count
- Recent 7-day writes / last sync / pending merges

### Ingest (batch import)

```bash
gmind ingest <file-or-dir> [--recursive] [--source <ref>]
```

- Supports `.md`, `.txt`, `.pdf`
- PDF text extraction via pdfplumber
- LLM extracts title, summary, page_type automatically
- Falls back to heuristics if no LLM key configured
- Batch-safe: auto-append on duplicate

### Sync (publish drafts)

```bash
gmind sync [--dry-run] [--auto-merge]
```

- Scans local `draft` pages and promotes them to `published`
- Auto-detects conflicts (same slug, different checksum)
- Conflicts are marked `merge_review`; snapshots saved to `page_history`
- `--dry-run`: previews without touching data
- `--auto-merge`: uses LLM to auto-merge conflicts (requires LLM key)
- **Agent workflow**: After `gmind sync`, check for `merge_review` pages. Use `gmind search` to read both versions, then use your own reasoning to merge and write the result back via `gmind add`.

### Merge (resolve conflicts)

```bash
gmind merge <slug> [--list] [--pick <version>] [--edit]
```

- `--list`: Show history versions for a page
- `--pick <version>`: Revert to a specific version
- `--edit`: Open $EDITOR to manually resolve

### Init

```bash
gmind init [--node <name>]
```

- Initialize gmind configuration and database connection

## Implemented Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize config and database |
| `add` | Add notes with auto-embedding and dedup |
| `search` | Vector similarity search, JSON output (agent-friendly) |
| `query` | Semantic search + LLM summary (human-friendly) |
| `sync` | Publish drafts, detect conflicts |
| `merge` | Manual conflict resolution with version history |

## Writing Rules

1. **Always include `--source`** for agent-initiated writes
2. **Reference existing pages** with `[[slug]]` syntax (English slug, not title)
3. **Use `--type entity`** for named entities (people, orgs, products)
4. **Prefer append over overwrite** when deduplication fires

## Prohibited Actions

- ❌ Do not call `gmind sync` unless explicitly asked
- ❌ Do not delete or overwrite existing pages without user confirmation
- ❌ Do not ingest more than 10 files in one batch without confirmation
- ❌ Do not call `gmind query` repeatedly for the same question

## Agent Design Principles

- **You ARE the LLM**: GMind does not call LLMs. Use `gmind search --json` to retrieve data, then synthesize answers yourself.
- **You ARE the merge engine**: When `gmind sync` produces `merge_review` pages, read both versions via search, merge them using your own judgment, then write back.
- **GMind is your memory, not your brain**: It stores and retrieves. Reasoning, summarization, and merging are your job.

## Roadmap Status

| Phase | Status | Commands |
|-------|--------|----------|
| P0 Core | ✅ Done | init, add, search, query |
| P1 Sync | ✅ Done | sync, merge |
| P2 Ingest | ✅ Done | ingest (files/PDF) |
| P4 Stats | ✅ Done | stats |
| P3 Graph | 📋 Todo | graph, link extraction |
| P4 Maintenance | 📋 Todo | lint, stats, export |
