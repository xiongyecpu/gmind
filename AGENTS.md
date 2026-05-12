# GMind — AI 编码代理项目指南

> 本文档面向 AI 编码代理。

---

## 项目概述

GMind 是一个面向知识工作者的开源知识库 CLI 工具，基于 PostgreSQL + pgvector 构建，通过向量搜索和知识图谱将碎片化的笔记、阅读材料与思考串联成可查询、可探索的知识网络。

**当前状态**：P8 完成（v3）。已有完整的 CLI、HTTP API、Chrome Extension、macOS 菜单栏应用（SwiftUI），以及内置 LLM 引擎。

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
│   └── llm/                # 新增：LLM 引擎
│       ├── engine.py       # Provider 抽象 (Ollama/OpenAI)
│       ├── cache.py        # SQLite 响应缓存
│       ├── extract.py      # 实体/关系提取
│       └── reason.py       # 检索+推理问答
├── gmind-macos/            # 新增：SwiftUI 菜单栏应用
│   ├── GMind/              # Swift 源码
│   ├── Info.plist
│   └── project.yml         # XcodeGen 配置
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
| macOS App | SwiftUI, AppKit NSStatusBar |
| 打包 | uv + pyproject.toml |
| 测试 | pytest |

---

## CLI 命令

```bash
gmind init --node <name>              # 初始化
gmind add "content" [--auto-extract]  # 添加笔记（可选 LLM 自动提取）
gmind search "keyword" --json         # 向量搜索
gmind query "question"                # 纯检索（无 LLM）
gmind ask "question"                  # LLM 增强问答（v3 新增）
gmind enrich <slug>                   # LLM 知识增强（v3 新增）
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
- `confidence FLOAT`
- `source` (manual/llm_extract)

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
ruff check src/ tests/

# 运行测试
pytest

# 本地运行
source .venv/bin/activate
gmind serve --port 8765

# macOS App
cd gmind-macos
xcodegen generate
open GMind.xcodeproj
```

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

---

## 代码风格

- ruff: line-length=100, target=py312
- 类型注解：全部使用 (from __future__ import annotations)
- 模块命名：小写下划线
- 数据库操作：使用参数化查询 (`%s` + tuple)

---

## License

MIT
