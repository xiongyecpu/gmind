# gmind Menu Bar

This is the first macOS menu bar prototype for normal users.

It focuses on one small loop:

```text
Ask -> Answer -> Settings
```

Run it during development:

```bash
cd apps/macos/GmindMenuBar
swift run GmindMenuBarApp
```

Build a local `.app` bundle:

```bash
cd apps/macos/GmindMenuBar
scripts/build-app.sh
open dist/gmind.app
```

The app stores its user config at `~/.gmind/gmind.toml` and stores the
SiliconFlow API key in macOS Keychain.

The built `.app` bundle includes its own CLI at:

```text
gmind.app/Contents/Resources/cli/gmind
```

When the app starts, it installs or updates:

```text
~/.local/bin/gmind -> <current app>/Contents/Resources/cli/gmind
```

So terminal users and agents can call:

```bash
gmind status --config ~/.gmind/gmind.toml
gmind add text --title "Project note" --file note.txt --config ~/.gmind/gmind.toml
gmind add markdown --title "Meeting notes" --file meeting.md --config ~/.gmind/gmind.toml
gmind add text --title "Quick note" --text "Project A signed the contract." --config ~/.gmind/gmind.toml
gmind ask "项目 A 当前进展如何？" --config ~/.gmind/gmind.toml
```

`gmind ask` runs the same core path used by the App: question embedding,
pgvector evidence search, and LLM synthesis. Use `--json` for agents.

Low-level inspection and pipeline commands live under `gmind debug ...`.

If the app is upgraded in place, the CLI follows the upgraded app bundle. If
`~/.local/bin/gmind` already exists as a real file instead of a symlink, the app
backs it up as `gmind.backup.<timestamp>` before installing the managed symlink.

## Finder menu

The app installs a macOS Quick Action / Service named:

```text
Send to Gmind
```

After the app is launched, it writes:

```text
~/Library/Services/Send to Gmind.workflow
```

Finder can send selected files to Gmind from the right-click `Services` /
`Quick Actions` area. The first version supports:

```text
.md / .markdown -> gmind add markdown
.txt            -> gmind add text
```

The workflow reads the API key from Keychain at runtime and calls
`~/.local/bin/gmind`; it does not store the key in the workflow. If the menu
does not appear immediately, launch the built app once and use Settings ->
Finder 菜单 -> 重新注册. During development, `pbs -flush` or restarting Finder may
be needed for macOS to refresh the menu.
