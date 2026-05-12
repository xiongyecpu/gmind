import SwiftUI
import AppKit

/// Manages the status bar item and its menu.
class MenuBarController: NSObject {
    private var statusItem: NSStatusItem!
    private var quickAddPanel: NSPanel?
    private var quickSearchPanel: NSPanel?
    private var dashboardWindow: NSWindow?
    
    override init() {
        super.init()
        setupStatusItem()
    }
    
    private func setupStatusItem() {
        statusItem = NSStatusBar.shared.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem.button {
            button.title = "🧠"
            button.action = #selector(showMenu)
            button.target = self
        }
    }
    
    @objc private func showMenu() {
        let menu = NSMenu()
        
        // Quick actions
        menu.addItem(NSMenuItem(title: "📝 Quick Add", action: #selector(showQuickAdd), keyEquivalent: "A"))
        menu.addItem(NSMenuItem(title: "🔍 Quick Search", action: #selector(showQuickSearch), keyEquivalent: "S"))
        menu.addItem(NSMenuItem.separator())
        
        // Stats
        addStatsItem(to: menu)
        menu.addItem(NSMenuItem.separator())
        
        // Recent pages
        addRecentPages(to: menu)
        menu.addItem(NSMenuItem.separator())
        
        // Settings & Dashboard
        menu.addItem(NSMenuItem(title: "⚙️ Settings", action: #selector(showSettings), keyEquivalent: ","))
        menu.addItem(NSMenuItem(title: "🚀 Dashboard", action: #selector(showDashboard), keyEquivalent: "D"))
        menu.addItem(NSMenuItem.separator())
        
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q"))
        
        statusItem.menu = menu
        statusItem.button?.performClick(nil)
        statusItem.menu = nil  // Reset so next click rebuilds menu
    }
    
    private func addStatsItem(to menu: NSMenu) {
        let statsItem = NSMenuItem(title: "📊 Loading stats...", action: nil, keyEquivalent: "")
        statsItem.isEnabled = false
        menu.addItem(statsItem)
        
        GMindAPI.shared.fetchStats { stats in
            DispatchQueue.main.async {
                if let stats = stats {
                    statsItem.title = "📊 \(stats.pageCount) pages"
                } else {
                    statsItem.title = "📊 Server offline"
                }
            }
        }
    }
    
    private func addRecentPages(to menu: NSMenu) {
        let recentItem = NSMenuItem(title: "📑 Recent", action: nil, keyEquivalent: "")
        recentItem.isEnabled = false
        menu.addItem(recentItem)
        
        GMindAPI.shared.fetchRecent(limit: 5) { pages in
            DispatchQueue.main.async {
                for page in pages {
                    let item = NSMenuItem(
                        title: "   → \(page.title)",
                        action: #selector(self.openPage),
                        keyEquivalent: ""
                    )
                    item.representedObject = page.slug
                    item.target = self
                    menu.addItem(item)
                }
                if pages.isEmpty {
                    let emptyItem = NSMenuItem(title: "   (no recent pages)", action: nil, keyEquivalent: "")
                    emptyItem.isEnabled = false
                    menu.addItem(emptyItem)
                }
            }
        }
    }
    
    @objc private func showQuickAdd() {
        closeAllPanels()
        
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 480, height: 320),
            styleMask: [.titled, .closable, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.title = "Quick Add"
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.center()
        panel.contentView = NSHostingView(rootView: QuickAddView(onClose: { [weak self] in
            self?.quickAddPanel?.close()
            self?.quickAddPanel = nil
        }))
        panel.makeKeyAndOrderFront(nil)
        quickAddPanel = panel
    }
    
    @objc private func showQuickSearch() {
        closeAllPanels()
        
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 560, height: 480),
            styleMask: [.titled, .closable, .nonactivatingPanel, .resizable],
            backing: .buffered,
            defer: false
        )
        panel.title = "Quick Search"
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.center()
        panel.contentView = NSHostingView(rootView: QuickSearchView(onClose: { [weak self] in
            self?.quickSearchPanel?.close()
            self?.quickSearchPanel = nil
        }))
        panel.makeKeyAndOrderFront(nil)
        quickSearchPanel = panel
    }
    
    @objc private func showDashboard() {
        closeAllPanels()
        
        if let window = dashboardWindow {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }
        
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 960, height: 720),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "GMind Dashboard"
        window.center()
        window.contentView = NSHostingView(rootView: DashboardView())
        window.isReleasedWhenClosed = false
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        dashboardWindow = window
    }
    
    @objc private func showSettings() {
        NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
    }
    
    @objc private func openPage(_ sender: NSMenuItem) {
        guard let slug = sender.representedObject as? String else { return }
        showDashboard()
        // TODO: Navigate to specific page in dashboard
    }
    
    @objc private func quit() {
        ServerManager.shared.stop()
        NSApp.terminate(nil)
    }
    
    private func closeAllPanels() {
        quickAddPanel?.close()
        quickAddPanel = nil
        quickSearchPanel?.close()
        quickSearchPanel = nil
    }
}
