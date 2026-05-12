---
title: GMind 设计方案 v2
date: 2026-05-09
tags:
  - project
  - gmind
  - design
status: historical-design
---

# GMind — 个人知识大脑

> 替代 gbrain 的轻量级个人知识管理系统。Python + PostgreSQL + 向量搜索 + 知识图谱。

> 状态说明：这是 2026-05-09 的早期设计稿，用于追溯决策背景。当前实现请以仓库根目录的 `README.md`、`AGENTS.md` 和源码为准。本文中关于 `query` 调 LLM、`ingest` 调 LLM、自动 LLM 合并等内容是当时规划，不完全代表当前代码行为。

## 决策记录

| 决策项 | 结论 |
|---|---|
| 语言 | Python 3.12+ |
| 存储 | 远程 PG，**单库 + origin_node + status** |
| 搜索 | 向量搜索（pgvector，**维度 1024**） |
| 知识图谱 | 先轻量版，预留升级空间 |
| 冲突合并 | LLM 合并 + 人工回退机制 |
| 访问方式 | CLI + skill 文件 |
| Embedding | SiliconFlow Qwen 4B，维度 1024（MRL 截断） |
| Slug 规则 | **英文 slug + 中文 title + aliases 字段** |
| 目标 | 替代 gbrain，GitHub 开源 |
| 服务器 | 腾讯云 2C2G 上海，已有 PG |

---

## 一、整体架构

```
                    ┌─────────────────────────────┐
                    │      腾讯云 PG (单库)         │
                    │                             │
                    │  public.pages               │
                    │    origin_node: home/office  │
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
   │  (家里电脑)  │       │  (公司电脑)  │         │  (其他电脑)  │
   │  node: home  │       │  node: office│         │  node: xxx   │
   └──────────────┘       └──────────────┘         └──────────────┘
          │                        │                        │
          ▼                        ▼                        ▼
   Hermes + skill           Claude Code               Codex
                            + AGENTS.md               + 指令文件
```

### 多节点模型（v2 简化版）

**v1 方案**：每台电脑一个 schema（node_{id}）做临时区，sync 推到 public。
**v2 方案**：单库，pages 表加 `origin_node` + `status` 两列。

优势：
- 省掉 N 个 schema 的建表、迁移、维护
- 跨机器查询天然实时，agent 写完另一台立刻能查到
- sync 退化成"把 draft → published + 冲突检查"，代码量砍三分之一

```
写入流程：
  gmind add "笔记内容"
    → 写入 public.pages (status='draft', origin_node='home')

同步流程：
  gmind sync
    1. 把自己的 draft → published
    2. 检查有无冲突（同名 slug 被 published）
    3. 有冲突 → 走 LLM 合并

查询流程：
  gmind query "xxx"
    → WHERE status IN ('published', 'merge_review')
       OR (status='draft' AND origin_node='本节点')
    → 每台电脑能看到：所有已发布内容 + 正在合并的内容 + 自己的草稿
```

---

## 二、数据库设计

### pages — 全局页面表

```sql
CREATE TABLE pages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT UNIQUE NOT NULL,          -- 英文路径: "entities/zhang-san"
    title         TEXT NOT NULL,                 -- 中文显示名: "张三"
    aliases       TEXT[] DEFAULT '{}',           -- 中文别名，搜索时一并匹配
    content       TEXT NOT NULL,                 -- markdown 正文
    page_type     TEXT NOT NULL DEFAULT 'note',  -- note/entity/concept/source/query/synthesis
    frontmatter   JSONB DEFAULT '{}',            -- YAML 元数据
    sources       TEXT[] DEFAULT '{}',            -- 来源文件列表
    tags          TEXT[] DEFAULT '{}',

    -- 向量（维度固定 1024）
    embedding     vector(1024),

    -- 多节点字段
    origin_node   TEXT NOT NULL DEFAULT 'default',  -- 物理节点标识（home/office），决定查询可见性
    status        TEXT NOT NULL DEFAULT 'draft',    -- draft / published / merge_review

    -- 系统字段
    checksum      TEXT NOT NULL,                   -- 内容哈希，冲突检测用
    version       INTEGER DEFAULT 1,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    created_by    TEXT,                            -- 写入者标识（用户名 / agent 名），审计追踪
    updated_by    TEXT                             -- 最后更新者标识
);

-- 向量索引（HNSW）
CREATE INDEX idx_pages_embedding ON pages
    USING hnsw (embedding vector_cosine_ops);

-- 按状态和节点查询
CREATE INDEX idx_pages_status ON pages(status);
CREATE INDEX idx_pages_node ON pages(origin_node);
CREATE INDEX idx_pages_type ON pages(page_type);
CREATE INDEX idx_pages_tags ON pages USING gin(tags);
```

### page_history — 变更历史

```sql
CREATE TABLE page_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id     UUID REFERENCES pages(id),
    version     INTEGER NOT NULL,
    snapshot    JSONB NOT NULL,             -- 整行序列化，包含 content/frontmatter/tags/全部字段
    checksum    TEXT NOT NULL,
    action      TEXT DEFAULT 'update',      -- update / merge / manual_resolve
    created_at  TIMESTAMPTZ DEFAULT now(),
    created_by  TEXT
);
```

### edges — 知识图谱关系

```sql
CREATE TABLE edges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_page   UUID REFERENCES pages(id) ON DELETE CASCADE,  -- 外键，级联删除
    to_page     UUID REFERENCES pages(id) ON DELETE CASCADE,
    from_slug   TEXT NOT NULL,              -- 冗余，人类可读
    to_slug     TEXT NOT NULL,
    link_type   TEXT NOT NULL DEFAULT 'related',  -- related / mentioned / derived_from
    weight      REAL DEFAULT 1.0,
    confidence  REAL,                       -- LLM 抽取置信度 0~1
    evidence    TEXT,                       -- 原文片段（为什么有这个关系）

    created_by  TEXT,                       -- 哪个模型/哪一轮抽取的
    created_at  TIMESTAMPTZ DEFAULT now(),

    UNIQUE(from_page, to_page, link_type)
);

CREATE INDEX idx_edges_from ON edges(from_page);
CREATE INDEX idx_edges_to ON edges(to_page);
CREATE INDEX idx_edges_type ON edges(link_type);
```

### sync_log — 同步日志

```sql
CREATE TABLE sync_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id  TEXT NOT NULL,              -- 幂等：同一次 sync 的 request_id 不会重复记录
    node        TEXT NOT NULL,
    action      TEXT NOT NULL,              -- push / pull / merge / conflict / manual_resolve
    slug        TEXT,
    detail      JSONB,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX idx_sync_log_request ON sync_log(request_id, slug);
```

---

## 三、CLI 命令设计

```bash
# ========== 初始化 ==========
gmind init                              # 首次使用：创建配置、连数据库、建表
gmind init --node office                # 指定节点名

# ========== 写入 ==========
gmind add "今天读了关于RAG的文章..."
gmind add --type entity --title "张三" --slug "zhang-san" --content "..."
gmind add --file ./paper.md
gmind add --source "claude-code:session-xxx" "..."   # agent 写入强制带来源
gmind ingest ./papers/                  # 批量导入目录（LLM 提取）
gmind ingest ./article.pdf              # 导入 PDF（LLM 摘要）

# ========== 查询 ==========
gmind query "RAG 和 fine-tuning 的区别"  # 向量搜索 + LLM 总结
gmind query --entity "张三"              # 查某个实体相关的一切
gmind query --type concept              # 只查概念类页面
gmind search "关键词"                   # 纯搜索，不带 LLM 总结
gmind search --json "关键词"             # JSON 输出 top-k，给 agent 用（省 token）

# ========== 图谱 ==========
gmind graph "entities/zhang-san"         # 看和某页面的所有关系
gmind graph "entities/zhang-san" --depth 2
gmind graph --orphans                   # 找孤立页面
gmind graph --hubs                      # 找枢纽页面

# ========== 同步 ==========
gmind sync                              # draft → published + 冲突检查 + LLM 合并
gmind sync --dry-run                    # 预览，不动数据
gmind merge --manual <slug>             # 手动解决冲突，选版本
gmind merge --manual <slug> --list     # 列出冲突版本
# 输出: version 3 (home, 2026-05-09 10:00)
#       version 4 (office, 2026-05-09 11:30)
gmind merge --manual <slug> --pick 4   # 选择版本
gmind merge --manual <slug> --edit    # 启动编辑器手动合并
gmind merge --manual <slug> --version 3  # 恢复到指定历史版本

# ========== 维护 ==========
gmind embed --all                       # 重新生成所有向量
gmind embed --new                       # 只生成 embedding 为 NULL 的（断点续跑）
gmind lint                              # 健康检查（孤立页、失效链接、待确认合并）
gmind stats                             # 统计看板
gmind export ./output/                  # 导出成 markdown 文件夹
```

---

## 四、同步合并流程

```
gmind sync 执行流程：

1. PUBLISH 阶段
   ├── 扫描自己的 pages (status='draft', origin_node='home')
   ├── 逐条检查有没有同名 slug 且 status='published'
   ├── 无冲突 → INSERT ... ON CONFLICT (slug) DO UPDATE（幂等）
   │   └── WHERE pages.checksum != EXCLUDED.checksum
   │   └── AND pages.status != 'merge_review'   -- 保护正在人工处理的冲突
   │   └── status → 'published'
   ├── 有冲突（checksum 不同）
   │   └── draft 版本 → status='merge_review'
   │   └── published 版本保持 status='published'（其他节点仍可见）
   │   └── 两个版本都存入 page_history
   └── 写入 sync_log（带 request_id 去重）

2. MERGE 阶段（处理 merge_review）
   ├── 取出冲突的两个版本（draft 和 published 各一）
   ├── 调用 LLM 合并
   ├── 合并成功 → 写入合并结果，status → 'published'
   │   └── 保留 merge_review 标记，等 gmind lint 或人工确认
   ├── 合并失败 → 保持 merge_review 状态，等人工介入
   └── 写入 page_history（action='merge'）

3. 图谱更新
   ├── 扫描新写入/更新的页面
   ├── 提取 [[链接]] 和实体引用
   └── 更新 edges
```

### 冲突回退机制

- 合并前：两个版本都存 `page_history`（完整 snapshot）
- 合并后：保留 `merge_review` 标记，`gmind lint` 会列出待确认页面
- 手动解决：`gmind merge --manual <slug> --list` 看版本，`--pick N` 选版本
- 编辑器合并：`gmind merge --manual <slug> --edit`
- 回退：`gmind merge --manual <slug> --version N` 恢复到指定历史版本

---

## 五、写入去重机制

```
gmind add 执行流程：

1. 对内容生成 embedding（同步，但和写入拆成两个事务）
2. 向量检索 top-1
3. 如果相似度 > 0.92
   → 提示"已存在类似页面: [[xxx]]，是否合并/追加/忽略？"
   → 默认行为：追加到已有页面的 ## Updates 段落
4. 如果相似度 ≤ 0.92
   → 正常创建新页面
```

---

## 六、Embedding 容错

```python
# embed 策略
- 同步生成：gmind add 时先生成 embedding（失败可重试），再写数据库
- 异步写入：add 先写 embedding=NULL，后台补（备选方案）
- 断点续跑：gmind embed --new 只处理 embedding IS NULL 的
- 批量请求：一次 32 条，不是一条一条调
- 失败重试：指数退避，最多 3 次
- 限流处理：SiliconFlow 抖动时自动降速
```

---

## 七、安全

- 配置文件 `~/.gmind/config.toml` 权限 `chmod 600`
- PG 连接强制 SSL：`sslmode=require`
- 认证策略：SSL + 强密码连接字符串（核心安全层）
  - 公网 PG 可选开启白名单 IP（适合固定 IP 场景如公司网络）
  - 动态 IP 环境（家庭宽带）依赖 SSL + 密码认证，不强制白名单
- README 明确声明：**单用户系统，未做多租户隔离**

---

## 八、可观测性 — gmind stats

```
$ gmind stats

📊 GMind 知识库概览

页面总数:        1,247
├── note:         523
├── entity:       312
├── concept:      198
├── source:       145
├── query:         42
└── synthesis:     27

向量覆盖率:      98.3% (1,226/1,247)
孤立页面:         89 (7.1%)
图谱关系:        3,847 条

最近 7 天写入:    34 页
最近一次 sync:    2 分钟前 (成功)
待确认合并:       3 页
平均 embed 延迟:  120ms
```

---

## 九、Skill 文件（给各 agent 用）

```markdown
# gmind-cli skill

## 何时触发
当用户要求记录笔记、查询知识、导入资料、或涉及"我的知识库"时使用。

## 核心命令
- 添加笔记: gmind add "内容" --source "agent-name:session-id"
- 快速搜索（省 token）: gmind search --json "关键词"
- 深度查询: gmind query "问题"
- 导入文件: gmind ingest <路径>
- 查看关系: gmind graph <slug>
- 同步: gmind sync

## 规范
- 所有写入必须带 --source，标注来源
- 引用已有页面用 [[slug]] 语法（英文 slug）
- 实体（人名、公司名）用 --type entity
- 写入前系统会自动检测重复（相似度 > 0.92 会提示）

## 禁止行为
- ❌ 不要主动调用 gmind sync（让用户控制同步时机）
- ❌ 不要批量 ingest 超过 10 个文件而不确认
- ❌ 不要删除或覆盖已有页面（用追加或更新）
- ❌ 不要在 gmind query 和 gmind search 之间重复调用（先用 search --json 判断是否需要深入）
```

---

## 十、技术栈

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12+ | 开发效率 |
| CLI 框架 | Typer | 简洁优雅，自带 help |
| 数据库 | PostgreSQL + pgvector | 已有，向量搜索原生支持 |
| Migration | Alembic | schema 版本管理，后期迭代必备 |
| Embedding | SiliconFlow Qwen 4B，维度 1024 | MRL 截断，质量损失小 |
| LLM | 可配置（OpenAI 兼容接口） | 摄入、查询总结、合并冲突用 |
| 打包 | uv + pyproject.toml | 现代 Python 打包分发 |
| 配置 | TOML 文件 `~/.gmind/config.toml` | 简单 |
| 测试 | pytest + testcontainers-python | 真实 PG 测试 |

---

## 十一、目录结构

```
gmind/
├── pyproject.toml
├── README.md
├── src/
│   └── gmind/
│       ├── __init__.py
│       ├── cli.py              # CLI 入口（Typer）
│       ├── config.py           # 配置管理（TOML）
│       ├── db.py               # 数据库连接和操作
│       ├── sync.py             # 同步 + 冲突检测
│       ├── merge.py            # LLM 合并 + 人工回退
│       ├── embed.py            # 向量生成（批量、断点续跑、重试）
│       ├── search.py           # 混合搜索（向量 + 关键词）
│       ├── graph.py            # 知识图谱操作
│       ├── ingest.py           # 资料摄入（LLM 提取）
│       ├── query.py            # 查询（搜索 + LLM 总结）
│       ├── lint.py             # 健康检查
│       ├── export.py           # 导出 markdown
│       ├── llm.py              # LLM 调用封装
│       └── stats.py            # 可观测性统计
├── migrations/                  # Alembic 数据库迁移
│   └── versions/               # 迁移脚本
├── skills/
│   └── gmind-cli/
│       └── SKILL.md            # 给 agent 用的 skill 文件
└── tests/
    ├── test_sync.py            # 冲突合并测试
    ├── test_search.py          # 搜索召回测试
    ├── test_ingest.py          # 摄入幂等性测试
    └── conftest.py             # testcontainers PG fixtures
```

---

## 十二、开发阶段

| 阶段 | 内容 | 说明 |
|------|------|------|
| **P0 核心** | init → add → embed → query | 最小闭环，先跑通（query 内部先做纯向量检索，P1 再拆出独立 search） |
| **P1 同步** | status 列 + publish + 冲突检测 + LLM 合并 + 人工回退 | 多电脑协作 |
| **P2 摄入** | ingest 文件/PDF + LLM 提取 + 去重 | 知识入库 |
| **P3 图谱** | 链接提取 + edges + graph 查询 | 知识关联 |
| **P4 维护** | lint + export + stats + 安全加固 | 长期可用 |
| **P5 开源** | README + 文档 + GitHub Actions CI | 发布 |

---

## 十三、测试策略

- **框架**：pytest + testcontainers-python（跑真实 PG，pgvector 行为无法用 SQLite mock）
- **重点覆盖**：
  - sync 的冲突合并（两个版本同时 published）
  - 向量搜索的召回率
  - ingest 的幂等性（同一文件摄入两次不会重复）
- **CI**：GitHub Actions，每次 PR 跑全量测试

---

## 十四、设计变更日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-05-09 | v1 初版 | 首次设计 |
| 2026-05-09 | v2 架构简化 | 砍掉多 schema，单库 + node_id + status |
| 2026-05-09 | v2 embedding 维度定 1024 | MRL 截断质量损失小，索引快 |
| 2026-05-09 | v2 slug 规则：英文+中文 title+aliases | 避免 shell 转义问题，兼容开源生态 |
| 2026-05-09 | v2 补冲突回退机制 | LLM 合并非万能，需兜底 |
| 2026-05-09 | v2 补并发幂等 | ON CONFLICT + request_id 去重 |
| 2026-05-09 | v2 补 embedding 容错 | SiliconFlow 抖动时的断点续跑、批量、重试 |
| 2026-05-09 | v2 补安全 | chmod 600、SSL、白名单、单用户声明 |
| 2026-05-09 | v2 补可观测性 | gmind stats 统计看板 |
| 2026-05-09 | v2 补 agent 规范 | search --json、--source 强制、去重、禁止行为 |
| 2026-05-09 | v2 page_history 改 JSONB snapshot | 保留完整历史，不只存 content |
| 2026-05-09 | v2 edges 加 page_id 外键 | slug 重命名时边自动跟随 |
| 2026-05-09 | v2 edges 加 confidence + created_by | 将来图谱清洗有据可查 |
| 2026-05-09 | v2 查询 visibility 规则明确 | published + merge_review OR (draft AND 本节点) |
| 2026-05-09 | v2 edges 外键加 ON DELETE CASCADE | 删页面时边自动清理 |
| 2026-05-09 | v2 sync 幂等 UPDATE 加保护条件 | checksum != 且 status != merge_review |
| 2026-05-09 | v2 embedding 异步 vs 去重矛盾解决 | add 同步生成 embedding，拆事务 |
| 2026-05-09 | v2 merge --manual 交互设计 | --list / --pick / --edit |
| 2026-05-09 | v2 P0 最小闭环再砍 | 砍掉独立 search，query 内部先做检索 |
| 2026-05-09 | v2 slug 生成策略 | P0 强制指定，P2 加拼音自动生成 |
