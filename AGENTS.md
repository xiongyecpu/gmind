# AGENTS.md

这些规则适用于在本仓库工作的 coding agent。

## Agent 状态规则

每次会话开始时：

1. 如果 `.agent/state.md` 存在，先读取它。
2. 读取 `git status --short --branch`。
3. 把 `.agent/state.md` 当作当前可恢复的工作状态。

工作过程中：

- 每次出现有意义的决策、文件修改、测试结果或阻塞点后，都更新 `.agent/state.md`。
- 更新内容保持简短、实用。
- 永远不要把密钥、API key、密码、token 或私有数据库 URL 写进 `.agent/state.md`。

最终回复前：

- 更新 `.agent/state.md`，写清楚本次改了什么、验证了什么、下一步是什么，以及仍有哪些风险或阻塞。
