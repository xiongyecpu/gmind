import Foundation

struct ConfigStore: Sendable {
    let homeURL: URL

    var configURL: URL {
        homeURL.appendingPathComponent("gmind.toml")
    }

    var importsURL: URL {
        homeURL.appendingPathComponent("imports", isDirectory: true)
    }

    var soloDefaultFolderURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Downloads", isDirectory: true)
    }

    init(
        homeURL: URL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".gmind", isDirectory: true)
    ) {
        self.homeURL = homeURL
    }

    func ensureHome() throws {
        try FileManager.default.createDirectory(
            at: homeURL,
            withIntermediateDirectories: true
        )
        try FileManager.default.createDirectory(
            at: importsURL,
            withIntermediateDirectories: true
        )
    }

    func loadDatabaseURL() -> String {
        if let databaseURL = loadDatabaseURL(from: configURL) {
            return databaseURL
        }

        let projectConfigURL = Self.findProjectRoot()
            .appendingPathComponent("gmind.toml")
        if let databaseURL = loadDatabaseURL(from: projectConfigURL) {
            return databaseURL
        }

        return ""
    }

    func loadSoloSettings() -> SoloSettings {
        if let settings = loadSoloSettings(from: configURL) {
            return settings
        }

        let projectConfigURL = Self.findProjectRoot()
            .appendingPathComponent("gmind.toml")
        if let settings = loadSoloSettings(from: projectConfigURL) {
            return settings
        }

        return SoloSettings(enabled: false)
    }

    func loadDatabaseURL(from url: URL) -> String? {
        guard let content = try? String(contentsOf: url, encoding: .utf8) else {
            return nil
        }

        for line in content.components(separatedBy: .newlines) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard trimmed.hasPrefix("url = ") else {
                continue
            }
            return trimmed
                .replacingOccurrences(of: "url = ", with: "")
                .trimmingCharacters(in: CharacterSet(charactersIn: "\" "))
        }

        return nil
    }

    func loadSoloSettings(from url: URL) -> SoloSettings? {
        guard let content = try? String(contentsOf: url, encoding: .utf8) else {
            return nil
        }

        var inSoloSection = false
        var enabled: Bool?

        for line in content.components(separatedBy: .newlines) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed == "[solo]" {
                inSoloSection = true
                continue
            }
            if trimmed.hasPrefix("[") {
                inSoloSection = false
            }
            guard inSoloSection, trimmed.hasPrefix("enabled = ") else {
                continue
            }
            let value = trimmed
                .replacingOccurrences(of: "enabled = ", with: "")
                .trimmingCharacters(in: CharacterSet(charactersIn: "\" "))
            enabled = value == "true"
        }

        guard let enabled else {
            return nil
        }
        return SoloSettings(enabled: enabled)
    }

    func save(databaseURL: String, soloSettings: SoloSettings) throws {
        try ensureHome()
        let content = """
        # gmind configuration

        [database]
        url = "\(databaseURL)"

        [models]
        llm_provider = "siliconflow"
        llm_model = "Qwen/Qwen3.6-35B-A3B"
        llm_base_url = "https://api.siliconflow.cn/v1"
        llm_api_key_env = "SILICONFLOW_API_KEY"
        embedding_provider = "siliconflow"
        embedding_model = "Qwen/Qwen3-Embedding-4B"
        embedding_dim = 1536
        embedding_base_url = "https://api.siliconflow.cn/v1"
        embedding_api_key_env = "SILICONFLOW_API_KEY"

        [solo]
        enabled = \(soloSettings.enabled ? "true" : "false")

        """
        try content.write(to: configURL, atomically: true, encoding: .utf8)
    }

    func writeImport(title: String, text: String) throws -> URL {
        try ensureHome()
        let safeTitle = title
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "/", with: "-")
        let name = safeTitle.isEmpty ? "untitled" : safeTitle
        let filename = "\(Int(Date().timeIntervalSince1970))-\(name).txt"
        let fileURL = importsURL.appendingPathComponent(filename)
        try text.write(to: fileURL, atomically: true, encoding: .utf8)
        return fileURL
    }

    static func findProjectRoot() -> URL {
        var url = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        for _ in 0..<8 {
            let marker = url.appendingPathComponent("pyproject.toml")
            if FileManager.default.fileExists(atPath: marker.path) {
                return url
            }
            url.deleteLastPathComponent()
        }
        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }
}
