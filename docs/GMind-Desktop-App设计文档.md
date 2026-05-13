# GMind Desktop App 设计文档

> 状态：已切换到 Electron 路线，第一版实现中。<br>
> Status: Electron has been selected; the first desktop version is being implemented.

## 1. 目标 / Goal

GMind 的产品入口从“用户手动安装 CLI + 手动启动 server”切到 `GMind.app`：

1. 用户启动 `GMind.app`。
2. App 自动注册或修复 `gmind` CLI。
3. App 自动启动本地 HTTP server。
4. macOS App、CLI、Chrome Extension、Agent skill 都通过同一个本地后端访问知识库。
5. 普通用户只需要打开 App；CLI 主要面向 Agent、脚本和高级用户。

一句话：**Mac App 给人使用，CLI 给其他 Agent 使用；App 是入口，CLI 和 server 是 App 管理出来的能力。**

## 2. 当前决策 / Decisions

| 决策 | 结论 |
|------|------|
| 桌面框架 | Electron |
| macOS 形态 | 菜单栏 / tray-first app，默认不显示 Dock 图标 |
| Windows 后续形态 | notification area / system tray app |
| 后端核心 | 继续使用 Python CLI + Starlette HTTP API |
| CLI 注册 | App 自动写入 `~/.local/bin/gmind` shim |
| server 生命周期 | App 启动时自动启动，App 退出时停止由 App 启动的 server |
| 用户配置 | 保留 `~/.gmind/config.toml`，不静默删除或覆盖 |

## 3. 当前实现 / Current Implementation

```text
.
├── gmind-desktop/
│   ├── index.html              # App shell
│   ├── src/
│   │   ├── main.js             # UI state, HTTP API calls, Electron bridge commands
│   │   └── styles.css          # Tray app UI
│   └── src/electron/
│       ├── main.cjs            # Electron tray, CLI registration, server lifecycle
│       └── preload.cjs         # Safe renderer bridge
├── src/gmind/server.py         # Starlette API, includes /health
└── src/gmind/config.py         # GMind config and LLM config compatibility
```

第一版 App 覆盖的核心功能：

- 概览：统计与近期状态
- 记一条：快速添加笔记
- 问一下：优先 `/ask`，失败时降级到 `/search`
- 知识雷达：扫描、队列、启动/暂停入库
- 模型配置：在 App 内编辑 `~/.gmind/config.toml` 的 LLM 配置
- 诊断：server 状态、CLI 状态、重启 server、修复 CLI

## 4. 架构 / Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                     GMind.app                            │
│                                                         │
│  Electron UI                                            │
│  - Tray/menu bar                                        │
│  - 记一条 / 问一下 / 知识雷达 / 设置 / 诊断              │
│                                                         │
│  Node app services                                      │
│  - Server lifecycle                                     │
│  - CLI registration                                     │
│  - Config read/write                                    │
│  - Diagnostics                                          │
│                                                         │
│  Python backend                                         │
│  - Typer CLI                                            │
│  - Starlette HTTP API                                   │
└─────────────────────────────────────────────────────────┘
             ▲
             │
      ~/.local/bin/gmind
      CLI shim managed by GMind.app
```

开发模式下，Electron App 会优先使用当前 repo 的 `.venv/bin/gmind`。正式发布时，目标是把后端 runtime 或 CLI helper 放进 App bundle，让干净机器无需手动安装 Python 包。

## 5. CLI 注册 / CLI Registration

App 启动时自动检查：

1. `~/.local/bin` 是否存在，不存在则创建。
2. `~/.local/bin/gmind` 是否存在。
3. 如果不存在，写入 GMind 管理的 shim。
4. 如果存在且是旧 GMind symlink 或 GMind 管理的 shim，自动替换。
5. 如果存在且是用户自己的普通文件，不静默覆盖。

shim 带 marker：

```bash
#!/bin/zsh
# Managed by GMind.app
exec "/path/to/gmind-cli-or-dev-venv-gmind" "$@"
```

## 6. Server 生命周期 / Server Lifecycle

App 启动时：

1. 请求 `GET http://127.0.0.1:8765/health`。
2. 如果是兼容 GMind server，复用。
3. 如果没有 server，启动 `gmind serve --port 8765`。
4. 如果端口冲突或启动失败，在诊断页展示错误。

健康检查：

```http
GET /health
```

返回：

```json
{
  "status": "ok",
  "app": "gmind",
  "version": "0.1.0",
  "node_name": "home",
  "config_path": "~/.gmind/config.toml"
}
```

## 7. 用户数据与清理边界 / Data Safety

项目清理只清理废弃 App 代码、旧构建产物、旧进程和 App 管理的 CLI shim，不清理知识库数据。

必须保留：

- `~/.gmind/config.toml`
- PostgreSQL / pgvector 数据库
- 用户的 API keys 和 node 配置
- Chrome Extension 配置

可以清理：

- 临时构建产物
- 旧的 `gmind serve` 进程
- App 管理范围内的旧 `~/.local/bin/gmind` symlink/shim

## 8. 第一版验收 / MVP Acceptance Criteria

- 双击 `GMind.app` 后，`http://127.0.0.1:8765/health` 可用。
- 终端运行 `gmind stats` 可用。
- 菜单栏 Quick Add 可保存笔记。
- Ask AI 在 LLM 配置可用时能回答；不可用时有清晰错误或降级搜索。
- Chrome Extension 不需要用户手动启动 server。
- App 能显示 server 状态和 CLI 状态。
- 不破坏现有 CLI 命令和 HTTP API。

## 9. 下一步 / Next Steps

1. 把 Python backend 做成 release 可携带 runtime 或 sidecar。
2. 增加更完整的首次启动配置向导。
3. 增加日志查看与 Copy Diagnostics。
4. 做 macOS 签名、公证和 DMG/zip 分发。
5. 抽象 Windows tray 差异，准备后续跨平台版本。
