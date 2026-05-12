import SwiftUI

@main
struct GMindApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        MenuBarExtra("GMind", systemImage: "brain.head.profile") {
            MenuBarContentView()
        }
        .menuBarExtraStyle(.window)
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        ServerManager.shared.ensureRunning()
    }

    func applicationWillTerminate(_ notification: Notification) {
        ServerManager.shared.stop()
    }
}
