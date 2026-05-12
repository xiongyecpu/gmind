import SwiftUI

struct QuickAddView: View {
    let onClose: () -> Void

    @State private var content = ""
    @State private var isSaving = false
    @FocusState private var isFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            TextEditor(text: $content)
                .font(.body)
                .focusable()
                .focused($isFocused)
                .scrollContentBackground(.hidden)
                .background(Color.clear)
                .overlay(
                    Group {
                        if content.isEmpty {
                            Text("想到了什么？直接贴进来...")
                                .foregroundStyle(.secondary)
                                .allowsHitTesting(false)
                        }
                    },
                    alignment: .topLeading
                )
                .padding(16)

            if isSaving {
                ProgressView()
                    .scaleEffect(0.7)
                    .padding(.bottom, 12)
            } else {
                Text("⌘↵ 记住")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
                    .padding(.bottom, 12)
            }
        }
        .frame(width: 400, height: 160)
        .background(.thinMaterial)
        .onAppear {
            isFocused = true
            if let text = NSPasteboard.general.string(forType: .string), !text.isEmpty {
                content = text
            }
        }
        .onExitCommand {
            onClose()
        }

        // Hidden button to handle ⌘↵
        Button("") { save() }
            .keyboardShortcut(.return, modifiers: .command)
            .opacity(0)
            .frame(width: 0, height: 0)
    }

    private func save() {
        guard !content.isEmpty else { return }
        isSaving = true

        GMindAPI.shared.addPage(content: content, title: nil, source: nil) { result in
            DispatchQueue.main.async {
                isSaving = false
                switch result {
                case .success:
                    NotificationCenter.default.post(name: .init("FlashMenuIcon"), object: nil)
                    onClose()
                case .failure(let error):
                    print("[GMind] save error: \(error)")
                }
            }
        }
    }
}
