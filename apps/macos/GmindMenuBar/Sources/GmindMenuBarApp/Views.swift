import SwiftUI

private enum GmindColors {
    static let background = Color(hex: 0xF7F5EF)
    static let paper = Color(hex: 0xFFFFFB)
    static let wash = Color(hex: 0xF0EDE4)
    static let ink = Color(hex: 0x20201D)
    static let secondary = Color(hex: 0x66645D)
    static let muted = Color(hex: 0x9A9589)
    static let line = Color(hex: 0xDFDBCF)
    static let blue = Color(hex: 0x2563EB)
    static let softBlue = Color(hex: 0xEEF4FF)
    static let green = Color(hex: 0x2F8F68)
}

struct MenuBarView: View {
    @EnvironmentObject private var state: GmindState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                GmindMark()

                Text("gmind")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(GmindColors.ink)

                Spacer()

                StatusPill(text: state.readyLabel, isBusy: state.isBusy)
            }

            Divider()
                .overlay(GmindColors.line)

            VStack(alignment: .leading, spacing: 6) {
                Text("今日知识库")
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(GmindColors.muted)
                    .textCase(.uppercase)

                Text(state.entities.isEmpty ? "已有资料可回答" : "知识库已就绪")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(GmindColors.ink)
            }
            .padding(.vertical, 2)

            HStack(spacing: 8) {
                MetricBox(value: "\(state.knowledgeCounts.entities)", label: "知识点")
                MetricBox(value: "\(state.knowledgeCounts.claims)", label: "事实")
                MetricBox(value: "\(state.knowledgeCounts.events)", label: "事件")
            }

            Button {
                openMainWindow(section: "ask")
            } label: {
                Text("问一下")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(PrimaryButtonStyle())

            Button {
                openMainWindow(section: "settings")
            } label: {
                Text("设置")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(SecondaryButtonStyle())

            Divider()
                .overlay(GmindColors.line)

            HStack {
                Text("最近：\(state.askQuestion)")
                    .font(.system(size: 12))
                    .foregroundStyle(GmindColors.secondary)
                    .lineLimit(1)

                Spacer()

                Button("退出") {
                    NSApplication.shared.terminate(nil)
                }
                .buttonStyle(.plain)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(GmindColors.secondary)
                .keyboardShortcut("q")
            }
        }
        .padding(14)
        .frame(width: 250)
        .background(GmindColors.paper)
    }

    private func openMainWindow(section: String) {
        state.selectedSection = section
        openWindow(id: "main")
        NSApplication.shared.activate(ignoringOtherApps: true)
    }
}

struct MainWindowView: View {
    @EnvironmentObject private var state: GmindState

    var body: some View {
        HStack(spacing: 0) {
            SidebarView()

            VStack(spacing: 0) {
                TopBarView()

                Group {
                    if state.selectedSection == "settings" {
                        SettingsView()
                    } else {
                        AskView()
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            }
        }
        .frame(width: 520)
        .frame(minHeight: 390)
        .background(GmindColors.paper)
    }
}

private struct SidebarView: View {
    @EnvironmentObject private var state: GmindState

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("GMIND")
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
                .foregroundStyle(GmindColors.muted)
                .padding(.horizontal, 8)
                .padding(.bottom, 10)

            SidebarButton(title: "问一下", section: "ask")
            SidebarButton(title: "设置", section: "settings")

            Spacer()
        }
        .padding(.horizontal, 7)
        .padding(.vertical, 12)
        .frame(width: 96)
        .background(GmindColors.wash.opacity(0.48))
        .overlay(alignment: .trailing) {
            Rectangle()
                .fill(GmindColors.line)
                .frame(width: 1)
        }
    }
}

private struct SidebarButton: View {
    @EnvironmentObject private var state: GmindState
    let title: String
    let section: String

    var body: some View {
        Button {
            state.selectedSection = section
        } label: {
            Text(title)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(state.selectedSection == section ? Color(hex: 0x1745A1) : GmindColors.secondary)
                .frame(maxWidth: .infinity, minHeight: 30, alignment: .leading)
                .padding(.horizontal, 8)
                .background(state.selectedSection == section ? GmindColors.softBlue : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct TopBarView: View {
    @EnvironmentObject private var state: GmindState

    var body: some View {
        HStack {
            Text(state.selectedSection == "settings" ? "设置" : "问一下")
                .font(.system(size: 20, weight: .semibold))
                .foregroundStyle(GmindColors.ink)

            Spacer()

            StatusPill(text: state.readyLabel, isBusy: state.isBusy)
        }
        .frame(height: 48)
        .padding(.horizontal, 16)
        .background(GmindColors.paper)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(GmindColors.line)
                .frame(height: 1)
        }
    }
}

private struct AskView: View {
    @EnvironmentObject private var state: GmindState

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            VStack(alignment: .leading, spacing: 8) {
                Text("你想知道什么？")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(GmindColors.secondary)

                TextEditor(text: $state.askQuestion)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(GmindColors.ink)
                    .scrollContentBackground(.hidden)
                    .frame(height: 58)
                    .padding(8)
                    .background(Color(hex: 0xFFFEFA))
                    .clipShape(RoundedRectangle(cornerRadius: 11, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 11, style: .continuous)
                            .stroke(GmindColors.line)
                    )

                HStack(spacing: 8) {
                    Chip(text: "全部资料", isActive: true)
                    Chip(text: "最近")
                    Spacer()
                    Button("问一下") {
                        state.ask()
                    }
                    .buttonStyle(PrimaryButtonStyle(width: 82))
                    .disabled(state.isBusy)
                }
            }
            .padding(12)
            .background(CardBackground())

            VStack(alignment: .leading, spacing: 8) {
                Text("回答")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(GmindColors.ink)

                Text(state.askAnswer)
                    .font(.system(size: 12))
                    .foregroundStyle(GmindColors.secondary)
                    .lineSpacing(3)
                    .textSelection(.enabled)

                HStack(spacing: 8) {
                    ForEach(state.askEvidenceChips, id: \.self) { chip in
                        Chip(text: chip)
                    }
                }
            }
            .padding(13)
            .background(CardBackground())
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }
}

struct SettingsView: View {
    @EnvironmentObject private var state: GmindState

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            SettingCard(title: "AI 引擎", detail: "用于综合回答。密钥保存在 macOS Keychain，不写进配置文件。") {
                SecureField("SiliconFlow API Key", text: $state.apiKey)
                    .textFieldStyle(.plain)
                    .font(.system(size: 12, design: .monospaced))
                    .padding(.horizontal, 11)
                    .frame(height: 32)
                    .background(FieldBackground())

                Button("测试") {
                    state.testConnection()
                }
                .buttonStyle(PrimaryButtonStyle(width: 74))
                .disabled(state.isBusy)
            }

            SettingCard(title: "知识库", detail: "保存资料、事实、事件和来源。") {
                TextField("PostgreSQL URL", text: $state.databaseURL)
                    .textFieldStyle(.plain)
                    .font(.system(size: 12, design: .monospaced))
                    .padding(.horizontal, 11)
                    .frame(height: 32)
                    .background(FieldBackground())

                Button("测试连接") {
                    state.testConnection()
                }
                .buttonStyle(PrimaryButtonStyle(width: 88))
                .disabled(state.isBusy)
            }

            SettingCard(title: "Solo 模式", detail: "开启后，Gmind 会先关注下载文件夹，并记录每次允许或拒绝的原因。") {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("下载文件夹")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(GmindColors.ink)
                        Text("~/Downloads")
                            .font(.system(size: 12, design: .monospaced))
                            .foregroundStyle(GmindColors.secondary)
                            .lineLimit(1)
                    }

                    Spacer()

                    Toggle("", isOn: $state.soloEnabled)
                        .toggleStyle(.switch)
                        .labelsHidden()
                        .disabled(state.isBusy)
                }
            }

            SettingCard(title: "命令行工具", detail: state.cliInstallLabel) {
                HStack {
                    Text("~/.local/bin/gmind")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundStyle(GmindColors.secondary)
                        .lineLimit(1)

                    Spacer()

                    Button("重新安装") {
                        state.registerCLI()
                    }
                    .buttonStyle(PrimaryButtonStyle(width: 88))
                }
            }

            SettingCard(title: "Finder 菜单", detail: state.finderServiceLabel) {
                HStack {
                    Text("Send to Gmind")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundStyle(GmindColors.secondary)
                        .lineLimit(1)

                    Spacer()

                    Button("重新注册") {
                        state.registerFinderService()
                    }
                    .buttonStyle(PrimaryButtonStyle(width: 88))
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }
}

private struct SettingCard<Content: View>: View {
    let title: String
    let detail: String
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(GmindColors.ink)

            Text(detail)
                .font(.system(size: 12))
                .foregroundStyle(GmindColors.secondary)
                .lineSpacing(3)

            content
        }
        .padding(12)
        .background(CardBackground())
    }
}

private struct MetricBox: View {
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(value)
                .font(.system(size: 15, weight: .semibold, design: .monospaced))
                .foregroundStyle(GmindColors.ink)

            Text(label)
                .font(.system(size: 11))
                .foregroundStyle(GmindColors.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(9)
        .background(Color(hex: 0xF7F5EF).opacity(0.52))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(GmindColors.line)
        )
    }
}

private struct StatusPill: View {
    let text: String
    let isBusy: Bool

    var body: some View {
        HStack(spacing: 6) {
            if isBusy {
                ProgressView()
                    .controlSize(.small)
                    .scaleEffect(0.6)
                    .frame(width: 8, height: 8)
            } else {
                Circle()
                    .fill(GmindColors.green)
                    .frame(width: 7, height: 7)
            }

            Text(text)
                .font(.system(size: 12, weight: .semibold))
        }
        .padding(.horizontal, 9)
        .frame(height: 24)
        .foregroundStyle(Color(hex: 0x1F6F4F))
        .background(GmindColors.green.opacity(0.09))
        .clipShape(Capsule())
        .overlay(
            Capsule()
                .stroke(GmindColors.green.opacity(0.24))
        )
    }
}

private struct Chip: View {
    let text: String
    var isActive = false

    var body: some View {
        Text(text)
            .font(.system(size: 12))
            .foregroundStyle(isActive ? Color(hex: 0x1745A1) : GmindColors.secondary)
            .padding(.horizontal, 10)
            .frame(height: 26)
            .background(isActive ? GmindColors.softBlue : Color(hex: 0xFFFEFA))
            .clipShape(Capsule())
            .overlay(
                Capsule()
                    .stroke(isActive ? GmindColors.blue.opacity(0.25) : GmindColors.line)
            )
    }
}

private struct GmindMark: View {
    var body: some View {
        Circle()
            .stroke(GmindColors.ink, lineWidth: 1)
            .frame(width: 20, height: 20)
            .overlay {
                Rectangle()
                    .fill(GmindColors.ink.opacity(0.22))
                    .frame(width: 1)
            }
    }
}

private struct CardBackground: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 14, style: .continuous)
            .fill(GmindColors.paper)
            .shadow(color: Color.black.opacity(0.08), radius: 14, y: 4)
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(GmindColors.line)
            )
    }
}

private struct FieldBackground: View {
    var body: some View {
        RoundedRectangle(cornerRadius: 10, style: .continuous)
            .fill(Color(hex: 0xFFFEFA))
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .stroke(GmindColors.line)
            )
    }
}

private struct PrimaryButtonStyle: ButtonStyle {
    var width: CGFloat?

    init(width: CGFloat? = nil) {
        self.width = width
    }

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: width, height: 32)
            .frame(maxWidth: width == nil ? .infinity : nil)
            .background(GmindColors.blue.opacity(configuration.isPressed ? 0.82 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
            .shadow(color: GmindColors.blue.opacity(0.16), radius: 9, y: 4)
    }
}

private struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .semibold))
            .foregroundStyle(GmindColors.ink)
            .frame(height: 32)
            .frame(maxWidth: .infinity)
            .background(configuration.isPressed ? GmindColors.wash : GmindColors.paper)
            .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .stroke(GmindColors.line)
            )
    }
}

private extension Color {
    init(hex: UInt, alpha: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: alpha
        )
    }
}
