# GMind 公司电脑接手交接 / Office Handoff

> 时间：2026-05-13  
> 交接来源：home 节点，Codex  
> 分支：`codex-home-macos-app-runtime-fixes`

## 1. 当前结论 / Current State

GMind 桌面端主线已经从旧 SwiftUI macOS app 切到 Tauri：

- 新桌面 app 在 `gmind-desktop/`。
- 旧 SwiftUI app 目录 `gmind-macos/` 已从仓库删除。
- 旧代码已在 home 机器本地备份到：

```text
/Users/xiongye/neal/gmind-backups/gmind-macos-legacy-20260513-062131.tar.gz
```

注意：这个备份路径只存在于 home 机器，不会随 git 同步到公司电脑。

## 2. 设计边界 / Product Boundary

产品形态已经确认：

- Mac App 给人使用。
- CLI 给 Agent、脚本和高级用户使用。
- App 启动时自动注册 CLI，并自动启动 HTTP server。
- 用户不需要手动跑 `gmind serve`。
- 用户知识库配置与数据继续保存在本机，不随 App 清理：
  - `~/.gmind/config.toml`
  - PostgreSQL / pgvector 数据库

不要删除或重置用户的 `~/.gmind/`、PostgreSQL 数据库、API key、Chrome Extension 配置。

## 3. 关键目录 / Key Paths

```text
gmind-desktop/
  index.html
  src/main.js
  src/styles.css
  src-tauri/src/main.rs
  src-tauri/tauri.conf.json

src/gmind/
  server.py        # 新增 /health
  config.py        # LLM legacy config 兼容

tests/
  test_config.py   # LLM config compatibility tests

docs/
  GMind-macOS-App化设计文档.md
```

## 4. 当前已实现 / Implemented

Tauri app 已有第一版功能：

- Tray/menu bar app，macOS `LSUIElement=true`。
- 自动启动 `gmind serve --host 127.0.0.1 --port 8765`。
- 自动注册 `~/.local/bin/gmind` shim。
- App 内页面：
  - 概览
  - 记一条
  - 问 AI
  - 饕餮盛宴
  - 模型配置
  - 诊断
- `POST /ask` 失败时，前端会降级到 `/search`。
- `/health` API 可用于桌面 app 探活。
- `~/.gmind/config.toml` 支持旧的顶层 LLM 配置兼容读取。

## 5. Home 机器验证结果 / Verified on Home

已通过：

```bash
cargo fmt --check
cargo check
npm run build
npm run tauri build -- --bundles app
uv run ruff check src/gmind/server.py tests/test_config.py
uv run pytest tests/test_config.py
git diff --check
```

home 机器运行态：

```text
GMind.app:
/Users/xiongye/neal/gmind/gmind-desktop/src-tauri/target/release/bundle/macos/GMind.app

health:
GET http://127.0.0.1:8765/health -> ok

stats:
585 pages, 1643 edges at handoff time
```

## 6. 公司电脑接手步骤 / Office Setup

在公司电脑上：

```bash
git fetch origin
git checkout codex-home-macos-app-runtime-fixes
git pull --ff-only
```

安装依赖并构建：

```bash
uv pip install -e ".[dev]"

cd gmind-desktop
npm install
npm run build
npm run tauri build -- --bundles app
```

启动 App：

```bash
open gmind-desktop/src-tauri/target/release/bundle/macos/GMind.app
```

检查：

```bash
curl -sS http://127.0.0.1:8765/health
gmind stats
```

如果公司电脑没有配置 LLM，在 App 的“模型配置”里配置即可。不要直接拿 home 机器的 `~/.gmind/config.toml` 覆盖 office 机器配置，office 的 `node_name` 应该是 `office`。

## 7. 已知风险 / Known Risks

- 当前 Tauri release build 在开发模式下仍指向 repo `.venv/bin/gmind`。正式分发前需要把 Python backend 打进 App bundle，或做 sidecar runtime。
- CLI shim 会自动替换旧 GMind symlink；如果用户已有非 GMind 管理的普通文件，App 不应静默覆盖。
- DMG 打包此前不稳定；当前验证的是 `.app` bundle：`npm run tauri build -- --bundles app`。
- 历史 `docs/` 里仍有旧方案稿；以 `README.md`、`AGENTS.md`、`docs/GMind-macOS-App化设计文档.md` 为当前口径。
- `gmind taotie scan` 可以运行，但批量 ingest 或扫描敏感目录前仍需用户确认。

## 8. 下一步建议 / Next Steps

1. 做 bundled backend：让 `GMind.app` 不再依赖 repo `.venv/bin/gmind`。
2. 增加首次启动配置向导，尤其是 database、embedding、LLM。
3. 增加日志查看、Copy Diagnostics、端口冲突提示。
4. 补 Tauri command / UI 的测试或最小 smoke test。
5. 准备签名、公证、DMG/zip 分发。

## 9. 交接摘要 / Handoff Summary

```text
Agent: Codex
Node: home
Branch: codex-home-macos-app-runtime-fixes
Scope: Tauri desktop app, CLI registration, server lifecycle, docs, config compatibility
Changed: gmind-desktop/, README.md, AGENTS.md, src/gmind/server.py, src/gmind/config.py, tests/test_config.py, docs/GMind-macOS-App化设计文档.md
Tests: cargo fmt/check, npm build, tauri app bundle, ruff, pytest, git diff --check
Open questions: bundled backend packaging, first-run onboarding, release signing/notarization
Next step: continue from Tauri mainline and remove remaining dev-only backend assumptions
```
