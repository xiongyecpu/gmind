# GMind Desktop

Tauri-based tray/status app for GMind.

This is the selected cross-platform desktop direction:

- macOS: menu bar app
- Windows: notification area / system tray app
- Linux: desktop tray where supported

The legacy SwiftUI implementation in `gmind-macos/` stays available until this Tauri app can reliably manage the backend server and CLI.

## Current Scope

This first scaffold focuses on platform boundaries:

- tray app shell
- local server status
- start/stop/restart `gmind serve`
- install/repair the `gmind` CLI shim
- diagnostics panel

The release path will later bundle the Python backend as a Tauri sidecar.
Tauri's sidecar model is a good fit for GMind because it supports bundling a Python CLI/API server binary so users do not need to install Python, Node.js, or `uv` separately for normal app usage.

## Development

Requirements:

- Node.js
- Rust toolchain (`cargo`, `rustc`)
- a working development `gmind` CLI until the sidecar is packaged

```bash
cd gmind-desktop
npm install
npm run build
npm run tauri dev
```

This workspace currently cannot be fully verified without Rust installed.
