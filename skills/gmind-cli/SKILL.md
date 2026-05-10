---
name: gmind-cli
description: "Interact with the GMind knowledge base via CLI. Use when the user asks to: (1) record a note or save knowledge, (2) query or search their personal knowledge base, (3) add an entity, concept, or source, (4) ask questions that require semantic search over stored notes, or (5) any task involving 'my knowledge base' or 'my notes'."
---

# GMind CLI Skill

GMind is a personal knowledge base backed by PostgreSQL + pgvector. It stores notes, performs vector search, and manages multi-node sync. **It does NOT call LLMs** -- reasoning and synthesis are the agent's job.

## Agent vs GMind: Responsibility Split

| Task | Who Does It |
|------|-------------|
| Store, retrieve, sync, export | **GMind CLI** |
| Generate embeddings | **GMind CLI** (calls embedding API) |
| Reason, summarize, answer | **You (the agent)** |
| Merge conflict judgment | **You (the agent)** |
| Extract title/summary from files | **You (the agent)** or simple heuristics |

## Binary Location

`~/.local/bin/gmind`

## Core Commands

### Add a note

```bash
gmind add "<content>" [--type <type>] [--title <title>] [--slug <slug>] [--source <source>]
```

- `--type`: `note` (default), `source`, `concept`, `project`, `person`, `company`, `product`, `synthesis`, `query`, `entity`
- `--title`: Display title. Defaults to first 50 chars of content.
- `--slug`: URL-safe identifier. Auto-generated from title pinyin if omitted.
- `--source`: Mandatory for agent writes. Format: `agent-name:session-id`
- `--on-duplicate`: `[a]ppend` / `[o]verwrite` / `[i]gnore`. Use in non-interactive mode.

**Type system — Three-layer model**:

GMind types are NOT just labels. They define the **role** of a page in the knowledge graph:

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

### Stats

```bash
gmind stats
```

- Pages total / by type / embedding coverage
- Orphan pages / graph edges count
- Recent 7-day writes / last sync / pending merges

### Ingest (batch import)

```bash
gmind ingest <file-or-dir> [--recursive] [--source <ref>]
```

- Supports `.md`, `.txt`, `.pdf`
- PDF text extraction via pdfplumber
- Uses simple heuristics for title extraction (first line / filename)
- **Does NOT call LLM** for extraction
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

### Lint

```bash
gmind lint
```

- Checks: orphan pages, broken [[links]], merge_review pending, missing embeddings

### Export

```bash
gmind export <output-dir>
```

- Exports all pages to `.md` files with YAML frontmatter

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

## Implemented Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize config and database |
| `add` | Add notes with auto-embedding and dedup |
| `search` | Vector similarity search, JSON output (agent-friendly) |
| `query` | Semantic search, formatted output (human-friendly) |
| `stats` | Knowledge base dashboard |
| `ingest` | Batch import .md/.txt/.pdf |
| `sync` | Publish drafts, detect conflicts |
| `graph` | Knowledge graph: links, orphans, hubs |
| `lint` | Health check |
| `export` | Export to markdown |
| `merge` | Manual conflict resolution with version history |

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

## Prohibited Actions

- ❌ Do not call `gmind sync` unless explicitly asked
- ❌ Do not delete or overwrite existing pages without user confirmation
- ❌ Do not ingest more than 10 files in one batch without confirmation
- ❌ Do not call `gmind query` or `gmind search` repeatedly for the same question

## Agent Design Principles

- **You ARE the LLM**: GMind does not call LLMs. Use `gmind search --json` to retrieve data, then synthesize answers yourself.
- **NEVER echo raw gmind output**: Whether JSON from `search` or formatted text from `query`, always read, understand, and rephrase with your own reasoning before responding to the user.
- **You ARE the merge engine**: When `gmind sync` produces `merge_review` pages, read both versions via search, merge them using your own judgment, then write back.
- **GMind is your memory, not your brain**: It stores and retrieves. Reasoning, summarization, and merging are your job.

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
