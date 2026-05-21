# gmind macOS App Design System

> Status: draft v4
> Scope: macOS menu bar MVP
> Product loop: Ask -> gmind finds relevant knowledge -> answer with evidence

## Product Position

gmind is an automated personal knowledge base for ordinary people. The macOS
app is not a manual note editor and not a developer console. It is a small Mac
utility where the human does two things:

```text
Ask a question.
Check settings when something is not connected.
```

Everything else is system work. The CLI, vectors, extraction pipeline, database,
and provider details stay behind the interface.

The visual direction is **minimal, intelligent, and Japanese-inspired**:
quiet paper surfaces, precise spacing, fine borders, modest color, and a calm
sense that the system is doing serious work in the background.

The app should be **small and refined**. Think menu bar companion, not full
desktop dashboard. Dense does not mean cramped: every surface should have fewer
objects, smaller dimensions, and better spacing. Current target window size is
about `520 x 390-430`.

## MVP Scope

Only two surfaces are in the first app design:

```text
问一下
设置
```

Do not add a `资料入口` surface in the app MVP. Source ingestion can remain in the
CLI or future automation, but the current human-facing app should not expand the
product surface before the ask loop feels good.

Success criteria:

```text
The menu bar popover clearly says gmind is ready.
The main window opens to 问一下.
The user can ask one question and see one synthesized answer.
The answer can show light evidence without exposing implementation.
Settings only covers AI key and knowledge base connection.
```

## Design Principles

### 1. Ask First

The product's primary action is `问一下`. This is not a chat app, and it is not a
knowledge-management dashboard. The interaction should feel closer to asking a
smart local appliance:

```text
Question -> answer -> small evidence hints
```

Avoid showing process panels, pipelines, logs, vector search diagrams, or future
feature lanes on the ask page.

### 2. One Small Loop

The MVP should resist expansion. Do not introduce `打开知识库`, `资料入口`, source
lanes, task queues, or knowledge graph browsing as first-class navigation.

Allowed on the ask page:

- question input
- primary `问一下` button
- answer card
- simple evidence chips
- clear empty / error state

Avoid on the ask page:

- right-side workflow panels
- multi-step processing explanations
- evidence cards by default
- database terms
- vector / chunk / schema language
- future automation teasers

### 3. Minimal, Smart, Native Mac

The visual style should feel like a quiet Mac utility with Japanese restraint:
small, precise, light, and intelligent. Use whitespace and alignment instead of
decorative metaphors.

Avoid:

- knowledge-toast visuals or wording
- franchise characters or names
- literal cartoon scenes
- decorative mascot UI
- large warm accent blocks
- playful food metaphors

### 4. Human Words

Use product language, not infrastructure language.

| Avoid | Use |
| --- | --- |
| `semantic search` | `找相关资料` |
| `vector recall` | `找相关资料` |
| `RAG answer` | `综合回答` |
| `provider` | `AI 引擎` |
| `database URL` | `知识库连接` |
| `entities` | `知识点` |
| `source_chunks` | `资料片段` |

The user can understand that gmind is smart without seeing how the machinery is
assembled.

## Core Surfaces

### Menu Bar Popover

Role: lightweight status and entry.

Structure:

```text
Header: gmind + ready / needs setup
Quiet status card: latest answer or setup prompt
Small counts: knowledge points / facts / sources
Primary action: 问一下
Secondary action: 设置
Footer: latest question or latest system state
```

Do not include `资料入口` in the popover.

### Ask Page

Role: the whole product loop for the MVP.

Structure:

```text
Top bar: 问一下 + readiness state
Question composer
Primary button
Answer card
Evidence chips
```

The ask page should be a single-column reading and writing surface. Avoid a
right rail unless there is a concrete user problem that cannot fit in the main
column.

Target feel:

```text
small window
short top bar
narrow sidebar
one compact composer
one compact answer
```

Good labels:

```text
你想问 gmind 什么？
问一下
回答
参考资料
没有找到相关资料
```

### Settings Page

Role: make the app usable.

Only include:

```text
AI 引擎
知识库
```

Settings can expose masked values and connection tests. It should not become a
general developer configuration editor.

## Visual Tokens

The current prototype uses an off-white paper surface, quiet ink, hairline
borders, signal-blue action color, and green readiness state.

```text
surface.background   #F7F5EF
surface.panel        #FFFFFB
surface.sidebar      #F0EDE4
ink.primary          #20201D
ink.secondary        #66645D
ink.muted            #9A9589
line.subtle          #DFDBCF
accent.action        #2F80ED
accent.ready         #2F8F68
```

Rules:

- Blue is for primary action and selected navigation.
- Green is for ready / healthy status.
- Keep backgrounds light enough for reading.
- Avoid warm yellow/orange blocks; they pull the product back toward the rejected
  childish direction.
- Use blue and green as small system signals, not decorative fills.

## Typography

```text
UI / body:       -apple-system, BlinkMacSystemFont, "SF Pro Text"
Display:         -apple-system, BlinkMacSystemFont, "SF Pro Display"
Telemetry:       "SF Mono", ui-monospace
```

Rules:

- No viewport-based font sizing.
- No negative letter spacing.
- Use mono only for small status, counts, and masked paths.
- Keep answer text readable before making it expressive.

## Shape And Layout

```text
control radius       11
panel radius         14
window radius        16
status pill radius   999
```

Layout:

- Menu bar popover can be compact and instrument-like.
- Main window uses a narrow sidebar with only `问一下` and `设置`.
- Ask page is single-column.
- Settings uses stacked compact cards; avoid tall blank panels.
- Do not nest cards inside cards unless the inner item is evidence.
- Avoid tall empty panels. If a surface has little content, shrink the surface.

## Components

### Primary Button

Copy:

```text
问一下
测试
测试连接
```

The primary ask button uses `accent.action`.

### Answer Card

The answer card is the signature component. It should look calm and readable,
with no decorative metaphor.

Content:

```text
Title: 回答
Synthesized answer
Evidence chips
```

### Evidence Snippet

Evidence is trust support, not a workflow panel.

```text
Fact title
Source name · date
```

Show at most a few snippets by default.

For the compact MVP, prefer chips over separate evidence cards. Open detailed
evidence later only if the user asks for it.

### Status Pill

States:

```text
可提问
正在回答
需要设置
连接失败
```

Do not show internal state names.

## Interaction Rules

- Main window is single-instance.
- Opening from the menu bar activates and focuses the app.
- Default destination is `问一下`.
- Long operations run in the background.
- The button can enter a processing state, but the user should not need to read
  a pipeline to understand what is happening.
- Errors must explain the recovery action.

## Empty And Error States

Empty:

```text
还没有可回答的资料
gmind 还没有找到能回答这个问题的内容。
```

Needs setup:

```text
还不能提问
先在设置里连接 AI 引擎和知识库。
[去设置]
```

Error:

```text
知识库连不上
检查设置里的知识库连接，或稍后再试。
[去设置]
```

## Prototype Reference

Current HTML prototype:

```text
apps/macos/GmindMenuBar/design/gmind-app-prototype.html
```

The prototype intentionally removes `资料入口` and the ask-page right rail. Keep it
small until the core ask loop is implemented and tested.
