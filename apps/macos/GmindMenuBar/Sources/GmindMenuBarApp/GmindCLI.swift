import Foundation

struct GmindCLI: Sendable {
    let projectRoot: URL
    let configURL: URL
    let bundledCLIURL: URL?

    init(configURL: URL) {
        self.configURL = configURL
        self.projectRoot = ConfigStore.findProjectRoot()
        self.bundledCLIURL = CLIInstaller().bundledCLIURL()
    }

    func dbCheck(apiKey: String) throws -> CommandResult {
        try run(["db", "check"], apiKey: apiKey)
    }

    func ingest(title: String, fileURL: URL, apiKey: String) throws -> Int {
        let result = try run(
            ["ingest", "text", "--title", title, "--file", fileURL.path],
            apiKey: apiKey
        )
        guard result.succeeded else {
            throw CLIError.commandFailed(result.humanMessage)
        }
        guard let sourceID = Self.extractSourceID(from: result.output) else {
            throw CLIError.commandFailed("资料已保存，但没有读到 source id。")
        }
        return sourceID
    }

    func embed(sourceID: Int, apiKey: String) throws {
        let result = try run(["embed", "source", "\(sourceID)"], apiKey: apiKey)
        guard result.succeeded else {
            throw CLIError.commandFailed(result.humanMessage)
        }
    }

    func extract(sourceID: Int, apiKey: String) throws {
        let result = try run(["extract", "llm", "\(sourceID)"], apiKey: apiKey)
        guard result.succeeded else {
            throw CLIError.commandFailed(result.humanMessage)
        }
    }

    func entities(apiKey: String) throws -> [EntitySummary] {
        let result = try run(["entities", "--json", "--limit", "100"], apiKey: apiKey)
        guard result.succeeded else {
            throw CLIError.commandFailed(result.humanMessage)
        }
        return try JSONDecoder().decode([EntitySummary].self, from: Data(result.output.utf8))
    }

    func entity(name: String, apiKey: String) throws -> EntityDetail {
        let result = try run(["entity", "show", name, "--json"], apiKey: apiKey)
        guard result.succeeded else {
            throw CLIError.commandFailed(result.humanMessage)
        }
        return try JSONDecoder().decode(EntityDetail.self, from: Data(result.output.utf8))
    }

    func ask(question: String, apiKey: String) throws -> AskCLIResponse {
        let result = try run(["ask", question, "--json"], apiKey: apiKey)
        guard result.succeeded else {
            throw CLIError.commandFailed(result.humanMessage)
        }
        return try JSONDecoder().decode(AskCLIResponse.self, from: Data(result.output.utf8))
    }

    func add(title: String, fileURL: URL, apiKey: String) throws {
        let addCommand = try Self.addCommand(for: fileURL)
        let result = try run(
            ["add", addCommand, "--title", title, "--file", fileURL.path, "--json"],
            apiKey: apiKey
        )
        guard result.succeeded else {
            throw CLIError.commandFailed(result.humanMessage)
        }
    }

    static func supportsAddFile(_ fileURL: URL) -> Bool {
        (try? addCommand(for: fileURL)) != nil
    }

    private func run(_ arguments: [String], apiKey: String) throws -> CommandResult {
        let process = Process()
        if let bundledCLIURL,
           FileManager.default.fileExists(atPath: bundledCLIURL.path)
        {
            process.executableURL = bundledCLIURL
            process.arguments = arguments + ["--config", configURL.path]
        } else {
            process.currentDirectoryURL = projectRoot
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["uv", "run", "gmind"] + arguments + [
                "--config",
                configURL.path,
            ]
        }
        process.environment = ProcessInfo.processInfo.environment.merging(
            ["SILICONFLOW_API_KEY": apiKey],
            uniquingKeysWith: { _, new in new }
        )

        let outputPipe = Pipe()
        let errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe

        try process.run()
        process.waitUntilExit()

        let output = String(
            data: outputPipe.fileHandleForReading.readDataToEndOfFile(),
            encoding: .utf8
        ) ?? ""
        let error = String(
            data: errorPipe.fileHandleForReading.readDataToEndOfFile(),
            encoding: .utf8
        ) ?? ""

        return CommandResult(
            status: process.terminationStatus,
            output: output,
            error: error
        )
    }

    private static func extractSourceID(from output: String) -> Int? {
        let pattern = #"Ingested source ([0-9]+)"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return nil
        }
        let range = NSRange(output.startIndex..<output.endIndex, in: output)
        guard
            let match = regex.firstMatch(in: output, range: range),
            let sourceRange = Range(match.range(at: 1), in: output)
        else {
            return nil
        }
        return Int(output[sourceRange])
    }

    private static func addCommand(for fileURL: URL) throws -> String {
        switch fileURL.pathExtension.lowercased() {
        case "md", "markdown":
            return "markdown"
        case "txt":
            return "text"
        default:
            throw CLIError.commandFailed("暂不支持这个文件类型。")
        }
    }
}

enum CLIError: LocalizedError {
    case commandFailed(String)

    var errorDescription: String? {
        switch self {
        case .commandFailed(let message):
            return message
        }
    }
}
