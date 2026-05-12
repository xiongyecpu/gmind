# GMind macOS Menu Bar App

A native macOS menu bar companion for GMind.

## Features

- **Menu bar icon** — Always accessible, no dock icon
- **Quick Add** (`⌘⇧A`) — Global shortcut to capture thoughts
- **Quick Search** (`⌘⇧S`) — Real-time vector search + Ask AI
- **Dashboard** — Stats, knowledge graph, recent pages
- **Auto server management** — Detects and starts `gmind serve` automatically

## Prerequisites

1. **GMind CLI installed and in PATH**
   ```bash
   # Verify
   which gmind
   gmind --version
   ```

2. **gmind serve must be working**
   ```bash
   gmind serve --port 8765
   # Should start without errors
   ```

## Build

### Option A: XcodeGen (recommended)

```bash
cd gmind-macos
# Install xcodegen if needed: brew install xcodegen
xcodegen generate
open GMind.xcodeproj
```

Then in Xcode: **Product → Build** (`⌘B`) or **Product → Run** (`⌘R`).

### Option B: Manual Xcode project

1. Open Xcode
2. **File → New → Project → macOS → App**
3. Name: `GMind`, Interface: `SwiftUI`, Language: `Swift`
4. Replace the generated files with the ones in `GMind/`:
   - Delete `ContentView.swift`
   - Add all `.swift` files from `gmind-macos/GMind/`
5. Replace `Info.plist` with the one provided
6. Build and run

### Option C: Swift Package Manager (no Xcode UI)

```bash
cd gmind-macos
swift build
swift run GMind
```

> Note: For SPM, you may need a `Package.swift` wrapper. The XcodeGen or manual Xcode approach is recommended.

## Setup

After first launch:

1. Make sure `gmind serve` is running (the app tries to auto-start it)
2. The menu bar icon 🧠 appears in your status bar
3. Click it to access Quick Add, Quick Search, Dashboard

## Architecture

```
┌─────────────────┐     HTTP API      ┌─────────────────────┐
│  GMind macOS    │  ═══════════════► │   gmind serve       │
│  (SwiftUI)      │   localhost:8765  │   (Python/Starlette)│
│                 │                   │                     │
│  - MenuBar      │                   │   - /add            │
│  - QuickAdd     │                   │   - /search         │
│  - QuickSearch  │                   │   - /ask (LLM)      │
│  - Dashboard    │                   │   - /enrich         │
└─────────────────┘                   └─────────────────────┘
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Click 🧠 icon | Open menu |
| `⌘⇧A` | Quick Add (via menu) |
| `⌘⇧S` | Quick Search (via menu) |
| `⌘,` | Settings |

> Global shortcuts require macOS system configuration. Go to **System Settings → Keyboard → Keyboard Shortcuts → App Shortcuts** to bind global hotkeys.

## Troubleshooting

**"Server offline" in menu**
- Check: `gmind serve --port 8765` works in terminal
- Check: `gmind` is in your PATH (`which gmind`)
- The app searches: `/usr/local/bin`, `/opt/homebrew/bin`, `~/.local/bin`, `~/gmind/.venv/bin`

**Build errors**
- Ensure macOS deployment target is 13.0+
- Xcode 15+ recommended

## License

Same as GMind — MIT
