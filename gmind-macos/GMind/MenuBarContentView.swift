import SwiftUI

struct MenuBarContentView: View {
    @State private var pageCount: Int = 0
    @State private var recentPages: [Page] = []
    @State private var isOnline = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Actions
            MenuAction(icon: "square.and.pencil", label: "记一条", shortcut: "⌘A") {
                PanelManager.shared.showQuickAdd()
            }
            MenuAction(icon: "brain.head.profile", label: "问 AI", shortcut: "⌘S") {
                PanelManager.shared.showAskAI()
            }

            Divider().padding(.vertical, 4)

            // Status
            HStack(spacing: 6) {
                Circle()
                    .fill(isOnline ? Color.green : Color.red)
                    .frame(width: 6, height: 6)
                Text("\(pageCount) 条笔记")
                    .font(.system(size: 12))
                Spacer()
            }
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14)
            .padding(.vertical, 4)

            if !recentPages.isEmpty {
                Divider().padding(.vertical, 4)

                Text("最近")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 14)
                    .padding(.top, 4)

                ForEach(recentPages) { page in
                    Button(page.title) {
                        openInEditor(slug: page.slug)
                    }
                    .buttonStyle(.plain)
                    .font(.system(size: 12))
                    .lineLimit(1)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 2)
                }
            }

            Divider().padding(.vertical, 4)

            MenuAction(icon: "gearshape", label: "模型配置") {
                PanelManager.shared.showModelConfig()
            }
            MenuAction(icon: "folder.badge.plus", label: "饕餮盛宴") {
                PanelManager.shared.showTaotie()
            }

            Divider().padding(.vertical, 4)

            MenuAction(icon: "power", label: "退出") {
                ServerManager.shared.stop()
                NSApp.terminate(nil)
            }
        }
        .padding(.vertical, 8)
        .frame(width: 180)
        .onAppear {
            loadData()
        }
    }

    private func loadData() {
        GMindAPI.shared.fetchStats { stats in
            DispatchQueue.main.async {
                isOnline = stats != nil
                pageCount = stats?.pageCount ?? 0
            }
        }
        GMindAPI.shared.fetchRecent(limit: 5) { pages in
            DispatchQueue.main.async {
                recentPages = pages
            }
        }
    }

    private func openInEditor(slug: String) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = ["-c", "gmind export /tmp/gmind-export >/dev/null 2>&1 && open /tmp/gmind-export/\(slug).md"]
        try? task.run()
    }
}

struct MenuAction: View {
    let icon: String
    let label: String
    var shortcut: String? = nil
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 13))
                    .frame(width: 16, alignment: .center)
                    .foregroundStyle(.secondary)
                Text(label)
                    .font(.system(size: 13))
                Spacer()
                if let shortcut = shortcut {
                    Text(shortcut)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 14)
        .padding(.vertical, 4)
    }
}
