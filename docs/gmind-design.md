# gmind 知识处理流程与数据表设计

> 日期：2026-05-16
> 状态：设计草案

## 1. 核心模型

gmind 是一个主动吸取知识的个人 AI 知识库。

它的主存储是数据库，向量索引用于语义召回，LLM 负责阅读资料、抽取结构、建立关系、推理结论、生成后续任务。

核心数据对象有 8 类：

```text
sources        原始资料
source_chunks  资料切片
entities       实体 / 页面对象
claims         断言
events         资料中发生的真实事件
relations      对象之间的关系
tasks          待处理问题和主动动作
logs           gmind 的系统操作日志
```

这 8 张表的职责可以概括为：

```text
资料进入 sources
资料被切成 source_chunks
LLM 从资料中抽取 entities / claims / events
LLM 用 relations 把它们连接起来
LLM 根据缺口、冲突和目标生成 tasks
gmind 用 logs 记录自己做过什么
```

## 2. 资料吸取流程

资料吸取流程，也就是 ingest pipeline，是 gmind 的核心流程。

```text
输入资料
  ↓
保存 source
  ↓
切分 source_chunks + embedding
  ↓
LLM 阅读 chunk
  ↓
抽取 entities
  ↓
抽取 claims
  ↓
抽取 events
  ↓
建立 relations
  ↓
推理新的 claims
  ↓
生成 tasks
  ↓
写入 logs
```

### 2.1 保存资料

用户提供资料，或者 gmind 主动搜索到资料后，先进入 `sources`。

资料可以是：

- 网页
- PDF
- Markdown
- 聊天记录
- 会议纪要
- 合同
- 付款记录
- 项目文档
- 用户手写笔记

这一阶段只保存原始证据，不急着判断。

### 2.2 切片和向量化

长资料会被切成 `source_chunks`。

每个 chunk 保存原文片段，并生成 embedding。

向量索引用于：

- 根据问题召回相关片段
- 给 claim / event 定位证据
- 避免每次查询都重读完整资料

### 2.3 抽取实体

LLM 从资料中识别实体，写入 `entities`。

实体是 gmind 的页面对象。每个实体都可以聚合资料、事件、断言、关系和任务，生成一个类似 wiki 的页面。

实体可以是：

- 人
- 公司
- 项目
- 合同
- 文档
- 产品
- 工具
- 技术概念
- 研究方向
- 业务流程

### 2.4 抽取断言

LLM 从资料中抽取 claim，写入 `claims`。

claim 是一句可以被引用、支持、反驳、更新的陈述。

例如：

```text
合同约定首付款应在合同签署后 5 日内支付。
传统 RAG 通常不会持续积累长期综合理解。
LLM Wiki 会维护一个持续更新的中间知识层。
```

claim 不只包含事实，也可以包含观点、假设、总结和结论。

### 2.5 抽取事件

LLM 从资料中抽取真实世界事件，写入 `events`。

event 必须表达“什么时候，谁，对什么，发生了什么”。

例如：

```text
2026-03-01 项目 A 签署合同。
2026-03-05 项目 A 收到首付款。
2026-04-10 客户提出需求变更。
```

event 用于处理时间线、先后顺序、项目进度、合同履约等问题。

### 2.6 建立关系

LLM 用 `relations` 把对象连接起来。

例如：

```text
claim --mentions--> entity
event --involves--> entity
claim --supported_by--> source_chunk
claim --derived_from--> event
task --about--> entity
entity --related_to--> entity
```

relations 是 gmind 从“很多条记录”变成“知识网络”的关键。

### 2.7 推理新的断言

LLM 可以基于多个 claims / events / sources 推理出新的 claim。

这类 claim 的 `origin` 应该是 `inferred`。

例如：

```text
event:
2026-03-01 项目 A 签署合同。

event:
2026-03-05 项目 A 收到首付款。

inferred claim:
项目 A 是先签合同后付款。
```

所谓 insight / 洞察，不单独建表，本质上就是这类 inferred claim。

### 2.8 生成任务

如果 LLM 发现缺口、冲突、待验证点或后续研究方向，就写入 `tasks`。

例如：

```text
确认项目 A 是否还有尾款未支付。
查找合同 001 是否存在补充协议。
验证“项目 A 已完成验收”是否有来源支持。
继续搜索 AI memory 相关的新资料。
```

问题不单独建表。问题是 task 的一种。

### 2.9 写入日志

gmind 每完成一次系统动作，都写入 `logs`。

例如：

```text
吸取了一份合同 PDF。
创建了 3 个 events。
创建了 5 条 claims。
关闭了任务“确认项目 A 是否收到首付款”。
```

logs 只记录 gmind 做过什么，不记录真实世界发生了什么。

## 3. 查询流程

查询时，gmind 不只做向量搜索。

它应该结合结构化数据和向量召回：

```text
用户问题
  ↓
识别相关 entity / claim / event / task
  ↓
必要时用向量召回 source_chunks
  ↓
读取结构化对象和证据片段
  ↓
LLM 综合回答
  ↓
必要时生成新的 claim 或 task
```

例如用户问：

```text
项目 A 是先签合同，还是先付款？
```

gmind 应该优先查 `events`：

```text
related_entity = 项目 A
event_type in contract_signed / payment_received
order by occurred_at
```

然后回答：

```text
项目 A 是先签合同，再收到首付款。

时间线：
- 2026-03-01 签署合同
- 2026-03-05 收到首付款
```

如果这个结论之前没有保存，可以生成一条 inferred claim：

```text
项目 A 是先签合同后付款。
```

## 4. 实体页面生成流程

gmind 的 wiki 页面不是主存储，而是由实体动态生成的视图。

以“项目 A”为例，页面可以这样生成：

```text
# 项目 A

## 概览
来自 entity.description 和 inferred claims

## 时间线
来自 events，按 occurred_at 排序

## 关键断言
来自 claims

## 当前结论
来自 origin = inferred 的 claims

## 相关资料
来自 sources / source_chunks

## 待处理任务
来自 tasks

## 相关实体
来自 relations
```

页面生成流程：

```text
输入 entity_id
  ↓
读取 entity
  ↓
读取相关 events
  ↓
读取相关 claims
  ↓
读取相关 tasks
  ↓
读取相关 sources
  ↓
读取相关 entities
  ↓
LLM 或模板生成页面
```

这种方式让 gmind 保持数据库结构化，同时保留 wiki 的可读性。

## 5. 主动研究流程

gmind 的主动性主要来自 `tasks`。

一个 task 可以驱动 gmind 主动找资料、验证 claim、补齐时间线、解决冲突。

```text
task
  ↓
规划搜索或读取动作
  ↓
获得 source
  ↓
执行 ingest pipeline
  ↓
更新 entities / claims / events / relations
  ↓
生成新的 inferred claims
  ↓
关闭旧 task 或生成新 task
  ↓
写入 logs
```

例如：

```text
task:
确认项目 A 是否已经收到首付款。

gmind 动作:
查找银行流水和项目资料。

event:
2026-03-05 项目 A 收到首付款。

claim:
项目 A 已收到首付款。

log:
完成任务“确认项目 A 是否已经收到首付款”。
```

## 6. 表设计

### 6.1 sources

`sources` 存原始资料。

#### 存什么

- 原文
- 标题
- URL
- 作者
- 发布时间
- 抓取时间
- 来源类型
- 可信度
- 资料元数据

#### 不存什么

- 不存切片，切片放 `source_chunks`
- 不存抽取出的断言，断言放 `claims`
- 不存真实事件，事件放 `events`
- 不存系统操作记录，操作记录放 `logs`

#### 谁产生

- 用户手动添加资料
- gmind 主动搜索发现资料
- 其他任务导入资料

#### 谁使用

- ingest pipeline
- source_chunks 生成流程
- claims / events 的证据追溯
- 查询回答时的引用来源

#### 建议字段

```text
id
title
source_type
url
author
published_at
captured_at
raw_text
trust_score
metadata_json
created_at
updated_at
```

### 6.2 source_chunks

`source_chunks` 存资料切片。

#### 存什么

- source 的局部文本
- chunk 在 source 中的位置
- embedding
- chunk 级元数据

#### 不存什么

- 不存完整资料，完整资料放 `sources`
- 不存 LLM 总结，LLM 总结应作为 `claims`
- 不存业务事件，业务事件放 `events`

#### 谁产生

- source 保存后，由切片流程自动产生

#### 谁使用

- 向量检索
- LLM 抽取 entities / claims / events
- claim / event 的证据定位
- 查询时召回相关上下文

#### 建议字段

```text
id
source_id
chunk_index
chunk_text
embedding
metadata_json
created_at
```

### 6.3 entities

`entities` 存实体，也就是页面级对象。

#### 存什么

- 人
- 公司
- 项目
- 合同
- 文档
- 产品
- 工具
- 概念
- 研究方向
- 流程

#### 不存什么

- 不存关于实体的所有事实，事实放 `claims`
- 不存实体发生过的时间线，时间线放 `events`
- 不存实体之间的连接，连接放 `relations`
- 不存待处理问题，问题放 `tasks`

#### 谁产生

- LLM 从 source_chunks 中抽取
- 用户手动创建
- gmind 在推理或任务执行中发现新实体

#### 谁使用

- 实体页面生成
- relations 连接
- tasks 关联
- events 关联
- claims 归属和引用

#### 建议字段

```text
id
name
entity_type
description
canonical_name
aliases_json
status
metadata_json
created_at
updated_at
```

#### 示例

```text
name = 项目 A
entity_type = project

name = 合同 001
entity_type = contract

name = RAG
entity_type = concept

name = gmind 产品设计
entity_type = topic
```

### 6.4 claims

`claims` 存断言。

断言是一句可以被引用、支持、反驳、更新的陈述。

#### 存什么

- 从资料直接抽取出的事实
- 从资料直接抽取出的观点
- 用户明确表达的判断
- LLM 基于多个 claims / events 推理出的结论
- LLM 对实体的总结

#### 不存什么

- 不存原文全文，原文放 `sources`
- 不存资料切片，切片放 `source_chunks`
- 不存带明确时间的真实世界事件，事件放 `events`
- 不存待执行动作，动作放 `tasks`

#### 谁产生

- LLM 从 source_chunks 中抽取
- 用户直接表达
- LLM 根据 claims / events / sources 推理生成

#### 谁使用

- 查询回答
- 实体页面的关键事实和当前结论
- relations 建立证据链
- tasks 验证或反驳断言

#### 建议字段

```text
id
text
claim_type
origin
status
confidence
source_id
source_chunk_id
metadata_json
created_at
updated_at
```

#### claim_type

```text
fact         事实
opinion      观点
hypothesis   假设
conclusion   结论
summary      总结
```

#### origin

```text
extracted     从资料直接抽取
inferred      LLM 推理得出
user_stated   用户直接表达
```

#### 示例

```text
extracted fact:
合同约定首付款应在合同签署后 5 日内支付。

extracted opinion:
LLM Wiki 比传统 RAG 更适合长期知识积累。

inferred conclusion:
项目 A 是先签合同后付款。

user_stated opinion:
gmind 应该是一个主动吸取知识的知识库。
```

### 6.5 events

`events` 存从资料中提取出的真实世界事件。

注意：`events` 不是系统日志。gmind 自己做过什么，放在 `logs`。

#### 存什么

- 签署合同
- 收到付款
- 支付款项
- 召开会议
- 提出需求变更
- 项目启动
- 项目暂停
- 项目验收
- 发票开具
- 审批通过

#### 不存什么

- 不存 gmind 的系统动作，系统动作放 `logs`
- 不存普通观点，观点放 `claims`
- 不存没有时间含义的标签或分类
- 不存长期状态本身，状态判断可以放 `claims`

#### 谁产生

- LLM 从 source_chunks 中抽取
- 用户手动录入事件
- gmind 根据可信资料补全事件

#### 谁使用

- 时间线查询
- 项目进度页面
- 合同履约判断
- inferred claims 推理
- tasks 验证和关闭

#### 建议字段

```text
id
event_type
title
description
occurred_at
occurred_at_precision
subject_entity_id
object_entity_id
related_entity_id
source_id
source_chunk_id
confidence
metadata_json
created_at
updated_at
```

#### 示例

```text
event_type = contract_signed
title = 项目 A 签署合同
occurred_at = 2026-03-01
related_entity_id = 项目 A

event_type = payment_received
title = 项目 A 收到首付款
occurred_at = 2026-03-05
related_entity_id = 项目 A
```

### 6.6 relations

`relations` 存对象之间的关系。

它是一张统一关系表，用来连接 source、chunk、entity、claim、event、task 等对象。

#### 存什么

- claim 提到了哪个 entity
- event 涉及哪个 entity
- claim 由哪个 source_chunk 支持
- claim 和 claim 是否冲突
- inferred claim 从哪些 events 推理而来
- task 关联哪个 entity
- entity 和 entity 之间有什么关系

#### 不存什么

- 不存对象本身
- 不存长文本内容
- 不替代具体表中的结构化字段

#### 谁产生

- LLM ingest 时自动建立
- LLM 推理时建立
- 用户手动修正
- 系统在合并实体或更新证据链时建立

#### 谁使用

- 实体页面生成
- 查询推理
- 证据追溯
- 冲突检测
- 知识图谱遍历

#### 建议字段

```text
id
subject_type
subject_id
predicate
object_type
object_id
source_id
confidence
metadata_json
created_at
updated_at
```

#### 示例

```text
claim --mentions--> entity
event --involves--> entity
claim --supported_by--> source_chunk
claim --contradicts--> claim
claim --derived_from--> event
task --about--> entity
entity --related_to--> entity
```

### 6.7 tasks

`tasks` 存 gmind 要处理的问题和主动动作。

问题不单独建表。问题是 task 的一种。

#### 存什么

- 待研究问题
- 待验证断言
- 待寻找资料
- 待抽取事件
- 待解决冲突
- 待更新实体总结
- 待监控实体或主题

#### 不存什么

- 不存已经确认的事实，事实放 `claims`
- 不存真实世界事件，事件放 `events`
- 不存系统日志，日志放 `logs`
- 不存完整资料，资料放 `sources`

#### 谁产生

- LLM 在 ingest 时发现缺口
- LLM 在查询时发现问题
- LLM 在冲突检测时生成
- 用户直接创建任务
- 定时监控策略创建任务

#### 谁使用

- 主动搜索流程
- 验证流程
- 冲突解决流程
- gmind 的任务队列
- logs 记录执行结果

#### 建议字段

```text
id
task_type
title
description
status
priority
related_entity_id
source_id
claim_id
event_id
metadata_json
created_at
updated_at
due_at
completed_at
```

#### task_type

```text
research_question   研究问题
verify_claim        验证断言
find_source         寻找资料
extract_events      抽取事件
resolve_conflict    解决冲突
summarize_entity    更新实体总结
monitor_entity      监控实体
```

#### 示例

```text
task_type = research_question
title = 项目 A 是先签合同还是先付款？
related_entity_id = 项目 A

task_type = verify_claim
title = 验证“项目 A 已完成验收”是否有来源支持
claim_id = claim_project_a_accepted
```

### 6.8 logs

`logs` 存 gmind 的系统操作记录。

#### 存什么

- gmind 吸取了什么资料
- 创建了哪些实体、断言、事件
- 建立了多少关系
- 生成了哪些任务
- 完成了哪些任务
- 查询或维护过程中发生了什么系统动作

#### 不存什么

- 不存真实世界事件，真实事件放 `events`
- 不存业务事实，业务事实放 `claims`
- 不存原始资料，原始资料放 `sources`

#### 谁产生

- ingest pipeline
- 主动任务执行流程
- 查询流程
- 实体页面更新流程
- 系统维护流程

#### 谁使用

- 回溯 gmind 做过什么
- 调试 ingest 结果
- 展示知识库演化历史
- 判断最近处理过哪些资料和任务

#### 建议字段

```text
id
action
title
summary
actor
object_type
object_id
metadata_json
created_at
```

#### 示例

```text
action = source_ingested
title = 吸取合同 001
summary = 创建了 2 个 events、4 条 claims、3 个 entities 和 9 条 relations。

action = task_completed
title = 完成任务：确认项目 A 是否收到首付款
summary = 根据银行流水确认项目 A 于 2026-03-05 收到首付款。
```

## 7. 表之间的关系

核心关系如下：

```text
source 1 -> many source_chunks
source 1 -> many claims
source 1 -> many events

entity 1 -> many claims
entity 1 -> many events
entity 1 -> many tasks

claim many -> many entities
event many -> many entities
task many -> many entities

relations 连接任意对象
logs 记录系统动作
```

更具体地说：

```text
sources 是证据入口
source_chunks 是检索入口
entities 是页面入口
claims 是判断入口
events 是时间线入口
relations 是图谱入口
tasks 是主动行动入口
logs 是系统历史入口
```

## 8. 合同和付款顺序示例

用户问题：

```text
项目 A 是先签合同，还是先付款？
```

资料进入后，gmind 抽取：

```text
entity:
项目 A

event:
项目 A 签署合同
occurred_at = 2026-03-01

event:
项目 A 收到首付款
occurred_at = 2026-03-05

claim:
合同约定首付款应在合同签署后 5 日内支付。
```

查询时，gmind 读取项目 A 的 events：

```text
2026-03-01 contract_signed
2026-03-05 payment_received
```

回答：

```text
项目 A 是先签合同，再收到首付款。
```

同时生成 inferred claim：

```text
项目 A 是先签合同后付款。
```

如果结合合同条款，还可以生成进一步结论：

```text
项目 A 的付款顺序符合合同约定。
```

## 9. 最小心智模型

```text
source   资料从哪里来
chunk    资料中可检索的片段
entity   被讨论的对象，也是 wiki 页面
claim    关于对象的断言，包括 LLM 推理结论
event    资料中发生过的真实事件
relation 对象之间的连接
task     gmind 要解决的问题或要执行的动作
log      gmind 自己做过什么
```

gmind 的目标不是保存更多文档，而是持续把资料转化为：

```text
实体
事件
断言
关系
任务
```

并围绕这些结构主动吸取下一批知识。
