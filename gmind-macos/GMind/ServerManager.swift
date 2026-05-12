import Foundation

/// Manages the gmind Python HTTP server subprocess.
class ServerManager {
    static let shared = ServerManager()
    
    private var task: Process?
    private let baseURL = "http://127.0.0.1:8765"
    private var isRunningCheck = false
    
    private init() {}
    
    /// Check if gmind server is already running.
    func isServerRunning() -> Bool {
        guard let url = URL(string: "\(baseURL)/check") else { return false }
        var request = URLRequest(url: url)
        request.timeoutInterval = 2
        
        let semaphore = DispatchSemaphore(value: 0)
        var reachable = false
        
        URLSession.shared.dataTask(with: request) { _, response, _ in
            reachable = (response as? HTTPURLResponse)?.statusCode == 200
            semaphore.signal()
        }.resume()
        
        _ = semaphore.wait(timeout: .now() + 3)
        return reachable
    }
    
    /// Start gmind serve if not already running.
    func ensureRunning() {
        guard !isRunningCheck else { return }
        isRunningCheck = true
        defer { isRunningCheck = false }
        
        if isServerRunning() {
            print("✅ GMind server already running")
            return
        }
        
        // Find gmind binary
        let gmindPath = findGMindBinary()
        guard let path = gmindPath else {
            print("❌ gmind binary not found. Make sure it's in PATH.")
            return
        }
        
        let task = Process()
        task.executableURL = URL(fileURLWithPath: path)
        task.arguments = ["serve", "--port", "8765"]
        task.standardOutput = FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        
        do {
            try task.run()
            self.task = task
            print("🚀 Started GMind server")
            
            // Wait a moment for server to be ready
            Thread.sleep(forTimeInterval: 2)
        } catch {
            print("❌ Failed to start server: \(error)")
        }
    }
    
    func stop() {
        task?.terminate()
        task = nil
    }
    
    private func findGMindBinary() -> String? {
        // Check common locations
        let candidates = [
            "/usr/local/bin/gmind",
            "/opt/homebrew/bin/gmind",
            "\(NSHomeDirectory())/.local/bin/gmind",
            "\(NSHomeDirectory())/gmind/.venv/bin/gmind",
        ]
        
        for path in candidates {
            if FileManager.default.isExecutableFile(atPath: path) {
                return path
            }
        }
        
        // Try which gmind
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/which")
        task.arguments = ["gmind"]
        let pipe = Pipe()
        task.standardOutput = pipe
        try? task.run()
        task.waitUntilExit()
        
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        if let path = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
           !path.isEmpty,
           FileManager.default.isExecutableFile(atPath: path) {
            return path
        }
        
        return nil
    }
}
