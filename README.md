# GMind — 知识图谱与向量搜索引擎

> 🧠 基于 PostgreSQL + pgvector 的知识管理系统。支持语义搜索、多节点同步与自动知识图谱构建。

---

## 这是什么？

GMind 是一个**面向知识工作者的开源知识库 CLI 工具**。它将碎片化的笔记、阅读材料与思考，通过向量搜索和知识图谱串联成一张可查询、可探索的知识网络。

核心理念：
- **写即入库** — 一条命令写入数据库，自动 embedding
- **问即搜索** — 自然语言查询，语义召回 + LLM 总结
- **多节点同步** — 多设备间 draft / published 状态自动合并
- **图谱关联** — 自动提取链接与实体关系，发现知识盲区

---

## 架构一览

```
                    ┌─────────────────────────────┐
                    │    中央 PostgreSQL 数据库      │
                    │                             │
                    │  public.pages               │
                    │    origin_node: node_a       │
                    │    status: draft/published   │
                    │                             │
                    │  public.edges               │
                    │    知识图谱关系               │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
   ┌──────────────┐       ┌──────────────┐         ┌──────────────┐
   │  gmind CLI   │       │  gmind CLI   │         │  gmind CLI   │
   │  (节点 A)    │       │  (节点 B)    │         │  (节点 C)    │
   │  node: a     │       │  node: b     │         │  node: c     │
   └──────────────┘       └──────────────┘         └──────────────┘
```

### 为什么单库 + 状态列？

| 方案 | 多 Schema 隔离 | **单库 + status 列** ✅ |
|------|--------------|------------------------|
| 维护成本 | N 个 schema 的迁移开销 | 一张表，两列解决 |
| 跨节点查询 | 需要推送到公共 schema | 天然实时，全局可见 |
| 同步逻辑 | 复杂的双向推/拉 | draft → published，代码量大幅降低 |

---

## 核心功能

```bash
# 初始化
$ gmind init --node home

# 添加笔记（自动去重、自动 embedding）
$ gmind add "今天读了关于 RAG 的文章..."
$ gmind add --type entity --title "张三" --slug "zhang-san" --content "..."

# 语义查询（向量搜索 + LLM 总结）
$ gmind query "RAG 和 fine-tuning 的区别"

# 快速搜索（JSON 输出，省 token，适合 Agent 调用）
$ gmind search --json "关键词"

# 查看知识图谱
$ gmind graph "entities/zhang-san" --depth 2

# 多节点同步（自动冲突检测 + LLM 合并）
$ gmind sync

# 统计看板
$ gmind stats
```

### 写入去重

添加内容时自动检索相似页面，相似度 > 0.92 提示合并/追加，避免知识库膨胀。

### 冲突合并与回退

多节点同时修改同一页面？
- `gmind sync` 自动 LLM 合并
- 合并结果标记 `merge_review`，待确认
- 不满意？`gmind merge --manual <slug> --list` 查看历史版本，`--pick` 回退

---

## 数据库设计

| 表 | 用途 |
|---|---|
| `pages` | 全局页面，支持 6 种类型（note / entity / concept / source / query / synthesis） |
| `page_history` | 变更历史，完整 JSONB snapshot，可回退到任意版本 |
| `edges` | 知识图谱关系，带置信度与证据原文 |
| `sync_log` | 同步日志，request_id 幂等去重 |

```sql
-- 核心字段
origin_node TEXT  -- 物理节点标识
status      TEXT  -- draft / published / merge_review
embedding   vector(1024)  -- pgvector HNSW 索引
```

---

## 技术栈

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12+ | 开发效率 |
| CLI 框架 | [Typer](https://typer.tiangolo.com/) | 简洁优雅，自带 help |
| 数据库 | PostgreSQL + [pgvector](https://github.com/pgvector/pgvector) | 向量搜索原生支持 |
| Migration | [Alembic](https://alembic.sqlalchemy.org/) | schema 版本管理 |
| Embedding | SiliconFlow Qwen 4B，维度 1024 | MRL 截断，质量损失小 |
| LLM | 可配置（OpenAI 兼容接口） | 摄入、查询总结、合并冲突 |
| 打包 | [uv](https://docs.astral.sh/uv/) + pyproject.toml | 现代 Python 打包 |
| 测试 | pytest + [testcontainers-python](https://testcontainers-python.readthedocs.io/) | 真实 PG 测试 |

---

## 快速开始

> ⚠️ 项目处于早期开发阶段，P0 核心闭环即将完成。

```bash
# 1. 安装（后续支持 pip/uv）
$ git clone https://github.com/xiongyecpu/gmind.git
$ cd gmind && uv pip install -e ".[dev]"

# 2. 配置
$ gmind init
# 按提示输入 PostgreSQL 连接信息

# 3. 开始使用
$ gmind add "我的第一条笔记"
$ gmind query "笔记"
```

---

## 开发路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| **P0 核心** | init → add → embed → query | 🚧 进行中 |
| **P1 同步** | status 列 + publish + 冲突检测 + LLM 合并 | 📋 待开始 |
| **P2 摄入** | ingest 文件/PDF + LLM 提取 + 去重 | 📋 待开始 |
| **P3 图谱** | 链接提取 + edges + graph 查询 | 📋 待开始 |
| **P4 维护** | lint + export + stats + 安全加固 | 📋 待开始 |
| **P5 开源** | README + 文档 + GitHub Actions CI | 📋 待开始 |

---

## 安全说明

- 配置文件 `~/.gmind/config.toml` 权限 `chmod 600`
- PG 连接强制 SSL：`sslmode=require`
- **单用户系统，未做多租户隔离**

---

## 为什么叫 GMind？

G for **Graph** + **Global** + **General** knowledge — 一张图，连接所有知识。

---

## License

[MIT](LICENSE)
