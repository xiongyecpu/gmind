---
name: gmind-cli
description: "Interact with the GMind knowledge base via CLI. Use when the user asks to: (1) record a note or save knowledge, (2) query or search their personal knowledge base, (3) add an entity, concept, or source, (4) ask questions that require semantic search over stored notes, or (5) any task involving 'my knowledge base' or 'my notes'."
---

# GMind CLI Skill

GMind is a personal knowledge base backed by PostgreSQL + pgvector. It supports semantic search, automatic deduplication, and multi-node sync.

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

### Search (preferred for agents)

```bash
gmind search "<keyword>" [--top-k <n>] [--json]
```

- Pure vector semantic search, **no LLM call**
- `--json`: JSON output for agent consumption (saves tokens)
- Default top-k is 5
- Returns: slug, title, content, type, similarity

**Agent workflow**: Use `gmind search --json` to retrieve relevant notes, then use your own reasoning to answer or synthesize. Do NOT use `gmind query` (it calls an external LLM and wastes tokens).

### Sync drafts to published

```bash
gmind sync [--dry-run]
```

- Scans local `draft` pages and promotes them to `published`
- Auto-detects conflicts (same slug, different checksum)
- Conflicts are marked `merge_review`; snapshots saved to `page_history`
- **Agent workflow**: After `gmind sync`, check for `merge_review` pages. Use `gmind search` to read both versions, then use your own reasoning to merge and write the result back via `gmind add`.
- `--dry-run`: previews without touching data

### Manually resolve conflicts

```bash
gmind merge <slug> --list                    # show history versions
gmind merge <slug> --pick <version>          # revert to version
gmind merge <slug> --version <version>       # same as --pick
gmind merge <slug> --edit                    # open $EDITOR
```

## Writing Rules

1. **Always include `--source`** for agent-initiated writes
2. **Reference existing pages** with `[[slug]]` syntax (English slug, not title)
3. **Use `--type entity`** for named entities (people, orgs, products)
4. **Prefer append over overwrite** when deduplication fires

## Agent Design Principles

- **You ARE the LLM**: GMind does not call LLMs. Use `gmind search --json` to retrieve data, then synthesize answers yourself.
- **You ARE the merge engine**: When `gmind sync` produces `merge_review` pages, read both versions via search, merge them using your own judgment, then write back.
- **GMind is your memory, not your brain**: It stores and retrieves. Reasoning, summarization, and merging are your job.

## Roadmap Status

| Phase | Status | Commands |
|-------|--------|----------|
| P0 Core | ✅ Done | init, add, search, query |
| P1 Sync | ✅ Done | sync, merge |
| P2 Ingest | 📋 Todo | ingest (files/PDF) |
| P3 Graph | 📋 Todo | graph, link extraction |
| P4 Maintenance | 📋 Todo | lint, stats, export |
