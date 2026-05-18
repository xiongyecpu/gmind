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

查询时应优先读取结构化对象，再用向量检索补充原文证据。

常见查询入口可以分为：

```text
当前事实 / 结论查询  -> claims + relations + source_chunks
时间顺序查询          -> events
冲突查询              -> claims + relations(predicate = contradicts)
历史变化查询          -> claims.status + relations + logs
证据追溯查询          -> relations(predicate = supported_by) -> source_chunks -> sources
开放问题查询          -> tasks
```

为了避免每次查询都手写复杂 join，可以在读取层提供稳定视图或 helper query：

```text
entity_claims_view
通过 relations 读取某个 entity 相关的 claims。

claim_current_view
默认读取 active / disputed / stale claims，排除 superseded / retracted / archived。

claim_conflict_view
读取 disputed claims，以及 claim --contradicts--> claim 的关系。

claim_lineage_view
读取 claim 的 supported_by / contradicts / supersedes / derived_from 等关系。
```

这些读取视图不改变主数据模型，只是把常用查询路径固定下来。

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
embedding_model
embedding_dim
embedding
metadata_json
created_at
```

#### 向量索引实现

第一版建议使用 Postgres + pgvector。

`source_chunks.embedding` 存 pgvector 的 `vector` 类型，维度由 embedding model 决定。

例如：

```text
embedding_model = embedding-model-name
embedding_dim = 1536
embedding = vector(1536)
```

这样 gmind 可以先用结构化条件过滤，再做向量相似度检索。

例如：

```text
source_id in (...)
created_at >= ...
sources.trust_score >= ...
order by embedding <=> query_embedding
```

如果未来数据量大到 pgvector 不够用，可以把向量索引拆到独立向量数据库。但即使拆出去，`source_chunks.id` 仍然应该作为证据锚点。

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
dedupe_key
external_ids_json
merge_status
merged_into_entity_id
metadata_json
created_at
updated_at
```

#### 去重和合并

LLM 多次 ingest 时，可能把同一个现实对象创建成多个 entity。

例如：

```text
项目 A
Project A
A 项目
本项目
客户官网改版项目
```

如果不做去重，同一个对象的 claims、events、tasks 会分散在多个页面里，查询和冲突检测也会漏掉信息。

entity 去重的目标是：

```text
把同一个现实对象收敛到同一个知识节点。
```

去重可以分三步：

```text
候选发现
用 canonical_name、aliases_json、external_ids_json、dedupe_key、名称相似度、embedding 和共同关系找可能重复的 entity。

判定
高置信度时自动确认 same_as / merged_into。
中置信度时生成 task，由用户或 LLM 后续确认。
低置信度时保持分开。

合并
不物理删除旧 entity。
旧 entity 标记为 merged，并通过 merged_into_entity_id 指向 canonical entity。
```

相关关系可以写入 `relations`：

```text
entity --same_as--> entity
entity --merged_into--> entity
entity --not_same_as--> entity
```

查询时，应先把 merged entity resolve 到 canonical entity，再读取相关 claims、events、tasks 和 relations。

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
- relations 建立实体关联和证据链
- tasks 验证或反驳断言

#### 建议字段

```text
id
text
claim_type
origin
status
confidence
as_of
valid_from
valid_to
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

#### status

```text
active        当前有效
disputed      存在冲突，待确认
superseded    已被新 claim 替代
retracted     确认错误，撤回
stale         依赖资料变化，需要重算
archived      历史保留
```

#### 与 entity 的关联

`claims` 表不直接保存 `entity_id`。

claim 和 entity 的关联统一走 `relations`：

```text
claim --about--> entity
claim --mentions--> entity
```

其中：

```text
about
表示这条 claim 主要是在说哪个 entity，适合实体页面和核心事实查询。

mentions
表示这条 claim 文本中提到了哪个 entity，但不一定是主语义对象。
```

这样可以避免在 `claims` 表和 `relations` 表里同时维护 entity 关系。

为了提高读取效率，查询层可以提供 `entity_claims_view`：

```text
entity_claims_view(entity_id)
  -> relations where object_type = entity and object_id = entity_id
  -> predicate in about / mentions
  -> join claims
```

也就是说：

```text
写入层：claim/entity 关系全部写 relations。
读取层：用 view 或 helper query 封装常用 join。
```

#### 来源和溯源

`source_id` 和 `source_chunk_id` 只表示直接来源。

它们主要适用于：

```text
origin = extracted
origin = user_stated
```

对于 `origin = inferred` 的 claim，来源通常不是单个 source，而是多个 claims、events 或 source_chunks。

这类溯源链应通过 `relations` 表表达：

```text
inferred claim --derived_from--> claim
inferred claim --derived_from--> event
inferred claim --supported_by--> source_chunk
```

如果 inferred claim 依赖的 claim 或 event 发生变化，应将 inferred claim 标记为 `stale`，并生成重新评估的 task。

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
- claim 是否替代了另一个 claim
- inferred claim 从哪些 claims / events 推理而来
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
claim --about--> entity
claim --mentions--> entity
event --involves--> entity
claim --supported_by--> source_chunk
claim --contradicts--> claim
claim --supersedes--> claim
claim --derived_from--> event
claim --derived_from--> claim
task --about--> entity
entity --related_to--> entity
entity --same_as--> entity
entity --merged_into--> entity
entity --not_same_as--> entity
```

#### 常用 predicate 边界

```text
about
表示主体对象主要关于另一个对象。
例如 claim --about--> entity。

mentions
表示文本中提到另一个对象。
例如 claim --mentions--> entity。

supported_by
表示主体对象有直接证据支持。
例如 claim --supported_by--> source_chunk。

derived_from
表示主体对象由其他结构化对象推理得出。
例如 inferred claim --derived_from--> event。

contradicts
表示两个 claim 互相冲突。
发现该关系后，相关 claim 通常应标记为 disputed，并生成 resolve_conflict task。

supersedes
表示一个新 claim 替代旧 claim。
旧 claim 通常应标记为 superseded。

same_as / merged_into / not_same_as
用于 entity 去重和合并。
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
scheduled_at
next_run_at
locked_at
locked_by
attempt_count
last_error
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

#### status

```text
open        等待执行
scheduled   已安排未来执行
running     正在执行
blocked     被外部条件阻塞
completed   已完成
failed      执行失败
cancelled   已取消
```

#### 调度方式

`tasks` 表只负责保存任务状态，不负责自己执行任务。

gmind runtime 中应有一个 worker / scheduler 负责调度。

第一版可以使用轮询：

```text
定期扫描 status in open / scheduled 的 tasks
筛选 next_run_at <= now 或 next_run_at 为空
按 priority desc, due_at asc, created_at asc 排序
取一批任务执行
执行前写入 locked_at / locked_by
失败时增加 attempt_count 并记录 last_error
```

任务可以由三类触发产生：

```text
event-driven
新 source ingest 后触发 extract / verify / resolve_conflict。

scheduled
定时扫描 open tasks，执行主动研究、监控和复查。

user-triggered
用户查询或手动要求时触发相关 task。
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

其中 claim 与 entity 的关联统一通过 `relations` 表表达。

event / task 可以保留高频查询字段，例如 `related_entity_id`、`claim_id`、`event_id`，但完整图谱关系仍然可以写入 `relations`。

例如：

```text
claim --about--> entity
event --involves--> entity
task --about--> entity
```

查询实体页面时，对 claim 使用读取视图封装 relations 查询。

例如：

```text
entity_claims_view
```

### 7.1 claim 更新、冲突和历史变化

claim 的原始含义应尽量稳定。

新资料进入后，优先更新证据、状态、置信度和关系；必要时创建新的 claim，而不是直接覆盖旧 claim。

常见更新方式：

```text
新资料支持已有 claim
增加 claim --supported_by--> source_chunk，提高 confidence。

新资料反驳已有 claim
新建相反 claim，建立 claim --contradicts--> claim。
相关 claim 标记为 disputed，并生成 resolve_conflict task。

新资料让 claim 过期
新建 active claim，旧 claim 标记为 superseded。
建立 new claim --supersedes--> old claim。

新资料让 claim 更精确
新建更精确 claim，旧 claim 标记为 superseded。

inferred claim 的依赖变化
将 inferred claim 标记为 stale，并生成重新评估 task。
```

历史变化主要通过三类信息读取：

```text
claims.status / updated_at
表示 claim 当前处于什么状态，以及最近何时变化。

relations
表示 claim 被哪些证据支持、被哪些 claim 反驳、被哪个新 claim 替代、从哪些对象推理而来。

logs
表示 gmind 在什么时候执行了 ingest、冲突检测、任务完成、状态更新等系统动作。
```

如果未来需要字段级版本管理，可以再增加：

```text
claim_versions
```

第一版不必先引入完整版本表。

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
