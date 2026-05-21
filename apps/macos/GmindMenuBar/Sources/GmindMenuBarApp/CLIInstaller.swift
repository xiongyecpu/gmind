import Foundation

struct CLIInstallState: Sendable {
    let installed: Bool
    let message: String
}

struct CLIInstaller: Sendable {
    let binURL: URL

    init(
        binURL: URL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".local/bin", isDirectory: true)
    ) {
        self.binURL = binURL
    }

    var linkURL: URL {
        binURL.appendingPathComponent("gmind")
    }

    func bundledCLIURL() -> URL? {
        Bundle.main.resourceURL?
            .appendingPathComponent("cli", isDirectory: true)
            .appendingPathComponent("gmind")
    }

    func installOrUpdate() -> CLIInstallState {
        guard let cliURL = bundledCLIURL() else {
            return CLIInstallState(
                installed: false,
                message: "开发模式：未找到内置 CLI"
            )
        }

        guard FileManager.default.fileExists(atPath: cliURL.path) else {
            return CLIInstallState(
                installed: false,
                message: "App 内没有 CLI"
            )
        }

        do {
            var replacedExistingCommand = false
            try FileManager.default.createDirectory(
                at: binURL,
                withIntermediateDirectories: true
            )

            if FileManager.default.fileExists(atPath: linkURL.path) {
                let values = try linkURL.resourceValues(forKeys: [.isSymbolicLinkKey])
                if values.isSymbolicLink == true {
                    try FileManager.default.removeItem(at: linkURL)
                } else {
                    try moveExistingCommandAside()
                    replacedExistingCommand = true
                }
            }

            try FileManager.default.createSymbolicLink(
                at: linkURL,
                withDestinationURL: cliURL
            )

            return CLIInstallState(
                installed: true,
                message: replacedExistingCommand
                    ? "旧 CLI 已备份，已安装新版"
                    : "CLI 已安装到 ~/.local/bin/gmind"
            )
        } catch {
            return CLIInstallState(
                installed: false,
                message: "CLI 安装失败：\(error.localizedDescription)"
            )
        }
    }

    private func moveExistingCommandAside() throws {
        let backupURL = binURL.appendingPathComponent(
            "gmind.backup.\(Int(Date().timeIntervalSince1970))"
        )
        try FileManager.default.moveItem(at: linkURL, to: backupURL)
    }
}
