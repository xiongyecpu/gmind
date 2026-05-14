# 知识雷达 — 设计文档

> 全电脑知识自动发现与入库系统

> 状态说明：知识雷达是 Taotie 后端能力的用户侧名称。当前代码已实现扫描、启发式/LLM 分类、黑名单、入库队列、历史记录和 watcher 配置管理；桌面雷达扫描会优先使用已配置的 watcher 文件夹，未配置时使用默认扫描范围；尚未实现独立常驻后台 watcher daemon。`.docx` 可被扫描与预览分类，但正文入库提取尚未接入 `gmind ingest`。

---

## 一、核心流程

```
扫描 → 过滤 → 排队 → 入库
  │       │       │       │
  ▼       ▼       ▼       ▼
遍历文件  LLM判断  用户确认  gmind ingest
遍历目录  隐私识别  实时进度  向量+知识化
```

---

## 二、扫描阶段

### 2.1 文件扫描

**扫描范围：**
- `~/Documents`, `~/Desktop`, `~/Downloads`
- `~/.hermes/sessions`
- `~/.openclaw/agents/*/sessions`
- `~/.claude/projects`
- `~/.kimi/sessions`
- `~/.codex/archived_sessions`
- 微信聊天记录：`~/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/*/Message`

**排除范围（系统目录）：**
- `/System`, `/usr`, `/bin`, `/sbin`
- `~/.cache`, `~/.Trash`, `node_modules`, `.git`
- 已入黑名单的文件

**识别格式（一期）：**
- `.md` — Markdown
- `.docx` — Word 文档
- `.pdf` — PDF
- `.txt` — 纯文本（> 500 字才认为是知识）

### 2.2 文件夹推荐

扫描过程中，自动发现"知识密度高"的文件夹：

| 启发式 | 规则 |
|--------|------|
| 知识文件占比 | 文件夹内 .md/.docx/.pdf 占比 > 30% |
| 文件更新频率 | 30 天内有修改 |
| 文件平均大小 | 平均 > 1KB（排除空文件）|
| 已知模式 | 匹配 `*/笔记/*`, `*/知识库/*`, `*/docs/*` |
| Agent 会话 | 已知路径（.hermes, .openclaw 等）|

**推荐展示：**
```
发现 5 个知识文件夹，是否加入监控？

📁 ~/Documents/笔记            342 个文件  [加入]
📁 ~/.hermes/sessions           891 个文件  [加入]
📁 ~/Projects/gmind/docs         14 个文件  [加入]
📁 ~/.openclaw/agents/main/...   56 个文件  [加入]
📁 ~/Library/Containers/...      247 个文件 [加入]  (微信聊天记录)

[全部加入]  [暂时不加]
```

---

## 三、过滤阶段

### 3.1 隐私过滤器（LLM 推理）

对每个文件的前 1000 字，做快速 LLM 判断：

```python
def classify_file(filepath: str, content_preview: str) -> dict:
    """
    返回:
    {
        "should_ingest": bool,      # 是否入库
        "reason": str,              # 原因
        "privacy_level": str,       # "safe" | "sensitive" | "private"
        "contains_passwords": bool,
        "contains_pii": bool,       # 身份证号、手机号、地址
        "is_knowledge": bool,       # 是否有知识价值
    }
    """
```

**Prompt 设计：**
```
判断以下文件是否适合作为个人知识库存入。

文件路径：{filepath}
内容预览：{content_preview[:1000]}

判断规则：
1. 是否包含密码、密钥、Token、API Key？
2. 是否包含身份证号、手机号、银行卡号等个人隐私？
3. 是否包含公司内部机密或商业敏感信息？
4. 内容是否有知识价值（笔记、文档、文章、思考）？

返回 JSON：
{
    "should_ingest": true/false,
    "reason": "简短说明",
    "privacy_level": "safe" | "sensitive" | "private",
    "contains_passwords": true/false,
    "contains_pii": true/false,
    "is_knowledge": true/false
}
```

### 3.2 黑名单机制

**本地黑名单文件：** `~/.gmind/taotie-blacklist.json`

```json
{
    "version": 1,
    "files": [
        "/Users/neal/.ssh/id_rsa",
        "/Users/neal/密码.txt",
        "/Users/neal/.env"
    ],
    "patterns": [
        "*/.ssh/*",
        "*/.env",
        "*/密码*",
        "*/secret*"
    ],
    "folders": [
        "/Users/neal/.cache"
    ]
}
```

**行为：**
- 用户标记"不入库" → 自动加入黑名单
- 后续扫描自动跳过黑名单文件
- 黑名单可手动编辑
- 支持 `folders` 级别排除（整个文件夹跳过）

---

## 四、入库队列

### 4.1 队列状态

```python
class IngestQueue:
    """入库队列管理器"""

    def __init__(self):
        self.current: FileTask | None = None   # 正在入库
        self.pending: list[FileTask] = []      # 排队中
        self.filtered: list[FileTask] = []     # 已过滤（不入库）
        self.completed: list[FileTask] = []    # 已完成
        self.paused: bool = False
```

### 4.2 入库流程

1. **扫描** → 发现候选文件
2. **过滤** → LLM 判断，标记 `should_ingest`
3. **排队** → 用户确认（默认全部入库，可手动排除）
4. **入库** → 逐个调用 `gmind ingest`
5. **后处理** → 自动向量化 + 知识化

### 4.3 并发控制

- 一次只入库 1 个文件（避免数据库竞争）
- 后台线程执行，不阻塞 UI
- 支持暂停/继续

---

## 五、UI 设计

### 5.1 主面板 — 扫描结果

**标签页：知识文件 / 隐私文件 / 已过滤**

```
┌────────────────────────────────────────────┐
│ 知识雷达                                    │
├────────────────────────────────────────────┤
│                                             │
│  扫描到 1,247 个候选文件                     │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 知识文件  │  │ 隐私文件  │  │  已过滤  │  │
│  │   1189   │  │    12    │  │    46    │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ ☑️ ~/笔记/产品规划.md          12 KB │  │
│  │ ☑️ ~/文档/需求分析.docx        45 KB │  │
│  │ ☑️ ~/PDF/论文.pdf              2 MB │  │
│  │ ☑️ ~/.hermes/session-xxx      156 KB │  │
│  │ ...                                  │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  [查看队列]  [开始入库]                      │
│                                             │
└────────────────────────────────────────────┘
```

- 点击标签页切换文件列表
- 每行文件可勾选/取消勾选（默认全部勾选）
- "不入库"按钮将文件移入已过滤 + 加入黑名单

### 5.2 队列面板 — 实时入库

```
┌────────────────────────────────────────────┐
│ 🍽️ 入库队列                                │
├────────────────────────────────────────────┤
│                                             │
│  正在入库：                                  │
│  ┌──────────────────────────────────────┐  │
│  │ 📄 ~/笔记/产品规划.md                  │  │
│  │ ████████████░░░░░░░░  60%            │  │
│  │ 向量化...                              │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  排队中 (12)：                               │
│  ┌──────────────────────────────────────┐  │
│  │ ☑️ ~/笔记/会议记录.md        [不入库] │  │
│  │ ☑️ ~/文档/需求分析.docx      [不入库] │  │
│  │ ☑️ ~/PDF/论文.pdf            [不入库] │  │
│  │ ☑️ ~/.hermes/session-xxx     [不入库] │  │
│  │ ...                                  │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  已过滤 (5) — 包含隐私内容：                  │
│  │ ⛔ ~/.ssh/id_rsa — 包含密钥            │  │
│  │ ⛔ ~/密码.txt — 包含密码               │  │
│  │ ...                                  │  │
│                                             │
│  [全部入库]  [暂停]  [清空队列]              │
│                                             │
└────────────────────────────────────────────┘
```

### 5.3 监听文件夹

**扫描出来的文件夹默认勾选：**

```
┌────────────────────────────────────────────┐
│ 📁 监听文件夹                               │
├────────────────────────────────────────────┤
│                                             │
│  扫描发现的文件夹（默认已勾选）：              │
│  ☑️ ~/Documents/笔记            342 文件   │
│  ☑️ ~/.hermes/sessions          891 文件   │
│  ☑️ ~/.openclaw/agents/...      56 文件    │
│  ☐ ~/Downloads                  12 文件    │
│                                             │
│  手动添加：                                  │
│  [+ 添加文件夹]                              │
│                                             │
│  扫描周期：                                  │
│  ○ 实时 (FSEvents)                          │
│  ● 每隔 1 小时                              │
│  ○ 每天 凌晨 2:00                           │
│  ○ 每周 周日 凌晨 2:00                       │
│                                             │
│  [保存设置]                                  │
│                                             │
└────────────────────────────────────────────┘
```

### 5.4 导入历史

```
┌────────────────────────────────────────────┐
│ 📜 导入历史                                 │
├────────────────────────────────────────────┤
│                                             │
│  2026-05-12 10:30                          │
│  ├── 📄 产品规划.md  →  pages/product-plan  │
│  ├── 📄 需求分析.docx → pages/requirements   │
│  └── 📄 论文.pdf → pages/paper-2025         │
│                                             │
│  2026-05-11 18:00                          │
│  ├── 📄 会议记录.md → pages/meeting-0511    │
│  └── 📄 hermes-session-xxx → pages/chat-xxx │
│                                             │
│  [清空历史]                                  │
│                                             │
└────────────────────────────────────────────┘
```

**历史存储：** `~/.gmind/taotie-history.json`

---

## 六、技术实现

### 6.1 Python 端（新增 `taotie.py`）

```
src/gmind/taotie/
├── __init__.py
├── scanner.py      # 文件扫描
├── classifier.py   # LLM 隐私分类
├── blacklist.py    # 黑名单管理
├── queue.py        # 入库队列
├── history.py      # 导入历史
└── watcher.py      # 文件夹监听配置
```

### 6.2 CLI 命令

```bash
# 扫描全电脑
gmind taotie scan

# 查看队列
gmind taotie queue

# 开始入库
gmind taotie ingest

# 管理黑名单
gmind taotie blacklist add ~/密码.txt
gmind taotie blacklist list
gmind taotie blacklist remove ~/密码.txt

# 添加监控文件夹
gmind taotie watch ~/Documents/笔记

# 启动后台监听
gmind taotie daemon
```

### 6.3 Electron 桌面端

- 扫描结果展示
- 队列实时状态（HTTP 轮询 / WebSocket）
- 文件详情弹窗
- 黑名单管理

---

## 七、一期范围

| 功能 | 状态 |
|------|------|
| 全电脑文件扫描（md/docx/pdf/txt） | 必须 |
| 文件夹推荐（hermes/openclaw/微信等） | 必须 |
| LLM 隐私过滤（密码/PII/机密） | 必须 |
| 黑名单机制 | 必须 |
| 入库队列 + 实时进度 | 必须 |
| 用户确认（入库/不入库） | 必须 |
| 文件夹监听（FSEvents） | 二期 |
| 后台守护进程 | 二期 |
| WebSocket 实时推送 | 二期 |
