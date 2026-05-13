# GMind Desktop

Electron-based tray/status app for GMind.

This is the selected desktop direction:

- macOS: menu bar app
- Windows: notification area / system tray app
- Linux: desktop tray where supported

The Electron app is the desktop mainline.

## Current Scope

This first scaffold focuses on platform boundaries:

- tray app shell
- local server status
- start/stop/restart `gmind serve`
- install/repair the `gmind` CLI shim
- diagnostics panel

The release path will later bundle the Python backend as an Electron extra resource or packaged helper so users do not need to install Python, Node.js, or `uv` separately for normal app usage.

## Development

Requirements:

- Node.js
- a working development `gmind` CLI until the sidecar is packaged

```bash
cd gmind-desktop
npm install
npm run build
npm run electron
```

Build an unsigned macOS app directory:

```bash
npm run electron:build
```
