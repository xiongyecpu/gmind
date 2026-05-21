# Finder Send to Gmind

## 目标

第一版采用方案 A：macOS Services / Quick Action 风格入口。

用户在 Finder 里选中文件后，通过右键菜单里的服务项把文件送入 Gmind。这个版本优先证明闭环，不引入 Finder Sync Extension、App Group 队列或 Xcode extension target。

```text
Finder 文件 -> Send to Gmind -> Gmind App -> 内置 CLI -> 问一下可检索
```

## 用户体验

### 入口

用户选中一个或多个文件，右键后从 Finder 的 `服务` / `快速操作` 区域触发：

```text
Send to Gmind
```

第一版支持：

```text
.md / .markdown -> gmind add markdown
.txt            -> gmind add text
```

其他文件会被跳过。

### 反馈

不打开大窗口。App 通过系统通知反馈结果：

```text
Gmind
已加入 3 个文件。
```

部分失败时：

```text
Gmind
2 个文件已加入，1 个文件未处理。
```

### 设置页

设置页增加一个小项：

```text
Finder 菜单
Send to Gmind
重新注册
```

这个入口只负责重新向 macOS 注册服务，不承载复杂配置。

## 技术设计

使用 App 安装真实 Automator workflow：

```text
~/Library/Services/Send to Gmind.workflow
```

App 启动时：

```text
register CLI symlink
write Send to Gmind.workflow
lsregister -f ~/Library/Services/Send to Gmind.workflow
pbs -flush
```

Finder 触发服务后，workflow 读取选中文件路径，运行 shell 脚本。脚本从 Keychain 读取 `SILICONFLOW_API_KEY`，再调用注册好的 CLI：

```bash
gmind add markdown --title "<filename>" --file "<path>"
gmind add text --title "<filename>" --file "<path>"
```

## 为什么不用纯 shell Quick Action

workflow 不保存 key。它在运行时用 macOS `security` 命令读取 App 已保存到 Keychain 的 `SILICONFLOW_API_KEY`：

```bash
security find-generic-password -s gmind -a SILICONFLOW_API_KEY -w
```

这样右键导入不依赖 shell profile，也不会把 key 写进脚本。

## 第一版限制

- 菜单位置由 macOS Services 决定，可能在 `服务` / `快速操作` 子菜单里，不保证 Finder 顶层直接显示。
- 服务注册后 macOS 可能需要一点时间刷新菜单；开发调试时可执行 `pbs -flush` 或重启 Finder。
- 暂不支持 PDF、Word、图片 OCR。
- 暂不做 Finder Sync Extension 的目录监听和文件状态图标。

## 后续升级

如果方案 A 的入口被证明高频使用，再升级到 Finder Sync Extension。那时再做：

- 更原生的 Finder 顶层菜单。
- 多目录监听。
- App Group 队列。
- 文件状态图标。
- 更完整的导入历史。
