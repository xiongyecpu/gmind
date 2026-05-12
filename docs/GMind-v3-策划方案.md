# GMind v3 策划方案：Mac 菜单栏 + 内置 LLM

> 从 "Agent-First Memory" 到 "Self-Contained Knowledge System"

---

## 一、为什么做这个转变

当前 GMind 的定位是 **Agent 的外部记忆** —— 存储、检索、同步由 GMind 做，推理由外部 Agent（Claude、Kimi 等）完成。

但用户的真实体验痛点是：

| 痛点 | 现状 | 期望 |
|------|------|------|
| 使用门槛 | 必须打开终端打命令 | 菜单栏一点即录 |
| 知识化 | Agent 每次都要重新理解上下文 | GMind 主动理解、结构化 |
| 图谱化 | 只有 `[[wikilink]]` 人工链接 | 自动提取实体、语义关联 |
| 推理链 | Agent 控制，不可复现 | GMind 内置，可追踪可回放 |

**核心转变**：GMind 从 "被动的存储器" 变成 "主动的知识管家"。

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      表现层 (Presentation)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Mac 菜单栏 App │  │   CLI 终端   │  │ Chrome Extension │   │
│  │  (SwiftUI)   │  │  (Typer)    │  │   (Manifest V3)  │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
└─────────┼────────────────┼──────────────────┼─────────────┘
          │                │                  │
          └────────────────┼──────────────────┘
                           │  HTTP API (Starlette)
┌──────────────────────────┼─────────────────────────────────┐
│                      核心层 (Core)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              GMind HTTP Server (Python)               │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐  │  │
│  │  │  /add   │ │ /search │ │ /query  │ │  /graph   │  │  │
│  │  │  /check │ │ /stats  │ │ /sync   │ │  /export  │  │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └───────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │  db.py   │ │ embed.py │ │ search.py│ │  server.py   │  │
│  │  add.py  │ │ query.py │ │ graph.py │ │   sync.py    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────┼─────────────────────────────────┐
│                   新增：LLM 引擎层                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  llm/  (新增模块)                      │  │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────┐   │  │
│  │  │  engine.py │  │ extract.py │  │  reason.py   │   │  │
│  │  │  (路由层)   │  │(实体/关系提取)│  │(推理/问答链)  │   │  │
│  │  └────────────┘  └────────────┘  └──────────────┘   │  │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────┐   │  │
│  │  │ enrich.py  │  │ summarize.py│  │  merge.py    │   │  │
│  │  │(知识增强)  │  │(自动摘要)   │  │(智能合并)    │   │  │
│  │  └────────────┘  └────────────┘  └──────────────┘   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              LLM Provider 适配器                      │  │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────────────────┐  │  │
│  │   │  Ollama │  │ OpenAI  │  │ SiliconFlow / Other │  │  │
│  │   │ (本地)   │  │(远程)   │  │    (远程)           │  │  │
│  │   └─────────┘  └─────────┘  └─────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────┼─────────────────────────────────┐
│                   存储层 (Storage)                          │
│  ┌─────────────────┐  ┌─────────────────────────────────┐  │
│  │  PostgreSQL     │  │  ~/.gmind/                      │  │
│  │  + pgvector     │  │  ├── config.toml               │  │
│  │  ├── pages      │  │  ├── llm_cache/  (推理缓存)     │  │
│  │  ├── edges      │  │  ├── local_models/ (本地模型)   │  │
│  │  ├── page_history│  │  └── assets/     (附件)         │  │
│  │  └── sync_log   │  │                                 │  │
│  └─────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、Mac 菜单栏应用

### 3.1 技术选型

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **SwiftUI + Python HTTP** | 原生体验，复用现有 server | 需要写 Swift 代码 | ⭐⭐⭐⭐⭐ |
| Electron + Python 子进程 | 一套代码跨平台 | 内存大、启动慢、不像 Mac 应用 | ⭐⭐ |
| PyQt / PySide | Python 全栈 | 非原生、打包体积大 | ⭐⭐⭐ |
| Tauri (Rust) + Python | 轻量、现代 | 学习曲线，过度工程 | ⭐⭐⭐ |

**推荐：SwiftUI + 复用 gmind serve**

理由：
- GMind 已经有 `gmind serve` HTTP server，SwiftUI 做前端是最轻量的方案
- 菜单栏应用天然适合 SwiftUI (`NSMenu`, `NSStatusBar`)
- 打包后可以做成 `.app`，用户双击即用
- 保持后端是 Python，不改现有 CLI 逻辑

### 3.2 功能设计

```
┌────────────────────────────────────────────┐
│  🧠 GMind                        [偏好设置] │  ← 状态栏常驻图标
├────────────────────────────────────────────┤
│  📝 Quick Add...              ⌘⇧A         │
│  🔍 Quick Search...           ⌘⇧S         │
│  ────────────────────────────────────────── │
│  📊 Stats                     128 pages    │
│  🔄 Last synced: 2m ago                    │
│  ────────────────────────────────────────── │
│  📑 Recent                                  │
│    → 向量数据库设计原理                      │
│    → Python 异步编程笔记                    │
│    → 会议：Q3 产品规划                       │
│  ────────────────────────────────────────── │
│  ⚙️ Settings                               │
│  🚀 Open Dashboard...                      │
│  ────────────────────────────────────────── │
│  Quit                         ⌘Q          │
└────────────────────────────────────────────┘
```

#### 核心交互

**Quick Add (⌘⇧A)**
```
┌────────────────────────────────────────────┐
│  📝 Quick Add                    [发送]     │
│  ┌────────────────────────────────────────┐ │
│  │                                        │ │
│  │  今天读了《重来》第三章，关于远程工作的   │ │
│  │  观点很犀利...                          │ │
│  │                                        │ │
│  └────────────────────────────────────────┘ │
│  Tags: [工作方法] [书籍]                    │
│  Source: [粘贴的链接]                       │
│  [⚡ Auto-extract entities]  [☑️]           │
└────────────────────────────────────────────┘
```
- 全局快捷键唤起（类似 Spotlight）
- 自动识别剪贴板中的 URL，填入 Source
- 可选"自动提取实体"（调用 LLM 引擎）

**Quick Search (⌘⇧S)**
```
┌────────────────────────────────────────────┐
│  🔍 Search...                             │
│  ┌────────────────────────────────────────┐ │
│  │  远程工作 的团队沟通                     │ │
│  └────────────────────────────────────────┘ │
│  ────────────────────────────────────────── │
│  📄 向量数据库设计原理          0.92        │
│  📄 重来 - 远程工作章节         0.88        │
│  👤 David Heinemeier Hansson  0.75        │
│  ────────────────────────────────────────── │
│  🤖 Ask AI about "远程工作 的团队沟通"      │
└────────────────────────────────────────────┘
```
- 实时向量搜索（输入即搜）
- 最后一行是 "Ask AI" —— 点击后进入 LLM 问答模式

**Dashboard (WebView)**
- 用 SwiftUI 的 `WebView` 或本地窗口
- 展示：知识图谱可视化、统计看板、最近活动流
- 可用 D3.js / Cytoscape.js 做图谱渲染

### 3.3 项目结构

```
gmind/
├── src/gmind/              # Python 后端（现有）
│   ├── server.py           # HTTP API（扩展 LLM 端点）
│   ├── llm/                # 新增：LLM 引擎
│   └── ...
│
├── gmind-macos/            # 新增：SwiftUI 项目
│   ├── GMind/              # Xcode 项目
│   │   ├── App.swift
│   │   ├── MenuBarView.swift
│   │   ├── QuickAddView.swift
│   │   ├── QuickSearchView.swift
│   │   ├── SettingsView.swift
│   │   ├── DashboardView.swift
│   │   ├── GMindAPI.swift       # HTTP 客户端
│   │   └── KeyboardShortcuts.swift
│   ├── GMind.xcodeproj/
│   └── README.md
│
└── ...
```

### 3.4 Swift ↔ Python 通信

```swift
// GMindAPI.swift —— Swift HTTP 客户端
class GMindAPI {
    static let shared = GMindAPI()
    var baseURL = "http://127.0.0.1:8765"
    
    func add(content: String, title: String?, source: String?, autoExtract: Bool) async throws {
        // POST /add
    }
    
    func search(query: String, topK: Int = 5) async throws -> [SearchResult] {
        // GET /search?q=...&k=5
    }
    
    func ask(question: String, contextSlugs: [String]?) async throws -> String {
        // POST /ask  ← 新增 LLM 端点
    }
    
    func stats() async throws -> Stats {
        // GET /stats
    }
}
```

菜单栏启动时自动：
1. 检查 `gmind serve` 是否运行
2. 未运行则自动启动（`Process("gmind", ["serve"])`）
3. 运行后连接 HTTP API

---

## 四、内置 LLM 引擎

这是最大的架构变化。GMind 从"不碰 LLM"变成"LLM 是核心能力"。

### 4.1 设计原则

1. **可配置 Provider**：本地优先（隐私），远程为辅（能力）
2. **推理可缓存**：相同输入命中缓存，不重复调用
3. **结果可审计**：所有 LLM 输出存入 `page_history`，可追踪可回滚
4. **渐进式增强**：不强制开启，用户可按需启用各功能

### 4.2 LLM Provider 架构

```python
# src/gmind/llm/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

class LLMProvider(Protocol):
    """LLM Provider 协议 —— 任何实现了这个接口的都可以接入"""
    
    def chat(self, messages: list[dict], temperature: float = 0.7) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def is_available(self) -> bool: ...


@dataclass
class OllamaProvider:
    """本地 Ollama 模型"""
    model: str = "qwen2.5:7b"
    base_url: str = "http://localhost:11434"
    
@dataclass
class OpenAIProvider:
    """OpenAI / SiliconFlow / 任何兼容 API"""
    api_key: str
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"


class LLMEngine:
    """LLM 引擎 —— 统一入口"""
    
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.cache = LLMCache()  # 基于 SQLite 的本地缓存
    
    def chat(self, messages: list[dict], **kwargs) -> str:
        cache_key = self._hash(messages, kwargs)
        if cached := self.cache.get(cache_key):
            return cached
        result = self.provider.chat(messages, **kwargs)
        self.cache.set(cache_key, result)
        return result
```

### 4.3 配置扩展

`~/.gmind/config.toml` 新增 LLM 配置段：

```toml
database_url = "postgresql://..."
node_name = "home"

# Embedding 保持不变
embedding_api_key = "sk-..."
embedding_model = "BAAI/bge-m3"
embedding_base_url = "https://api.siliconflow.cn/v1"

# ── 新增：LLM 配置 ──
[llm]
provider = "ollama"  # "ollama" | "openai" | "siliconflow"

[llm.ollama]
base_url = "http://localhost:11434"
model = "qwen2.5:7b"
# 可选：推理参数
temperature = 0.3

[llm.openai]
api_key = "sk-..."
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"

[llm.features]
auto_extract = true      # 添加笔记时自动提取实体和关系
auto_summarize = true    # 自动生成摘要和标签
auto_link = true         # 自动发现语义关联（非 wikilink）
query_with_reasoning = true  # query 命令启用 LLM 增强
smart_merge = true       # 合并冲突时自动判断
```

### 4.4 LLM 功能模块

#### A. 自动知识提取 (`llm/extract.py`)

添加笔记时自动：

```python
def extract_entities(content: str, engine: LLMEngine) -> list[Entity]:
    """从笔记内容中提取命名实体"""
    prompt = f"""
    从以下笔记中提取所有实体（人物、公司、产品、概念、地点等）。
    对每个实体，给出：名称、类型、一句话描述。
    只返回 JSON 数组，不要其他文字。
    
    笔记内容：
    {content[:2000]}
    """
    # 返回: [{"name": "向量数据库", "type": "concept", "description": "..."}, ...]

def extract_relations(content: str, existing_entities: list[str], engine: LLMEngine) -> list[Relation]:
    """提取实体之间的关系"""
    # 返回: [{"from": "向量数据库", "to": "pgvector", "relation": "基于"}, ...]
```

**效果**：添加一篇笔记后，GMind 自动：
1. 提取实体 → 生成对应 `pages`（type=entity）
2. 提取关系 → 写入 `edges` 表
3. 原有 `[[wikilink]]` 保留，语义关联作为补充

#### B. 语义关联发现 (`llm/enrich.py`)

```python
def find_semantic_links(slug: str, engine: LLMEngine, top_k: int = 5) -> list[LinkSuggestion]:
    """
    找到与给定页面语义相关但尚未建立链接的其他页面。
    不依赖 wikilink，而是基于内容语义相似度 + LLM 判断。
    """
    # 1. 向量搜索找到 top 20 候选
    # 2. LLM 逐一判断："这两篇笔记是否真正相关？关系是什么？"
    # 3. 返回高置信度的关联建议
```

#### C. LLM 增强查询 (`llm/reason.py`)

当前 `gmind query` 只是向量搜索返回原始结果。增强后：

```python
def reasoned_query(question: str, engine: LLMEngine) -> str:
    """
    1. 向量搜索检索相关页面
    2. 构建上下文（页面内容摘要）
    3. LLM 基于上下文回答问题
    4. 回答中嵌入 [[slug]] 引用
    """
    context = retrieve_relevant_pages(question, top_k=8)
    
    prompt = f"""
    基于以下知识库内容，回答用户问题。
    引用相关页面时使用 [[slug]] 格式。
    如果不确定，明确说明。
    
    知识库内容：
    {format_context(context)}
    
    用户问题：{question}
    """
    
    return engine.chat([{"role": "user", "content": prompt}])
```

#### D. 智能合并 (`llm/merge.py`)

```python
def smart_merge(slug: str, draft: str, published: str, engine: LLMEngine) -> MergeResult:
    """
    当 sync 检测到冲突时，LLM 分析两个版本：
    - 哪些是新增内容（应该保留）
    - 哪些是删除内容（是否误删）
    - 哪些段落存在矛盾（需要人工判断）
    
    返回：合并后的文本 + 冲突标记 + 置信度评分
    """
```

#### E. 自动摘要与标签 (`llm/summarize.py`)

```python
def auto_summarize(content: str, engine: LLMEngine) -> Summary:
    """生成：一句话摘要、3-5 个标签、关键要点"""
    
def suggest_title(content: str, engine: LLMEngine) -> str:
    """如果用户没给标题，自动生成"""
```

### 4.5 新增的 HTTP API 端点

```python
# server.py 新增路由

async def ask_endpoint(request: Request) -> JSONResponse:
    """POST /ask —— LLM 增强问答"""
    data = await request.json()
    question = data.get("question", "")
    top_k = data.get("top_k", 8)
    
    # 1. 向量检索
    # 2. LLM 推理
    # 3. 返回答案 + 引用
    return JSONResponse({
        "answer": "...",
        "sources": [{"slug": "...", "title": "...", "relevance": 0.95}],
        "reasoning_trace": "..."  # 可选：推理链
    })

async def enrich_endpoint(request: Request) -> JSONResponse:
    """POST /enrich —— 对指定页面做知识增强"""
    # 提取实体、关系、摘要、标签
    # 返回新增的内容

async def suggest_links_endpoint(request: Request) -> JSONResponse:
    """GET /suggest-links?slug=... —— 语义关联建议"""
    # 返回建议建立的新边

async def stats_llm_endpoint(request: Request) -> JSONResponse:
    """GET /stats/llm —— LLM 使用统计"""
    # 调用次数、缓存命中率、Token 消耗
```

---

## 五、数据模型扩展

### 5.1 `pages` 表新增列

```sql
-- 新增：LLM 生成的结构化数据
ALTER TABLE pages ADD COLUMN summary TEXT;           -- 一句话摘要
ALTER TABLE pages ADD COLUMN tags TEXT[];            -- 自动标签
ALTER TABLE pages ADD COLUMN entities JSONB;         -- 提取的实体 [{name, type}]
ALTER TABLE pages ADD COLUMN llm_enriched BOOLEAN DEFAULT FALSE;  -- 是否已 LLM 增强
ALTER TABLE pages ADD COLUMN auto_extracted BOOLEAN DEFAULT FALSE; -- 实体是否自动提取
```

### 5.2 新增 `llm_calls` 表（审计追踪）

```sql
CREATE TABLE llm_calls (
    id SERIAL PRIMARY KEY,
    request_id TEXT UNIQUE NOT NULL,    -- 去重键
    function_name TEXT NOT NULL,        -- extract / reason / summarize / merge
    input_hash TEXT NOT NULL,           -- 输入内容哈希
    input_preview TEXT,                 -- 输入前 200 字（调试）
    output_preview TEXT,                -- 输出前 200 字
    provider TEXT NOT NULL,             -- ollama / openai
    model TEXT NOT NULL,
    tokens_prompt INT,
    tokens_completion INT,
    latency_ms INT,
    cached BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.3 `edges` 表增强

```sql
-- 已有：link_type = 'related'
-- 新增类型：
--   'semantic'    -- LLM 发现的语义关联
--   'mentions'    -- 页面 A 提到了实体 B
--   'derived_from' -- 派生关系
--   'contradicts' -- 矛盾关系（高阶功能）

ALTER TABLE edges ADD COLUMN confidence FLOAT DEFAULT 1.0;  -- 关联置信度 (0-1)
ALTER TABLE edges ADD COLUMN source TEXT DEFAULT 'manual';    -- manual / llm_extract / semantic_search
ALTER TABLE edges ADD COLUMN llm_reason TEXT;                 -- LLM 为什么建立这个关联
```

---

## 六、实施路线图

### Phase 1: LLM 引擎骨架（2-3 天）

- [ ] 创建 `src/gmind/llm/` 包
- [ ] 实现 `engine.py` —— Provider 协议 + Ollama/OpenAI 适配
- [ ] 实现 `cache.py` —— SQLite 本地缓存
- [ ] 扩展 `config.py` —— 读取 `[llm]` 配置段
- [ ] 扩展 `server.py` —— 新增 `/ask` 端点
- [ ] 更新 `pyproject.toml` —— 添加 LLM 相关依赖（可选）

### Phase 2: 知识提取（2-3 天）

- [ ] 实现 `llm/extract.py` —— 实体/关系提取
- [ ] 实现 `llm/summarize.py` —— 摘要/标签
- [ ] 修改 `add.py` —— 添加 `auto_extract` 选项
- [ ] 扩展数据库 schema —— `summary`, `tags`, `entities` 列
- [ ] CLI 新增：`gmind enrich <slug>` —— 手动触发知识增强
- [ ] CLI 新增：`gmind ask "question"` —— LLM 问答

### Phase 3: Mac 菜单栏应用（3-5 天）

- [ ] 创建 `gmind-macos/` SwiftUI 项目
- [ ] 实现状态栏图标 + 菜单
- [ ] 实现 Quick Add（全局快捷键）
- [ ] 实现 Quick Search（实时向量搜索）
- [ ] 实现 Dashboard（WebView + 统计）
- [ ] 自动启动/管理 `gmind serve` 进程
- [ ] 打包为 `.app` + 签名（如果可能）

### Phase 4: 深度集成（3-5 天）

- [ ] 语义关联发现 (`llm/enrich.py`)
- [ ] 智能合并 (`llm/merge.py`)
- [ ] 图谱可视化（Dashboard 中的 D3.js 图谱）
- [ ] Chrome Extension 升级 —— 也支持 LLM 自动提取
- [ ] LLM 审计看板（调用统计、缓存命中率）

### Phase 5: 打磨（持续）

- [ ] 本地模型一键安装脚本（`./install-ollama.sh`）
- [ ] 推理结果质量评估（用户反馈循环）
- [ ] 缓存预热策略
- [ ] 文档更新 + 视频演示

---

## 七、关键技术决策

### 7.1 本地模型 vs 远程 API

| 场景 | 推荐 | 理由 |
|------|------|------|
| **日常记录** | Ollama qwen2.5:7b | 快、免费、隐私 |
| **深度问答** | GPT-4o / DeepSeek | 能力强、理解深 |
| **批量处理** | 本地模型 | 避免 API 费用和限流 |
| **首次体验** | 远程 API | 零配置，即用即走 |

**默认配置**：
- 优先检测本地 Ollama，有则默认用本地
- 无本地模型则引导用户配置远程 API
- 不同功能可用不同模型（轻量任务用本地，复杂任务用远程）

### 7.2 缓存策略

```python
# ~/.gmind/llm_cache.sqlite
# key = hash(provider + model + messages_json)
# value = {response, created_at, usage}
# TTL = 7 days（可配置）
```

同一篇笔记的相同 LLM 请求应该命中缓存。例如：
- 用户先 `gmind add "..." --auto-extract`
- 然后再 `gmind enrich <slug>`
- 如果内容没变，第二次应直接返回缓存结果

### 7.3 向后兼容

- LLM 功能全部可选，默认关闭
- 现有 CLI 命令行为不变（`query` 依然是纯检索）
- 新增命令/参数来实现 LLM 功能，不破坏旧接口
- Agent-First 模式保留：LLM 开启时 GMind 更智能，关闭时就是原来的 GMind

---

## 八、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 本地模型推理慢 | 高 | 中 | 异步处理 + 缓存 + 可降级到远程 |
| LLM 输出质量不稳定 | 中 | 中 | 提示词工程 + 结果校验 + 用户反馈 |
| SwiftUI 开发维护成本 | 中 | 低 | 保持薄客户端，逻辑全在 Python 后端 |
| 架构复杂度上升 | 高 | 中 | 模块化设计，LLM 层可整体移除 |
| Token/API 费用 | 低 | 低 | 缓存 + 本地模型优先 + 用量统计 |

---

## 九、竞品对标

| 产品 | GMind 差异点 |
|------|-------------|
| **Obsidian** | 我们不只是一个编辑器，而是主动理解你的知识 |
| **Notion AI** | 数据完全本地/自托管，LLM 可离线运行 |
| **Mem.ai** | 开源、可扩展、有知识图谱 |
| **Fabric** | 更聚焦个人知识管理，而非通用 AI 管道 |
| **Zotero** | 不只是文献管理，是通用知识库 |

**一句话定位**：
> GMind = 本地优先的 Obsidian + 自动知识化的 Mem.ai + 开源可扩展的架构

---

## 十、下一步建议

如果你决定开干，我建议按这个顺序：

1. **今天就做**：启动 Phase 1，先搭 LLM 引擎骨架。用一个下午让 `gmind ask "xxx"` 能跑起来。
2. **本周内**：Phase 2，知识提取。让添加笔记时自动抽实体，看看效果。
3. **下周**：Phase 3，SwiftUI 菜单栏。先做出能用的 Quick Add 和 Search。
4. **再下周**：深度打磨，发布 v3.0。

要不要我现在就开始写 Phase 1 的代码？
