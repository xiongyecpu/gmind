# Agent 状态

## 当前目标

把 gmind 做成面向普通人的 macOS 菜单栏 App；当前正在设计和实现核心 solo 模式。

## 当前假设

- App 面向普通人；CLI 仍作为 agent、脚本和 App 的执行层。
- 密钥只保存在本地。不要提交 `gmind.toml`、API key、密码或私有数据库 URL。
- solo 模式是 App 的持续吸取知识能力；CLI 不暴露 `gmind solo ...` 顶层命令。
- CLI 只提供执行原语：`gmind add text/markdown --file ... --solo`，表示本次 add 先由大模型判断文件是否值得入库。

## 最近完成

- 文件导入路径已可追踪：`gmind add text/markdown --file` 和旧 `ingest text --file` 会把规范化文件路径写入 `sources.metadata_json.source_path`，同时写入对应 `logs.metadata_json.source_path`。
- 已移除 CLI 顶层 `gmind solo scan`；这个方向不符合产品边界。
- 已新增 `gmind add text/markdown --file ... --solo`：先调用 LLM 判断文件是否应入库；模型拒绝时返回 `skipped=true`，不执行 ingest/embed/extract；模型接受时继续走现有 add 管线。
- `--solo` 当前只支持 `--file`，不支持 `--text` / `--stdin`，因为它表达的是“添加这个文件时先判断是否入库”。
- 已用 fake LLM 实跑 skip 路径：`env GMIND_LLM_PROVIDER=fake uv run --no-cache gmind add text --title skip-demo --file /private/tmp/gmind-solo-skip.txt --solo --json --config gmind.toml`，返回 `skipped=true`。
- solo 判断留痕已完成：每次 `add --solo` 判断都会写 `logs`，允许为 `solo_add_allowed`，拒绝为 `solo_add_rejected`，metadata 包含 `source_path`、`should_ingest`、`reason`、`confidence`。已实跑 fake LLM 拒绝路径，`debug logs` 出现 `solo_add_rejected`。
- App 设置页已新增 solo 开关，不展示等级；配置只保存 `[solo] enabled = true/false`。界面说明默认关注 `~/Downloads`，但尚未实现后台持续扫描。
- `gmind add text/markdown` 现在可以省略 `--title`；省略时会由 LLM 根据路径和正文片段生成标题。显式传 `--title` 时不额外推理标题。已实跑 fake LLM：`add text --text ... --json --skip-embed --skip-extract` 成功。
- 默认配置解析已简化：不传 `--config` 时会自动用 `GMIND_CONFIG`、当前目录向上最近的 `gmind.toml`，否则回退到 `~/.gmind/gmind.toml`。已验证 `uv run gmind status --json` 不带 `--config` 可跑通。
- 发现真实 `add markdown --file ... --solo --json` 体验问题：JSON 只在完整 add/embed/extract 后输出，用户会误以为“啥也没有”。已新增 `--dry-run`，用于只返回 solo 判断并跳过入库/embed/extract；dry-run 判断日志会带 `metadata_json.dry_run=true`。
- 已实测 `GMIND_LLM_PROVIDER=fake uv run --no-cache gmind add markdown --file /Users/neal/Downloads/2026年3月竞品动态报告.md --solo --dry-run --json`，返回 `source_id=null`、`dry_run=true`、`should_ingest=true`，并写入 `solo_add_allowed` 日志。
- CLI 现在支持 macOS Keychain fallback 读取 API key：环境变量不存在时自动执行 `security find-generic-password` 读取 App 存入 Keychain 的 key。真实模型 dry-run 实测通过，`should_ingest=true`，`confidence=0.95`，标题自动生成为"2026年3月骑行竞品动态报告"。
- solo 判断提示词已改为全中文，LLM 返回中文 reason。
- extract LLM 提取已并行化：`extract_llm_source` 用 `ThreadPoolExecutor` 并发调用 `provider.extract_chunk`（最大并发 5），数据库写入仍保持串行事务。add 文件的速度瓶颈（extract 串行逐块调用 LLM）已优化。
- 修复 extract 日期解析 bug：LLM 返回的 `occurred_at` 可能只有年份（如 `"2024"`），原代码直接传入 PostgreSQL 导致 `invalid input syntax for type timestamp with time zone` 错误，整个事务回滚。已新增 `_safe_parse_date` 安全解析 `YYYY-MM-DD`/`YYYY-MM`/`YYYY` 三种格式，无效时回退 NULL。
- 模型从 `Qwen/Qwen3.6-35B-A3B` 切换为 `deepseek-ai/DeepSeek-V4-Flash`；OpenAI client 增加 `timeout=60` 避免无限等待。但实测 DeepSeek 在硅基流动上响应时间波动极大（1s~32s），完整 add 仍超时（3m12s）。API 服务商的实例负载不稳定是核心瓶颈，不是代码问题。
- 最新验证：`uv run pytest` 通过 74 个测试；`swift build` 在 `apps/macos/GmindMenuBar` 此轮未重跑，上一轮通过。

## 下一步

- 下一步在 App 里做真正的 solo 模式：开关开启后持续从候选目录/agent 会话/历史导入父目录中发现文件，然后调用 CLI 的 `add --solo` 执行大模型判断和入库。
- 继续完善 `--solo` 的 LLM prompt 和结果观测，用真实模型批量看“该不该入库”的判断是否准确。
- 按最新产品要求，App 第一版 solo 候选目录先只做 `~/Downloads`，不要加级别 UI。
- App 后台调用 CLI 时可直接使用 `gmind add text/markdown --file <path> --solo`，无需传 title；CLI 会让 LLM 生成标题。
- 日常 CLI 也无需传 `--config gmind.toml`；只有需要覆盖路径时再用 `--config` 或 `GMIND_CONFIG`。
- 后续需要补 UI 或 debug 入口查看最近 `solo_add_allowed` / `solo_add_rejected` 记录，增强用户信任。
- 每次有重要决策、修改、测试或阻塞后，保持 `.agent/state.md` 和 `.agent/stats.md` 更新。

## 注意事项

- 当前工作区包含较多未提交/未跟踪的既有 App 和 CLI 改动；不要覆盖无关本地修改。
- 不要提交本地密钥。
