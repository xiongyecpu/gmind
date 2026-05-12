import SwiftUI

struct SettingsView: View {
    @AppStorage("gmindServerAutoStart") private var autoStartServer = true
    @AppStorage("gmindServerPort") private var serverPort = "8765"
    @AppStorage("gmindShortcutAdd") private var shortcutAdd = "⌘⇧A"
    @AppStorage("gmindShortcutSearch") private var shortcutSearch = "⌘⇧S"
    
    @State private var serverStatus = "Checking..."
    @State private var isServerOnline = false
    
    var body: some View {
        TabView {
            // General
            Form {
                Section {
                    Toggle("Auto-start GMind server on launch", isOn: $autoStartServer)
                    
                    HStack {
                        TextField("Port", text: $serverPort)
                            .frame(width: 80)
                        Text("Server port")
                            .foregroundStyle(.secondary)
                    }
                }
                
                Section {
                    HStack {
                        Circle()
                            .fill(isServerOnline ? Color.green : Color.red)
                            .frame(width: 8, height: 8)
                        Text("Status: \(serverStatus)")
                        Spacer()
                        Button("Refresh") {
                            checkServer()
                        }
                    }
                }
            }
            .tabItem {
                Label("General", systemImage: "gear")
            }
            
            // Shortcuts
            Form {
                Text("Global shortcuts (configure in System Settings → Keyboard → Shortcuts)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                
                HStack {
                    Text("Quick Add")
                    Spacer()
                    Text(shortcutAdd)
                        .foregroundStyle(.secondary)
                }
                
                HStack {
                    Text("Quick Search")
                    Spacer()
                    Text(shortcutSearch)
                        .foregroundStyle(.secondary)
                }
            }
            .tabItem {
                Label("Shortcuts", systemImage: "keyboard")
            }
            
            // About
            VStack(spacing: 16) {
                Text("🧠")
                    .font(.system(size: 64))
                Text("GMind")
                    .font(.title)
                Text("Knowledge Graph & Vector Search")
                    .foregroundStyle(.secondary)
                Text("Version 3.0")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                
                Divider()
                
                Link("github.com/xiongyecpu/gmind", destination: URL(string: "https://github.com/xiongyecpu/gmind")!)
            }
            .padding()
            .tabItem {
                Label("About", systemImage: "info.circle")
            }
        }
        .frame(width: 480, height: 320)
        .onAppear { checkServer() }
    }
    
    private func checkServer() {
        serverStatus = "Checking..."
        let online = ServerManager.shared.isServerRunning()
        isServerOnline = online
        serverStatus = online ? "Online" : "Offline"
    }
}

#Preview {
    SettingsView()
}
