import SwiftUI
import AppKit

class PanelManager {
    static let shared = PanelManager()

    private var quickAddPanel: NSPanel?
    private var askAIPanel: NSPanel?
    private var modelConfigPanel: NSPanel?
    private var taotiePanel: NSPanel?

    private init() {}

    func showQuickAdd() {
        closeAll()
        let panel = makePanel(title: "记一条", width: 420, height: 220)
        panel.contentView = NSHostingView(rootView: QuickAddView(onClose: { [weak self] in
            self?.quickAddPanel?.close()
            self?.quickAddPanel = nil
        }))
        panel.makeKeyAndOrderFront(nil)
        quickAddPanel = panel
    }

    func showAskAI() {
        closeAll()
        let panel = makePanel(title: "问 AI", width: 580, height: 520)
        panel.contentView = NSHostingView(rootView: AskAIView(onClose: { [weak self] in
            self?.askAIPanel?.close()
            self?.askAIPanel = nil
        }))
        panel.makeKeyAndOrderFront(nil)
        askAIPanel = panel
    }

    func showModelConfig() {
        closeAll()
        let panel = makePanel(title: "模型配置", width: 400, height: 280)
        panel.contentView = NSHostingView(rootView: ModelConfigView(onClose: { [weak self] in
            self?.modelConfigPanel?.close()
            self?.modelConfigPanel = nil
        }))
        panel.makeKeyAndOrderFront(nil)
        modelConfigPanel = panel
    }

    func showTaotie() {
        closeAll()
        let panel = makePanel(title: "饕餮盛宴", width: 520, height: 420)
        panel.contentView = NSHostingView(rootView: TaotieView(onClose: { [weak self] in
            self?.taotiePanel?.close()
            self?.taotiePanel = nil
        }))
        panel.makeKeyAndOrderFront(nil)
        taotiePanel = panel
    }

    private func makePanel(title: String, width: CGFloat, height: CGFloat) -> NSPanel {
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: width, height: height),
            styleMask: [.titled, .closable, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.title = title
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.center()
        return panel
    }

    private func closeAll() {
        quickAddPanel?.close(); quickAddPanel = nil
        askAIPanel?.close(); askAIPanel = nil
        modelConfigPanel?.close(); modelConfigPanel = nil
        taotiePanel?.close(); taotiePanel = nil
    }
}
