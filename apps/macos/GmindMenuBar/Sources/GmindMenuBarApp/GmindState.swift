import AppKit
import Foundation
import UserNotifications

@MainActor
final class GmindState: ObservableObject {
    @Published var databaseURL: String
    @Published var apiKey: String
    @Published var soloEnabled: Bool
    @Published var statusText = "还没有检查"
    @Published var isBusy = false
    @Published var entities: [EntitySummary] = []
    @Published var selectedEntity: EntitySummary?
    @Published var entityDetail: EntityDetail?
    @Published var addTitle = ""
    @Published var addText = ""
    @Published var selectedSection = "ask"
    @Published var askQuestion = "项目 A 当前进展如何？还有什么需要跟进？"
    @Published var askAnswer = "提一个问题，gmind 会从已有知识里找线索并给出回答。"
    @Published var askEvidenceChips: [String] = ["等待提问"]
    @Published var cliInstallLabel = "正在检查 CLI..."
    @Published var finderServiceLabel = "正在注册 Finder 菜单..."

    let configStore = ConfigStore()
    let keychainStore = KeychainStore()
    let cliInstaller = CLIInstaller()
    let finderServiceInstaller = FinderServiceInstaller()

    private var cli: GmindCLI {
        GmindCLI(configURL: configStore.configURL)
    }

    init() {
        self.databaseURL = configStore.loadDatabaseURL()
        self.apiKey = keychainStore.loadAPIKey()
        self.soloEnabled = configStore.loadSoloSettings().enabled
        requestNotificationPermission()
        registerCLI()
        registerFinderService()
    }

    var readyLabel: String {
        if databaseURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "需要设置数据库"
        }
        if apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "需要填写 AI 密钥"
        }
        if isBusy {
            return "正在工作"
        }
        if statusText == "还没有检查" || statusText == "可以使用" {
            return "可提问"
        }
        return statusText
    }

    var knowledgeLabel: String {
        let claimCount = entities.reduce(0) { $0 + $1.claimCount }
        let eventCount = entities.reduce(0) { $0 + $1.eventCount }
        return "\(entities.count) 个实体，\(claimCount) 条事实，\(eventCount) 个事件"
    }

    var knowledgeCounts: (entities: Int, claims: Int, events: Int) {
        let claimCount = entities.reduce(0) { $0 + $1.claimCount }
        let eventCount = entities.reduce(0) { $0 + $1.eventCount }
        return (entities.count, claimCount, eventCount)
    }

    func saveSettings() {
        let configStore = configStore
        let keychainStore = keychainStore
        let databaseURL = databaseURL
        let apiKey = apiKey
        let soloSettings = soloSettings
        runBusy("正在保存设置...") {
            try configStore.save(databaseURL: databaseURL, soloSettings: soloSettings)
            try keychainStore.saveAPIKey(apiKey)
        } onSuccess: {
            self.statusText = "设置已保存"
        }
    }

    func testConnection() {
        let configStore = configStore
        let keychainStore = keychainStore
        let databaseURL = databaseURL
        let apiKey = apiKey
        let soloSettings = soloSettings
        let cli = cli

        runBusy("正在检查连接...") {
            try configStore.save(databaseURL: databaseURL, soloSettings: soloSettings)
            try keychainStore.saveAPIKey(apiKey)
            let result = try cli.dbCheck(apiKey: apiKey)
            if result.succeeded {
                return ConnectionCheckResult(
                    command: result,
                    entities: try cli.entities(apiKey: apiKey)
                )
            }
            return ConnectionCheckResult(command: result, entities: [])
        } onSuccess: { check in
            if check.command.succeeded {
                self.entities = check.entities
                self.statusText = "可以使用"
            } else {
                self.statusText = self.friendlyError(check.command.humanMessage)
            }
        }
    }

    func addPastedText() {
        let title = addTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        let text = addText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !title.isEmpty else {
            statusText = "请先给资料起个标题"
            return
        }
        guard !text.isEmpty else {
            statusText = "请先粘贴一些内容"
            return
        }

        let configStore = configStore
        let keychainStore = keychainStore
        let databaseURL = databaseURL
        let apiKey = apiKey
        let soloSettings = soloSettings
        let cli = cli

        runBusy("正在阅读资料...") {
            try configStore.save(databaseURL: databaseURL, soloSettings: soloSettings)
            try keychainStore.saveAPIKey(apiKey)
            let fileURL = try configStore.writeImport(title: title, text: text)
            return try Self.processFile(
                title: title,
                fileURL: fileURL,
                cli: cli,
                apiKey: apiKey
            )
        } onSuccess: { entities in
            self.entities = entities
            self.addTitle = ""
            self.addText = ""
            self.statusText = "完成：资料已整理"
        }
    }

    func addFile(_ fileURL: URL) {
        let title = fileURL.deletingPathExtension().lastPathComponent
        let configStore = configStore
        let keychainStore = keychainStore
        let databaseURL = databaseURL
        let apiKey = apiKey
        let soloSettings = soloSettings
        let cli = cli

        runBusy("正在阅读资料...") {
            try configStore.save(databaseURL: databaseURL, soloSettings: soloSettings)
            try keychainStore.saveAPIKey(apiKey)
            return try Self.processFile(
                title: title,
                fileURL: fileURL,
                cli: cli,
                apiKey: apiKey
            )
        } onSuccess: { entities in
            self.entities = entities
            self.statusText = "完成：资料已整理"
        }
    }

    func addFinderFiles(_ fileURLs: [URL]) {
        let supportedURLs = fileURLs.filter { GmindCLI.supportsAddFile($0) }
        let unsupportedCount = fileURLs.count - supportedURLs.count
        guard !supportedURLs.isEmpty else {
            statusText = "暂不支持这些文件"
            notify(title: "Gmind", message: "暂只支持 .md、.markdown 和 .txt 文件。")
            return
        }

        let configStore = configStore
        let keychainStore = keychainStore
        let databaseURL = databaseURL
        let apiKey = apiKey
        let soloSettings = soloSettings
        let cli = cli

        runBusy("正在送入 Gmind...") {
            try configStore.save(databaseURL: databaseURL, soloSettings: soloSettings)
            try keychainStore.saveAPIKey(apiKey)
            return try Self.processFinderFiles(
                supportedURLs,
                unsupportedCount: unsupportedCount,
                cli: cli,
                apiKey: apiKey
            )
        } onSuccess: { result in
            self.entities = result.entities
            self.statusText = result.statusText
            self.notify(title: "Gmind", message: result.notificationText)
        }
    }

    func refreshKnowledge() {
        let cli = cli
        let apiKey = apiKey

        runBusy("正在读取知识...") {
            try cli.entities(apiKey: apiKey)
        } onSuccess: { entities in
            self.entities = entities
            self.statusText = "可以使用"
        }
    }

    func ask() {
        let question = askQuestion.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !question.isEmpty else {
            statusText = "先输入问题"
            askAnswer = "先输入一个你想知道的问题。"
            askEvidenceChips = ["需要问题"]
            return
        }

        let configStore = configStore
        let keychainStore = keychainStore
        let databaseURL = databaseURL
        let apiKey = apiKey
        let soloSettings = soloSettings
        let cli = cli

        runBusy("正在回答...") {
            try configStore.save(databaseURL: databaseURL, soloSettings: soloSettings)
            try keychainStore.saveAPIKey(apiKey)
            let response = try cli.ask(question: question, apiKey: apiKey)
            let entities = try cli.entities(apiKey: apiKey)
            return AskResult(
                answer: response.answer,
                evidenceChips: Self.evidenceChips(from: response),
                entities: entities
            )
        } onSuccess: { result in
            self.entities = result.entities
            self.askAnswer = result.answer
            self.askEvidenceChips = result.evidenceChips
            self.statusText = "可以使用"
        }
    }

    func selectEntity(_ entity: EntitySummary) {
        selectedEntity = entity
        let cli = cli
        let apiKey = apiKey

        runBusy("正在打开知识...") {
            try cli.entity(name: entity.name, apiKey: apiKey)
        } onSuccess: { detail in
            self.entityDetail = detail
            self.statusText = "可以使用"
        }
    }

    func openConfigFolder() {
        NSWorkspace.shared.open(configStore.homeURL)
    }

    func registerCLI() {
        let result = cliInstaller.installOrUpdate()
        cliInstallLabel = result.message
    }

    func registerFinderService() {
        let result = finderServiceInstaller.registerAppBundle()
        NSUpdateDynamicServices()
        finderServiceLabel = result.message
    }

    private var soloSettings: SoloSettings {
        SoloSettings(enabled: soloEnabled)
    }


    nonisolated private static func processFile(
        title: String,
        fileURL: URL,
        cli: GmindCLI,
        apiKey: String
    ) throws -> [EntitySummary] {
        try cli.add(title: title, fileURL: fileURL, apiKey: apiKey)
        return try cli.entities(apiKey: apiKey)
    }

    nonisolated private static func processFinderFiles(
        _ fileURLs: [URL],
        unsupportedCount: Int,
        cli: GmindCLI,
        apiKey: String
    ) throws -> FinderImportResult {
        var successCount = 0
        var failureCount = 0

        for fileURL in fileURLs {
            do {
                let title = fileURL.deletingPathExtension().lastPathComponent
                try cli.add(title: title, fileURL: fileURL, apiKey: apiKey)
                successCount += 1
            } catch {
                failureCount += 1
            }
        }

        let entities = try cli.entities(apiKey: apiKey)
        return FinderImportResult(
            successCount: successCount,
            failureCount: failureCount,
            unsupportedCount: unsupportedCount,
            entities: entities
        )
    }

    nonisolated private static func evidenceChips(from response: AskCLIResponse) -> [String] {
        var chips = response.evidence.prefix(3).map { evidence in
            String(format: "%.2f · %@", evidence.score, evidence.title)
        }
        chips.append(contentsOf: response.followups.prefix(1))
        return chips.isEmpty ? ["暂无证据"] : Array(chips.prefix(4))
    }

    private func runBusy<T: Sendable>(
        _ message: String,
        work: @escaping @Sendable () throws -> T,
        onSuccess: @escaping @MainActor (T) -> Void
    ) {
        isBusy = true
        statusText = message
        Task.detached(priority: .userInitiated) {
            do {
                let value = try work()
                await MainActor.run {
                    onSuccess(value)
                    self.isBusy = false
                }
            } catch {
                await MainActor.run {
                    self.statusText = self.friendlyError(error.localizedDescription)
                    self.isBusy = false
                }
            }
        }
    }

    private func friendlyError(_ message: String) -> String {
        if message.contains("password authentication failed") {
            return "数据库密码不对"
        }
        if message.contains("Missing API key") {
            return "需要填写 AI 密钥"
        }
        if message.contains("Connection refused") || message.contains("connection failed") {
            return "数据库连不上"
        }
        if message.isEmpty {
            return "操作失败"
        }
        return message
    }

    private func notify(title: String, message: String) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = message

        let request = UNNotificationRequest(
            identifier: "gmind.finder.\(UUID().uuidString)",
            content: content,
            trigger: nil
        )
        UNUserNotificationCenter.current().add(request)
    }

    private func requestNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .sound]
        ) { _, _ in }
    }
}

struct FinderImportResult: Sendable {
    let successCount: Int
    let failureCount: Int
    let unsupportedCount: Int
    let entities: [EntitySummary]

    var statusText: String {
        if failureCount == 0 && unsupportedCount == 0 {
            return "完成：\(successCount) 个文件已送入"
        }
        return "完成：\(successCount) 个成功，\(failureCount + unsupportedCount) 个未处理"
    }

    var notificationText: String {
        if failureCount == 0 && unsupportedCount == 0 {
            return "已加入 \(successCount) 个文件。"
        }
        return "\(successCount) 个文件已加入，\(failureCount + unsupportedCount) 个文件未处理。"
    }
}
