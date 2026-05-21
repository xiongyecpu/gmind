# gmind

gmind is a proactive personal AI knowledge base.

The product shape is now:

```text
macOS menu bar app for humans
CLI for agents and automation
```

Humans ask questions in the App. Agents use the CLI to add material, ask the
knowledge base, check readiness, and diagnose setup.

gmind 是一个主动吸取知识的个人 AI 知识库。

现在的产品形态是：

```text
macOS 菜单栏 App 给普通人使用
CLI 给智能体和自动化调用
```

人类在 App 里提问；智能体用 CLI 添加资料、提问、检查状态和诊断环境。

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

The current implementation includes a macOS menu bar app and a bundled CLI.

当前版本已经包含 macOS 菜单栏 App 和随 App 打包的 CLI。

Implemented:

```text
macOS menu bar app
bundled CLI inside the .app
automatic CLI registration at ~/.local/bin/gmind
config initialization
Postgres + pgvector schema initialization
database readiness checks
add text files through one product command
ask existing knowledge through vector search + LLM synthesis
debug namespace for pipeline/database inspection
```

已实现：

```text
macOS 菜单栏 App
App 内置 CLI
自动注册 ~/.local/bin/gmind
配置初始化
Postgres + pgvector schema 初始化
数据库可用性检查
通过一个产品命令添加文本资料
通过向量搜索 + LLM 综合回答询问已有知识
debug 命名空间用于管线和数据库调试
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

The CLI is intentionally small at the product layer:

```bash
gmind setup
gmind status --config gmind.toml
gmind add text --title "Project note" --file note.txt --config gmind.toml
gmind add markdown --title "Meeting notes" --file meeting.md --config gmind.toml
gmind add text --title "Quick note" --text "Project A signed the contract." --config gmind.toml
gmind ask "项目 A 当前进展如何？" --config gmind.toml
gmind doctor --config gmind.toml
```

产品层 CLI 故意保持很小：

```bash
gmind setup
gmind status --config gmind.toml
gmind add text --title "测试资料" --file note.txt --config gmind.toml
gmind add markdown --title "会议纪要" --file meeting.md --config gmind.toml
gmind add text --title "快速记录" --text "项目 A 已签署合同。" --config gmind.toml
gmind ask "项目 A 当前进展如何？" --config gmind.toml
gmind doctor --config gmind.toml
```

During local development, prefix commands with `uv run`:

```bash
uv sync --dev
uv run gmind setup
uv run gmind status --config gmind.toml
uv run gmind add text --title "Project note" --file note.txt --config gmind.toml
uv run gmind add markdown --title "Meeting notes" --file meeting.md --config gmind.toml
uv run gmind add text --title "Quick note" --text "Project A signed the contract." --config gmind.toml
uv run gmind ask "项目 A 当前进展如何？" --config gmind.toml
```

`gmind add text` and `gmind add markdown` both accept exactly one input source:

```bash
gmind add text --title "From file" --file note.txt --config gmind.toml
gmind add text --title "Direct text" --text "项目 A 已签署合同。" --config gmind.toml
echo "项目 A 收到首付款。" | gmind add text --title "From stdin" --stdin --config gmind.toml
gmind add markdown --title "Markdown file" --file note.md --config gmind.toml
gmind add markdown --title "Markdown text" --text "## 项目 A\n\n已签署合同。" --config gmind.toml
```

`gmind ask` embeds the question, searches similar source chunks with pgvector,
and asks the configured LLM to synthesize an answer from those evidence chunks.
Use `--json` when an agent or the App needs structured output:

```bash
gmind ask "项目 A 当前进展如何？" --json --config gmind.toml
```

Debug commands remain available for development and operator inspection, but
they are not the product surface:

```bash
uv run gmind debug db check --config gmind.toml
uv run gmind debug entities --config gmind.toml
uv run gmind debug entity show "项目 A" --config gmind.toml
uv run gmind debug pipeline embed-source 1 --config gmind.toml
uv run gmind debug pipeline extract-llm 1 --config gmind.toml
uv run gmind debug logs --config gmind.toml
```

The old low-level commands such as `entities`, `claims`, `events`, `relations`,
`ingest`, `embed`, and `extract` are kept for compatibility, but they are hidden
from the main help output. New agent code should use `add`, `ask`, `status`, and
`debug`.

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
