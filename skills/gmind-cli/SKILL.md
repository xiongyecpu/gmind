---
name: gmind-cli
description: "Interact with the GMind knowledge base via CLI. Use when the user asks to: (1) record a note or save knowledge, (2) query or search their personal knowledge base, (3) add an entity, concept, or source, (4) ask questions that require semantic search over stored notes, or (5) any task involving 'my knowledge base' or 'my notes'."
---

# GMind CLI Skill

GMind is a personal knowledge base backed by PostgreSQL + pgvector. It stores notes, performs vector search, manages multi-node sync, and (v3+) has built-in LLM capabilities for knowledge extraction and reasoning.

## Agent vs GMind: Responsibility Split

| Task | Who Does It |
|------|-------------|
| Store, retrieve, sync, export | **GMind CLI** |
| Generate embeddings | **GMind CLI** (calls embedding API) |
| Vector search | **GMind CLI** |
| LLM reasoning / Q&A | **GMind CLI** (`gmind ask`) — v3 |
| Entity/relation extraction | **GMind CLI** (`gmind enrich`, `--auto-extract`) — v3 |
| Deep synthesis & judgment | **You (the agent)** |
| Merge conflict resolution | **You (the agent)** or `gmind merge` |

## Binary Location

`~/.local/bin/gmind`

## Core Commands

### Add a note

```bash
gmind add "<content>" [--type <type>] [--title <title>] [--slug <slug>] [--source <source>] [--auto-extract]
```

- `--type`: `note` (default), `source`, `concept`, `project`, `person`, `company`, `product`, `synthesis`, `query`, `entity`, `capture`
- `--title`: Display title. Defaults to first 50 chars of content.
- `--slug`: URL-safe identifier. Auto-generated from title pinyin if omitted.
- `--source`: Mandatory for agent writes. Format: `agent-name:session-id`
- `--on-duplicate`: `[a]ppend` / `[o]verwrite` / `[i]gnore`. Use in non-interactive mode.
- `--auto-extract` / `-x`: **v3** — CLI opt-in. Auto-extract entities, relations, summary, and tags via LLM after saving.

**Type system — Three-layer model**:

```
L0 原始素材 (Raw input)          L1 提炼实体 (Entity档案)        L2 整合输出 (Output)
─────────────────────           ─────────────────────          ─────────────────
source   ───┐                     person   (人物档案)  ───→    synthesis (综合总结)
note    ────┼──→  提炼、聚合  →   company  (公司档案)  ───→    project   (项目跟踪)
capture ────┘                     product  (产品档案)
                                  concept  (概念档案)
```

| Layer | Type | Role | Example |
|-------|------|------|---------|
| **L0 素材** | `source` | 人工收集的外部资料（书、文章、网页、PDF） | "Tesla Q3 财报原文" |
| **L0 素材** | `note` | 人的随手记录、想法、草稿 | "读财报的一些思考" |
| **L0 素材** | `capture` | 自动工具采集的原始转录（会话、日志、系统输出） | "hermes-session-20260510" |
| **L1 实体** | `person` | 人物档案，聚合所有关于这个人的 source | "Elon Musk" ← 被多个 source 链接 |
| **L1 实体** | `company` | 公司档案，聚合所有关于这家公司的 source | "Tesla" ← 被多个 source 链接 |
| **L1 实体** | `product` | 产品/工具档案 | "PostgreSQL" |
| **L1 实体** | `concept` | 概念/知识点档案 | "向量数据库" |
| **L2 输出** | `synthesis` | 综合多篇素材的总结 | "2024 AI 年度回顾" |
| **L2 输出** | `project` | 正在进行的项目/工作跟踪 | "GMind 开发" |
| — | `query` | 查询/问答记录 | "为什么 PG 比 MySQL 好" |
| — | `entity` | 未分类实体（legacy fallback） | — |

**Critical**: L1 entity pages are **档案中心** — they are linked TO by multiple L0 source pages. A `person` page like `[[elon-musk]]` should contain a summary of who he is and list key facts, while individual sources (articles, tweets) about him link to `[[elon-musk]]`.

**Deduplication**: Similarity > 0.92 triggers merge prompt. In non-interactive mode, default is append.

### Search (primary retrieval command)

```bash
gmind search "<keyword>" [--top-k <n>] [--json]
```

- Pure vector semantic search, **no LLM call**
- `--json`: JSON output for agent consumption
- Default top-k is 5
- Returns: slug, title, content, type, similarity

**Critical rule**: After receiving search results from gmind, **do NOT dump raw JSON or text directly to the user**. You must first read and understand the retrieved content, then use your own reasoning to synthesize a coherent, human-friendly answer. Cite sources using `[[slug]]` format.

### Query (retrieval only)

```bash
gmind query "<question>" [--top-k <n>]
```

- Same as `search` but with human-readable formatted output
- **Does NOT call LLM**. Just shows retrieved chunks.
- **Critical rule**: Even with formatted output, do NOT echo gmind's raw results directly to the user. Read, understand, and rephrase with your own reasoning.
- For agent use, prefer `search --json` (saves tokens).

### Ask — LLM-enhanced Q&A (v3)

```bash
gmind ask "<question>" [--top-k <n>] [--temperature <t>]
```

- Retrieves relevant pages via vector search, then uses LLM to reason and answer
- Answer includes `[[slug]]` citations
- Sources are listed with relevance scores
- **Use this when the user asks a question that requires synthesis across multiple notes**

### Enrich — LLM knowledge extraction (v3)

```bash
gmind enrich <slug>
```

- Analyzes an existing page with LLM
- Auto-extracts: entities, relations, summary, tags
- Creates entity pages (type=`entity`) for extracted entities
- Creates entity pages and graph edges (`link_type=mentions` or relation type). The current DB schema has `created_by` and `evidence`, not an `edges.source` column.
- Sets `llm_enriched=true` on the page

### Capture — Agent session history (v3)

```bash
gmind capture <agent> [--latest] [--all] [--session <id>] [--all-agents]
```

- Imports agent conversation history into GMind as `capture` type pages
- Supported agents: `hermes`, `claude`, `codex`, `kimi`, `openclaw`
- `--latest`: Import the most recent session only
- `--all`: Import all sessions for the agent
- `--session <id>`: Import a specific session by ID
- `--all-agents`: Import latest session from all supported agents

Session files are read from standard locations:
- `hermes`: `~/.hermes/sessions/`
- `claude`: `~/.claude/projects/`
- `codex`: `~/.codex/archived_sessions/`
- `kimi`: `~/.kimi/sessions/`
- `openclaw`: `~/.openclaw/agents/main/sessions/`

### Stats

```bash
gmind stats
```

- Pages total / by type / embedding coverage
- Orphan pages / graph edges count
- Recent 7-day writes / last sync / pending merges
- The HTTP `/stats` endpoint also exposes `llm_enriched`; CLI `gmind stats` currently focuses on core knowledge base health.

### Ingest (batch import)

```bash
gmind ingest <file-or-dir> [--recursive] [--source <ref>]
```

- Supports `.md`, `.txt`, `.pdf`
- Taotie can discover and preview-classify `.docx`, but normal `gmind ingest` does not yet extract `.docx` content.
- PDF text extraction via pdfplumber
- Uses simple heuristics for title extraction (first line / filename)
- **Does NOT call LLM** for extraction (use `--auto-extract` on individual adds instead)
- Batch-safe: auto-append on duplicate

### Sync

```bash
gmind sync [--dry-run]
```

- Scans local `draft` pages and promotes them to `published`
- Auto-detects conflicts (same slug, different checksum)
- Conflicts are marked `merge_review`; snapshots saved to `page_history`
- `--dry-run`: previews without touching data
- **Agent workflow**: After `gmind sync`, check for `merge_review` pages. Use `gmind search` to read both versions, then use your own reasoning to merge and write the result back via `gmind add`.

### Graph

```bash
gmind graph <slug> [--depth <n>]
gmind graph --orphans
gmind graph --hubs
gmind graph --rebuild
```

- Parses `[[slug]]` and `[[slug|title]]` syntax in page content
- `--rebuild` scans entire database and populates edges table
- v3: Also shows `llm_extract` edges (from `gmind enrich`)

### Lint

```bash
gmind lint
```

- Checks: orphan pages, broken [[links]], merge_review pending, missing embeddings
- v3: Also checks pages not yet LLM-enriched

### Export

```bash
gmind export <output-dir>
```

- Exports all pages to `.md` files with YAML frontmatter
- v3: Includes `summary`, `tags`, `entities` in frontmatter

### Merge

```bash
gmind merge <slug> [--list] [--pick <version>] [--edit]
```

- Manual conflict resolution with version history

### Init

```bash
gmind init [--node <name>]
```

- Initialize gmind configuration and database connection
- Only asks for: database URL, embedding API key, embedding model
- v3: Also configure `[llm]` section for LLM provider (Ollama/OpenAI)

## Implemented Commands

| Command | Description | v3 |
|---------|-------------|-----|
| `init` | Initialize config and database | |
| `add` | Add notes with auto-embedding and dedup | `+ --auto-extract` |
| `search` | Vector similarity search, JSON output (agent-friendly) | |
| `query` | Semantic search, formatted output (human-friendly) | |
| `ask` | LLM-enhanced Q&A with citations | ✅ |
| `enrich` | Auto-extract entities, relations, summary, tags | ✅ |
| `capture` | Import agent session histories | ✅ |
| `stats` | Knowledge base overview | |
| `ingest` | Batch import .md/.txt/.pdf | |
| `sync` | Publish drafts, detect conflicts | |
| `graph` | Knowledge graph: links, orphans, hubs | |
| `lint` | Health check | |
| `export` | Export to markdown | |
| `merge` | Manual conflict resolution with version history | |

## Writing Rules

1. **Always include `--source`** for agent-initiated writes
2. **Reference existing pages** with `[[slug]]` syntax (English slug, not title)
3. **Follow the three-layer flow**:
   - External material → `source` (record what you read)
   - Auto-captured content → `capture` (session logs, tool output, API dumps)
   - Extract entities from source → `person`/`company`/`product`/`concept` (create/update档案)
   - Source pages should LINK TO entity pages: "Tesla's CEO is [[elon-musk]]"
   - Synthesize multiple sources → `synthesis` or `project`
4. **Entity pages are档案 centers** — keep them updated with latest facts from new sources
5. **Prefer append over overwrite** when deduplication fires
6. **Use `--auto-extract`** when adding substantial notes from CLI — it attempts to create entity pages and edges when LLM is configured

## Prohibited Actions

- ❌ Do not call `gmind sync` unless explicitly asked
- ❌ Do not delete or overwrite existing pages without user confirmation
- ❌ Do not ingest more than 10 files in one batch without confirmation
- ❌ Do not call `gmind query` or `gmind search` repeatedly for the same question

## Agent Design Principles

- **GMind is your memory**: Use `gmind search --json` to retrieve data, `gmind ask` for LLM-synthesized answers.
- **NEVER echo raw gmind output**: Whether JSON from `search` or formatted text from `query`, always read, understand, and rephrase with your own reasoning before responding to the user.
- **You ARE the merge engine**: When `gmind sync` produces `merge_review` pages, read both versions via search, merge them using your own judgment, then write back.
- **Capture your sessions**: Use `gmind capture <agent> --latest` to persist this conversation into your knowledge base.

## CRITICAL: Never dump raw results to the user

After calling `gmind search --json` or `gmind query`, you have raw retrieval data. **Your job is to read it and compose a natural, synthesized answer for the user.**

❌ **Wrong**: Pasting the JSON array, CLI output, or numbered similarity list directly into the response. The user did not ask for database dump.

✅ **Right**: Parse the results internally, synthesize the answer in your own words, cite sources with `[[slug]]` where relevant. Present it as a normal conversational answer.

Think of it as: gmind is your memory retrieval, not the user's. You query your memory, then answer the question. The user should never see the underlying SQL/JSON any more than they should see your neural activations.

## Roadmap Status

| Phase | Status | Commands |
|-------|--------|----------|
| P0 Core | Done | init, add, search, query |
| P1 Sync | Done | sync, merge |
| P2 Ingest | Done | ingest |
| P3 Graph | Done | graph |
| P4 Maintenance | Done | stats, lint, export |
| P5 Open Source | Done | docs, CI |
| P6 Browser | Done | gmind serve, Chrome extension |
| P7 LLM Engine | Done | ask, enrich, capture, auto-extract |
| P8 macOS App | Done | Menu bar, Quick Add, Ask AI, model config |
| P9 Taotie | Done | Scan, classification, ingest queue, history, watcher config |
