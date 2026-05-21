import SwiftUI

@main
struct GmindMenuBarApp: App {
    @StateObject private var state = GmindState()

    init() {
        guard SingleInstanceLock.shared.acquire() else {
            SingleInstanceLock.shared.activateExistingInstance()
            exit(0)
        }
    }

    var body: some Scene {
        MenuBarExtra("gmind", systemImage: "brain.head.profile") {
            MenuBarView()
                .environmentObject(state)
        }
        .menuBarExtraStyle(.window)

        Window("gmind", id: "main") {
            MainWindowView()
                .environmentObject(state)
        }
        .defaultSize(width: 520, height: 424)
        .windowResizability(.contentSize)
    }
}
