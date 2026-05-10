# GMind — AI 编码代理项目指南

> 本文档面向 AI 编码代理。阅读前须知：本项目目前**仅包含设计文档**，尚无实际可运行的源代码。

---

## 项目概述

GMind 是一个面向知识工作者的开源知识库 CLI 工具，基于 PostgreSQL + pgvector 构建，目标是通过向量搜索和知识图谱将碎片化的笔记、阅读材料与思考串联成可查询、可探索的知识网络。

**当前状态**：极早期设计阶段。仓库中仅有 `README.md`（设计规格书）和 `LICENSE`（Apache 2.0），无源代码、无构建配置、无测试。

---

## 仓库现状

```
.
├── LICENSE          # Apache License 2.0
├── README.md        # 项目设计文档（含架构图、CLI 命令设计、数据库 Schema 规划、技术栈选型、路线图）
└── AGENTS.md        # 本文件
```

**关键事实**：
- 无 `pyproject.toml`、`setup.py`、`setup.cfg` 或任何其他 Python 包配置文件。
- 无源码目录（如 `src/`、`gmind/`）。
- 无测试目录或测试框架配置。
- 无 CI/CD 配置（如 `.github/workflows/`）。
- 无数据库迁移脚本、Dockerfile、或其他部署制品。
- Git 历史仅 3 个 commit，全部集中在文档撰写。

---

## 设计意图（来自 README.md）

以下信息全部来源于 `README.md` 中的设计规划，**尚未落地实现**：

### 技术栈规划

| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.12+ | 开发效率 |
| CLI 框架 | Typer | 简洁优雅，自带 help |
| 数据库 | PostgreSQL + pgvector | 向量搜索原生支持 |
| Migration | Alembic | schema 版本管理 |
| Embedding | SiliconFlow Qwen 4B，维度 1024 | MRL 截断，质量损失小 |
| LLM | 可配置（OpenAI 兼容接口） | 摄入、查询总结、合并冲突 |
| 打包 | uv + pyproject.toml | 现代 Python 打包 |
| 测试 | pytest + testcontainers-python | 真实 PG 测试 |

### 架构设计

- **单库 + status 列** 方案：所有节点共享同一个 PostgreSQL 数据库，通过 `origin_node` 列标识物理节点，`status` 列区分 `draft` / `published` / `merge_review`。
- 核心表（规划中）：`pages`、`page_history`、`edges`、`sync_log`。
- `pages.embedding` 使用 `vector(1024)` 并建立 HNSW 索引。

### 规划中的 CLI 命令

```bash
gmind init --node <name>          # 初始化节点配置
gmind add <content>               # 添加笔记（自动去重、自动 embedding）
gmind add --type entity ...       # 添加结构化页面
gmind query <question>            # 语义查询（向量搜索 + LLM 总结）
gmind search --json <keyword>     # 快速搜索（JSON 输出，适合 Agent 调用）
gmind graph <slug> --depth <n>    # 查看知识图谱
gmind sync                        # 多节点同步（冲突检测 + LLM 合并）
gmind merge --manual <slug> ...   # 手动合并/回退
gmind stats                       # 统计看板
```

### 开发路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| **P0 核心** | init → add → embed → query | 🚧 进行中（尚未提交代码） |
| **P1 同步** | status 列 + publish + 冲突检测 + LLM 合并 | 📋 待开始 |
| **P2 摄入** | ingest 文件/PDF + LLM 提取 + 去重 | 📋 待开始 |
| **P3 图谱** | 链接提取 + edges + graph 查询 | 📋 待开始 |
| **P4 维护** | lint + export + stats + 安全加固 | 📋 待开始 |
| **P5 开源** | README + 文档 + GitHub Actions CI | 📋 待开始 |

---

## 构建与测试

**当前无可执行的构建或测试流程。**

根据 `README.md` 中的规划，未来预期的开发工作流为：

```bash
# 安装依赖（规划）
uv pip install -e ".[dev]"

# 运行测试（规划）
pytest
```

---

## 代码风格与约定

**尚未形成。** 由于无源代码，目前不存在任何代码风格指南、lint 配置（如 ruff、black、mypy）或命名约定。

建议未来参照 Python 社区标准：
- 使用 `ruff` 进行代码格式化和 lint。
- 使用 `mypy` 进行类型检查（Typer 对类型注解有良好支持）。
- 采用 `src/` 目录布局（如 `src/gmind/`）。

---

## 安全注意事项

以下安全策略在 `README.md` 中有提及，但**尚未在代码中实现**：

- 配置文件计划存放于 `~/.gmind/config.toml`，目标权限 `chmod 600`。
- PostgreSQL 连接计划强制 `sslmode=require`。
- 项目定位为**单用户系统**，不计划做多租户隔离。

---

## 给 AI 代理的建议

1. **不要假设代码存在**：在修改任何功能前，先确认相关文件是否已创建。
2. **以 README 为设计规格书**：若用户要求实现功能，README 中描述的 CLI 接口和数据库设计是当前最权威的参考。
3. **从 P0 开始**：核心闭环（init → add → embed → query）是验证架构的最小可行路径。
4. **优先创建基础设施**：建议首先添加 `pyproject.toml`、源码目录结构和 pytest 测试框架，再迭代业务功能。

---

## License

Apache License 2.0
