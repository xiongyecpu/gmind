# GMind — AI 编码代理项目指南

> 本文档面向 AI 编码代理。

---

## 项目概述

GMind 是一个面向知识工作者的开源个人知识库工具，基于 PostgreSQL + pgvector 构建，通过向量搜索、轻量知识图谱和可选 LLM 增强，将碎片化的笔记、阅读材料与思考串联成可查询、可探索、可问答的知识网络。

**当前状态（以代码实现为准）**：v4 / P10 功能线正在落地，包含 CLI、HTTP API、Chrome Extension、Electron 桌面托盘/菜单栏应用、内置 LLM 引擎，以及知识雷达（Taotie）扫描与入库队列。需要注意：LLM 功能是可选增强；CLI `gmind add` 需要显式 `--auto-extract` 才会自动提取；Taotie watcher 当前是监听文件夹配置与 API/UI 管理，不是独立常驻 FSEvents 后台进程；`.docx` 当前可被扫描和预览分类，但批量入库正文提取尚未接入 `ingest.py`。

**文档权威性**：`README.md`、本文件和 `docs/GMind-Desktop-App设计文档.md` 描述当前实现；`docs/GMind-知识雷达设计文档.md` 描述 Taotie/知识雷达当前设计边界。

---

## 仓库结构

```
.
├── src/gmind/              # Python 后端核心
│   ├── cli.py              # Typer CLI 入口
│   ├── server.py           # Starlette HTTP API
│   ├── db.py               # PostgreSQL + pgvector
│   ├── config.py           # TOML 配置管理
│   ├── embed.py            # Embedding API (SiliconFlow)
│   ├── add.py              # 添加笔记
│   ├── query.py            # 纯向量检索
│   ├── search.py           # 向量搜索 (JSON/agent)
│   ├── graph.py            # 知识图谱操作
│   ├── enrich.py           # LLM 知识增强
│   ├── capture.py          # Agent 会话导入
│   ├── taotie/             # 知识雷达（Taotie 后端能力）
│   │   ├── scanner.py      # 全电脑文件扫描
│   │   ├── classifier.py   # LLM 隐私分类
│   │   ├── blacklist.py    # 黑名单管理
│   │   ├── queue.py        # 入库队列
│   │   ├── history.py      # 导入历史
│   │   └── watcher.py      # 文件夹监听配置
│   └── llm/                # LLM 引擎
│       ├── engine.py       # Provider 抽象 (Ollama/OpenAI)
│       ├── cache.py        # SQLite 响应缓存
│       ├── extract.py      # 实体/关系提取
│       └── reason.py       # 检索+推理问答
├── gmind-desktop/          # Electron 桌面托盘/菜单栏应用
│   ├── src/                # HTML/CSS/JS App UI
│   └── src/electron/       # Electron shell、tray、server/CLI 管理
├── chrome-extension/       # Chrome 插件 (Manifest V3)
├── tests/                  # pytest 测试
├── skills/                 # Agent skills (gmind-cli)
├── pyproject.toml          # uv 打包配置
└── README.md               # 项目文档
```

---

## 技术栈

| 组件 | 选型 |
|------|------|
| 后端 | Python 3.12+, Typer, Starlette, psycopg, pgvector |
| Embedding | SiliconFlow / OpenAI-compatible (BAAI/bge-m3) |
| LLM | Ollama (本地) 或 OpenAI-compatible (远程) |
| 缓存 | SQLite (LLM 响应缓存) |
| Desktop App | Electron, HTML/CSS/JS |
| 打包 | uv + pyproject.toml, Electron app bundle |
| 测试 | pytest |

---

## CLI 命令

```bash
gmind init --node <name>              # 初始化
gmind add "content"                   # 添加笔记（CLI 默认不做 LLM 提取）
gmind add "content" --auto-extract    # 添加后触发 LLM 实体/关系/标签提取
gmind search "keyword" --json         # 向量搜索
gmind query "question"                # 纯检索（无 LLM）
gmind ask "question"                  # LLM 增强问答
gmind enrich <slug> / --all           # LLM 知识增强
gmind capture hermes --latest         # 导入 Agent 会话
gmind taotie scan                     # 全电脑扫描
gmind taotie start / pause / queue    # 入库队列控制
gmind taotie watch add <folder>       # 添加监听文件夹配置
gmind sync                            # 同步
gmind graph <slug> --depth 2          # 知识图谱
gmind stats                           # 统计
gmind serve --port 8765               # HTTP 服务器
```

## HTTP API 端点

| 端点 | 说明 |
|------|------|
| POST /add | 添加笔记 |
| GET /check?source=... | 检查 URL 是否已保存 |
| GET /search?q=...&k=5 | 向量搜索 |
| POST /ask | LLM 问答 |
| POST /enrich | LLM 知识增强 |
| GET /taotie/scan | 全电脑文件扫描 |
| GET /taotie/queue | 入库队列状态 |
| POST /taotie/queue/start | 启动入库 |
| POST /taotie/queue/pause | 暂停入库 |
| POST /taotie/queue/clear | 清空队列 |
| POST /taotie/queue/select | 勾选/取消勾选队列文件 |
| POST /taotie/queue/remove | 从队列移除并加入黑名单 |
| POST /taotie/queue/add | 添加文件到队列 |
| GET /taotie/history | 导入历史 |
| GET /taotie/watcher | 监听文件夹 |
| POST /taotie/watcher/add | 添加监听文件夹配置 |
| POST /taotie/watcher/remove | 移除监听文件夹配置 |

---

## 数据库 Schema

核心表：`pages`, `page_history`, `edges`, `sync_log`

`pages` 关键列：
- `embedding vector(1024)` — 向量嵌入
- `status` (draft/published/merge_review)
- `origin_node` — 多节点标识
- `tags TEXT[]` — 标签
- `summary TEXT` — LLM 生成摘要（v3）
- `entities JSONB` — LLM 提取实体（v3）
- `llm_enriched BOOLEAN` — 是否已 LLM 增强（v3）

`edges` 关键列：
- `link_type` (related/mentions/semantic)
- `weight REAL`
- `confidence FLOAT`
- `evidence TEXT`
- `created_by TEXT`

注意：当前 schema 没有 `edges.source` 列。若要记录 `manual / llm_extract / semantic_search` 这样的来源，需要先做 schema 迁移，或改用现有 `created_by` / `evidence` 字段。

---

## 配置

`~/.gmind/config.toml`:

```toml
database_url = "postgresql://..."
node_name = "home"
embedding_api_key = "sk-..."
embedding_model = "BAAI/bge-m3"

[llm]                                   # v3 新增
provider = "ollama"                     # or "openai"

[llm.ollama]
model = "qwen2.5:7b"
base_url = "http://localhost:11434"
```

---

## 开发工作流

```bash
# 安装依赖
uv pip install -e ".[dev]"

# 检查代码
uv run ruff check src/ tests/

# 运行测试
uv run pytest

# 本地运行
source .venv/bin/activate
gmind serve --port 8765

# Desktop App
cd gmind-desktop
npm run build
npm run electron:build
```

---

## 多电脑 / 多 Agent 协作规则

本项目会在至少两台电脑上开发：家里电脑和公司电脑，也会由多个 coding agent 交替或并行参与。所有 agent 必须把 Git 当作代码事实来源，把 GMind / gbrain 当作历史记忆来源，避免靠口头记忆或本地未提交文件传递状态。

### 机器与身份

- 家里电脑统一使用节点名 `home`，公司电脑统一使用节点名 `office`。`~/.gmind/config.toml` 的 `node_name` 必须与机器身份一致。
- 每个 agent 开工时先确认三件事：当前机器、当前分支、当前任务范围。
- agent 记录知识或开发笔记时，`--source` 使用 `agent:<agent>/<node>/<branch>` 格式，例如 `agent:codex/home/codex-home-fix-enrich`。
- 不确定当前机器身份、数据库指向、远端仓库或任务归属时，先问用户，不要猜。

### 分支与工作区

- `main` 只作为稳定主线。除非用户明确要求，不直接在 `main` 上开发或提交。
- 每个任务使用独立分支，命名格式：`<agent>/<node>/<short-task>`，例如 `codex/home/docs-agent-rules`、`claude/office/server-tests`、`kimi/home/macos-taotie-ui`。
- 同一台机器上并行跑多个 agent 时，优先使用独立 clone 或 `git worktree`，不要让两个 agent 同时操作同一个 checkout。
- 一个分支只解决一个清晰任务。发现顺手可修的问题，先记录，除非它阻塞当前任务。
- 切换电脑继续干活前，必须先把上一台电脑的改动提交或明确说明仍是未提交草稿；不要依赖“另一台电脑里有个没提交版本”。

### 开工前检查

每个 agent 开工前必须做：

```bash
git status --short
git branch --show-current
git log --oneline -5
```

- 如果工作区有未提交改动，先判断是否是当前任务相关。不是自己做的改动，不要 revert、覆盖或格式化。
- 如果需要基于远端最新状态继续开发，先执行非破坏性的 fetch / pull；遇到冲突或权限问题时问用户。
- 需要历史决策、旧项目线索、过往会话时，优先用可用的 `gbrain query` 做语义检索，再用关键词搜索补查。

### 任务所有权

- 开始实质修改前，先在自己的工作说明里明确“本次负责的文件/模块范围”。
- 多 agent 并行时，文件范围必须尽量互斥。例如一个 agent 负责 `src/gmind/llm/`，另一个负责 `gmind-desktop/src/electron/`。
- 如果必须改别人正在改的文件，先停下来问用户，或在回复里明确说明冲突风险。
- 数据库 schema、配置格式、CLI 参数、HTTP API 返回结构属于高影响面变更，不能静默改；必须同步更新 README、AGENTS、skill 文档和测试。

### 提交与交接

- 每次完成一个小闭环后，优先形成小而清晰的 commit。commit message 用英文 Conventional Commit 风格，正文可中英混合。
- 交接给用户或另一个 agent 时，必须说明：分支、改动文件、测试结果、未完成事项、需要注意的风险。
- 推荐交接模板：

```markdown
Agent:
Node:
Branch:
Scope:
Changed:
Tests:
Open questions:
Next step:
```

- 如果用户要求发 PR，PR 描述必须包含测试结果和迁移/配置影响；没有跑的测试要明说。

### 同步与数据安全

- `gmind sync` 会改变知识库页面状态。agent 不主动执行，除非用户明确要求。
- `gmind taotie scan` 可以运行；批量 ingest、启动大规模队列、导入聊天记录或扫描敏感目录前必须先问用户。
- 不提交任何真实密钥、数据库 URL、API Key、个人隐私文件或 `~/.gmind/` 本地状态。
- 涉及删除、覆盖、重置、清空队列、数据库迁移回滚等不可逆操作，必须先问用户。

### 什么时候必须问用户

- 当前实现和设计文档冲突，且无法从源码判断产品意图。
- 需要在“家里电脑状态”和“公司电脑状态”之间选择哪个为准。
- 需要决定是否兼容旧数据、是否迁移线上数据库、是否改变公开 CLI/API 行为。
- 发现用户或其他 agent 的未提交改动阻塞当前任务。
- 任务范围变大，可能从“修一个点”变成“重构一片”。

---

## LLM 模块架构

```
src/gmind/llm/
├── engine.py       # LLMEngine 统一入口，Provider 协议
│   ├── OllamaProvider    # 本地 Ollama
│   └── OpenAIProvider    # OpenAI / SiliconFlow / DeepSeek
├── cache.py        # SQLite 缓存（7 天 TTL）
├── extract.py      # 实体/关系/摘要/标签提取
└── reason.py       # retrieve → build context → LLM answer
```

新增 LLM 功能时：
1. 在 `llm/` 下添加新模块
2. 在 `server.py` 添加端点
3. 在 `cli.py` 添加命令
4. 在 `enrich.py` 集成到知识增强流程

新增 Taotie 功能时：
1. 在 `taotie/` 下添加新模块
2. 在 `server.py` 添加 `/taotie/*` 端点
3. 在 `cli.py` 的 `taotie_app` 下添加命令
4. 在 Electron 桌面端的知识雷达界面添加 UI

---

## 代码风格

- ruff: line-length=100, target=py312
- 类型注解：全部使用 (from __future__ import annotations)
- 模块命名：小写下划线
- 数据库操作：使用参数化查询 (`%s` + tuple)

---

## License

MIT
