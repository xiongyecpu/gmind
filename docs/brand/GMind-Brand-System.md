# GMind Brand System

> Status: v0.1 design foundation for the Electron menu bar app and future website.

## Brand Idea

GMind is a local-first knowledge system. It helps people keep thoughts, documents, and agent work connected without asking them to understand databases, servers, or embeddings.

The brand should feel like a trusted personal memory layer:

- Quiet, not sleepy
- Intelligent, not flashy
- Local and private, not corporate SaaS
- Useful in ten seconds, deep when needed

## Product Language

Use human-facing names in the app:

| Technical concept | Product copy |
|---|---|
| Add note | 记一条 |
| Ask AI / RAG | 问一下 |
| Taotie | 知识雷达 |
| Diagnostics | 诊断 |
| Embedding model | 向量化模型 |
| Reasoning model | 推理模型 |
| Server ready | 知识库正常 |
| Ingest queue | 待加入 |

Avoid exposing `server`, `CLI`, `PostgreSQL`, `port`, or raw provider jargon on the main surface. Model configuration belongs in Settings and should be framed as two required capabilities: `向量化模型` and `推理模型`.

## Logo

Primary mark:

- `gmind-desktop/src/assets/gmind-mark.svg`

The mark combines a `G` with three graph nodes. It should be used as the menu bar app mark, app icon source, website favicon basis, and compact product signature.

Usage rules:

- Do not recolor individual nodes unless a full palette migration is approved.
- Do not add glows, gradients, or drop shadows to the mark.
- Use the mark at 16, 24, 32, 48, and 96 px sizes.
- Pair with the word `GMind` in text instead of building a complex wordmark.

## Color Tokens

GMind should not read as a one-color green app. The system uses a quiet neutral base, a memory green, and two supporting signal colors for graph intelligence and warm human input.

```css
:root {
  --gm-ink: #17211d;
  --gm-muted: #617068;
  --gm-paper: #f5f7f2;
  --gm-surface: #ffffff;
  --gm-line: #dfe6dc;
  --gm-green: #2e7d5b;
  --gm-green-soft: #e4f0e9;
  --gm-blue: #2d6cdf;
  --gm-blue-soft: #e8eefb;
  --gm-copper: #c85f32;
  --gm-copper-soft: #f6e9e2;
  --gm-yellow: #d6a43a;
  --gm-danger: #b84a3c;
}
```

Roles:

- `--gm-green`: primary action, healthy knowledge state, saved confirmation.
- `--gm-blue`: search/answer/intelligence signal.
- `--gm-copper`: human note-taking, recent memory, warm highlights.
- `--gm-yellow`: waiting, scan in progress, gentle alerts.
- `--gm-ink`: text and mark stroke.

## Typography

Use platform-native body type for trust and performance, plus a more literary display face on marketing surfaces.

App:

```css
font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
```

Website/display:

```css
font-family: "Newsreader", "Source Serif 4", Georgia, serif;
```

Rules:

- App panel headings stay compact: 16-22 px.
- Website hero headings may use serif display.
- Do not use all-caps labels except tiny technical section hints.
- Letter spacing stays `0`; use weight and spacing, not tracking, for hierarchy.

## Shape And Layout

GMind UI should feel like a carefully kept notebook, not a dashboard.

- Menu popover width: 390-430 px.
- Corner radius: 8 px for repeated items, 12 px for the popover shell.
- Main input radius: 10 px.
- Minimum touch target: 32 px.
- No nested cards. Use bands, rows, and separators.
- One primary action per area.
- Keep the first view usable without scrolling.

## Components

### Menu Bar Popover

Purpose: the everyday surface. A user should complete `记一条` or `问一下` in under 10 seconds.

Sections:

1. Header: mark, `GMind`, natural-language status.
2. Knowledge status: today count, total count, last saved.
3. `记一条`: multiline text field + save button.
4. `问一下`: single-line prompt + answer/search state.
5. `知识雷达`: discovery summary + review action.
6. Recent memory: last 3 saved items.
7. Footer: settings and diagnostics.

### Save Toast

Triggered from menu bar after successful save.

Copy examples:

- `已加入知识库`
- `这条内容已经记过了`
- `知识库暂时不可用，稍后再试`

### Knowledge Radar

`知识雷达` replaces `饕餮` in user-facing UI. It should sound safe and helpful, not hungry or invasive.

Safety rules:

- Always make scan scope visible before scanning.
- Default to Documents/Desktop/Downloads.
- Sensitive files are skipped by default.
- Use copy like `已跳过可能包含隐私的内容`.

### Settings

Settings must show two required model configurations:

1. `向量化模型`: required for saving, embedding, search, and similarity.
2. `推理模型`: required for `问一下`, summaries, tags, entities, and relationship extraction.

Do not present model capability as a single optional AI toggle. If either model is missing, the app should say what is blocked in human terms:

- `还不能记一条：请先配置向量化模型。`
- `还不能问一下：请先配置推理模型。`
- `知识库还没准备好：两套模型都需要配置。`

## Motion

Motion should be restrained and purposeful:

- Popover open: 120 ms ease-out fade + 4 px vertical settle.
- Save success: mark pulse once, then toast.
- Radar count update: number rolls or fades, no bouncing.
- Loading: quiet text state, no spinner unless wait > 600 ms.

## Website Direction

The future website should use the same tokens but with more editorial scale:

- White/green paper base.
- Serif hero headline.
- Product screenshots and real UI, not abstract blobs.
- Sections: `记一条`, `问一下`, `知识雷达`, `本地优先`, `给 Agent 的 CLI`.
- Avoid generic AI landing page tropes: purple gradients, huge abstract orbs, and fake dashboard cards.

## Design Promise

GMind should make a non-technical user feel:

> “我不用整理完才开始。先记下来，它会帮我连起来。”
