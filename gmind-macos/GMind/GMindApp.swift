import SwiftUI
import AppKit

@main
struct GMindApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        // No standard window — everything is menu bar driven
        Settings {
            SettingsView()
        }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var menuBarController: MenuBarController?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Hide dock icon
        NSApp.setActivationPolicy(.accessory)
        
        menuBarController = MenuBarController()
        
        // Ensure gmind serve is running
        ServerManager.shared.ensureRunning()
    }
    
    func applicationWillTerminate(_ notification: Notification) {
        ServerManager.shared.stop()
    }
}
