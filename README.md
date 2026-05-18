# gmind

gmind is a proactive personal AI knowledge base.

It ingests sources, extracts entities, claims, events, relations, and tasks, then keeps knowledge current through structured queries and active follow-up work.

gmind 是一个主动吸取知识的个人 AI 知识库。

它会吸取资料，抽取实体、断言、事件、关系和任务，并通过结构化查询与主动任务持续更新理解。

## Model configuration

`gmind init` creates a `gmind.toml` configured for SiliconFlow by default.

Set your API key in the shell before running model-backed commands:

```bash
export SILICONFLOW_API_KEY="..."
```

The key should not be committed. Keep local secrets in `.env` or your shell profile.

模型配置默认使用硅基流动。运行真实向量化或 LLM 抽取前，需要设置：

```bash
export SILICONFLOW_API_KEY="..."
```

不要把真实密钥提交到仓库。

默认抽取模型：

```toml
llm_model = "Qwen/Qwen3.6-35B-A3B"
```

如果需要更快、更大上下文的低成本抽取，可以临时切到：

```toml
llm_model = "deepseek-ai/DeepSeek-V4-Flash"
```

## Current status / 当前进度

The current implementation is a working CLI-first knowledge engine prototype.

当前版本已经是一个可运行的 CLI 优先知识引擎原型。

Implemented:

```text
config initialization
Postgres + pgvector schema initialization
database readiness checks
plain text ingest
source chunk embedding
stub extraction
LLM extraction with SiliconFlow
source/entity/claim/event/relation/task/log inspection
```

已实现：

```text
配置初始化
Postgres + pgvector schema 初始化
数据库可用性检查
纯文本 ingest
source chunk 向量化
规则版抽取
硅基流动 LLM 抽取
source / entity / claim / event / relation / task / log 查询
```

Verified against remote `gmind_dev`:

```text
text file -> sources/source_chunks/logs
source_chunks -> embeddings
source_chunks -> entities/claims/events/relations/logs
entity show -> claims/events/relations readback
```

已经在远程 `gmind_dev` 验证：

```text
文本文件 -> sources/source_chunks/logs
source_chunks -> embeddings
source_chunks -> entities/claims/events/relations/logs
entity show -> claims/events/relations 读回
```

## CLI quickstart / CLI 快速开始

```bash
uv sync --dev
uv run gmind init
uv run gmind db check --config gmind.toml
uv run gmind ingest text --title "Project note" --file note.txt --config gmind.toml
uv run gmind embed source 1 --config gmind.toml
uv run gmind extract llm 1 --config gmind.toml
uv run gmind entity show "项目 A" --config gmind.toml
```

Useful inspection commands:

```bash
uv run gmind sources --config gmind.toml
uv run gmind source show 1 --config gmind.toml
uv run gmind entities --config gmind.toml
uv run gmind claims --entity "项目 A" --config gmind.toml
uv run gmind events timeline --entity "项目 A" --config gmind.toml
uv run gmind relations for claim 1 --config gmind.toml
uv run gmind tasks --config gmind.toml
uv run gmind logs --config gmind.toml
```

## Next steps / 下一步

```text
claim deduplication
entity canonicalization beyond simple names
claim conflict detection
task scheduler / worker
better extraction eval fixtures
```

```text
claim 去重
更完整的 entity 规范化
claim 冲突检测
task scheduler / worker
更系统的抽取评测样例
```
