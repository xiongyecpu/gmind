---
name: gmind-cli
description: "Interact with the GMind knowledge base via CLI. Use when the user asks to: (1) record a note or save knowledge, (2) query or search their personal knowledge base, (3) add an entity, concept, or source, (4) ask questions that require semantic search over stored notes, or (5) any task involving 'my knowledge base' or 'my notes'."
---

# GMind CLI Skill

GMind is a personal knowledge base backed by PostgreSQL + pgvector. It supports semantic search, automatic deduplication, and knowledge graph (planned).

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

### Query the knowledge base

```bash
gmind query "<question>" [--top-k <n>]
```

- Performs vector semantic search + LLM summarization
- Default top-k is 5
- Returns answer with cited sources in `[[slug]]` format

### Sync drafts to published

```bash
gmind sync [--dry-run]
```

- Scans local `draft` pages and promotes them to `published`
- Auto-detects conflicts (same slug, different checksum)
- Conflicts trigger LLM auto-merge; fallback to `merge_review` if merge fails
- `--dry-run` previews without touching data

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

## Prohibited Actions

- ❌ Do not call `gmind sync` unless explicitly asked
- ❌ Do not delete or overwrite existing pages without user confirmation
- ❌ Do not ingest more than 10 files in one batch without confirmation
- ❌ Do not call `gmind query` repeatedly for the same question

## P0 Availability Note

As of current version, only `init`, `add`, and `query` are implemented.
`search`, `graph`, `sync`, `ingest`, `stats`, and `export` are on the roadmap (P1–P5).
