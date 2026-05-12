import SwiftUI

enum TaotieTab: String, CaseIterable {
    case scan = "扫描结果"
    case queue = "入库队列"
    case watcher = "监听文件夹"
    case history = "导入历史"
}

enum FileFilter: String, CaseIterable {
    case knowledge = "知识文件"
    case sensitive = "隐私文件"
    case filtered = "已过滤"
}

struct TaotieView: View {
    let onClose: () -> Void

    @State private var selectedTab: TaotieTab = .scan
    @State private var fileFilter: FileFilter = .knowledge

    // Scan state
    @State private var isScanning = false
    @State private var scanResult: TaotieScanResult?
    @State private var scanError: String?

    // File selection
    // selected state is stored in scanResult.files[].selected

    // Queue state
    @State private var queueState: TaotieQueueState?
    @State private var isQueueRefreshing = false
    @State private var queueTimer: Timer?

    // History
    @State private var historyRecords: [TaotieHistoryRecord] = []

    // Watcher
    @State private var watcherFolders: [TaotieWatcherFolder] = []

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("🍽️ 饕餮盛宴")
                    .font(.headline)
                Spacer()
                Button(action: onClose) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding()

            // Tab picker
            Picker("", selection: $selectedTab) {
                ForEach(TaotieTab.allCases, id: \.self) { tab in
                    Text(tab.rawValue).tag(tab)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)

            Divider()

            // Content
            Group {
                switch selectedTab {
                case .scan:
                    scanView
                case .queue:
                    queueView
                case .watcher:
                    watcherView
                case .history:
                    historyView
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(width: 600, height: 520)
        .background(Color.clear)
        .onAppear {
            loadWatcher()
            loadHistory()
        }
        .onDisappear {
            queueTimer?.invalidate()
        }
        .onChange(of: selectedTab) { newTab in
            if newTab == .queue {
                startQueueRefresh()
            } else {
                queueTimer?.invalidate()
            }
        }
    }

    // MARK: - Scan View

    private var scanView: some View {
        VStack(spacing: 0) {
            if isScanning {
                Spacer()
                ProgressView("扫描中...")
                Spacer()
            } else if scanResult != nil {
                // Filter tabs
                HStack(spacing: 0) {
                    ForEach(FileFilter.allCases, id: \.self) { filter in
                        Button(filter.rawValue) {
                            fileFilter = filter
                        }
                        .buttonStyle(.plain)
                        .padding(.vertical, 6)
                        .padding(.horizontal, 12)
                        .background(fileFilter == filter ? Color.accentColor.opacity(0.15) : Color.clear)
                        .foregroundColor(fileFilter == filter ? .accentColor : .secondary)
                        .cornerRadius(6)
                    }
                    Spacer()
                    Text("\(filteredFiles.count) 个文件")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.horizontal)
                .padding(.top, 8)

                // File list
                List(filteredFiles) { file in
                    HStack(spacing: 8) {
                        Toggle("", isOn: Binding(
                            get: { scanResult?.files.first(where: { $0.path == file.path })?.selected ?? true },
                            set: { newValue in
                                toggleFileSelection(file.path, selected: newValue)
                            }
                        ))
                        .toggleStyle(.checkbox)
                        .labelsHidden()

                        fileIcon(for: file.ext)
                            .foregroundStyle(.secondary)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(fileName(from: file.path))
                                .font(.system(size: 12))
                                .lineLimit(1)
                            Text(file.path)
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }

                        Spacer()

                        if file.privacyLevel != "safe" {
                            Image(systemName: file.privacyLevel == "private" ? "lock.fill" : "exclamationmark.triangle.fill")
                                .foregroundStyle(file.privacyLevel == "private" ? .red : .orange)
                                .font(.system(size: 10))
                        }

                        Text(byteString(file.size))
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 2)
                }
                .listStyle(.plain)

                // Actions
                HStack {
                    Button("重新扫描") { startScan() }
                        .font(.caption)
                    Spacer()
                    Button("不入库") {
                        markSelectedAsBlacklist()
                    }
                    .font(.caption)
                    .disabled(selectedFiles().isEmpty)
                    Button("开始入库") {
                        addSelectedToQueue()
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                    .disabled(selectedFiles().isEmpty)
                }
                .padding()
            } else {
                Spacer()
                VStack(spacing: 16) {
                    Image(systemName: "folder.badge.gear")
                        .font(.system(size: 48))
                        .foregroundStyle(.secondary.opacity(0.3))
                    Text("点击开始扫描全电脑")
                        .foregroundStyle(.secondary)
                    Button("开始扫描") { startScan() }
                        .buttonStyle(.borderedProminent)
                }
                Spacer()
            }
        }
    }

    private var filteredFiles: [TaotieFile] {
        guard let result = scanResult else { return [] }
        switch fileFilter {
        case .knowledge:
            return result.files.filter { $0.shouldIngest && $0.privacyLevel == "safe" }
        case .sensitive:
            return result.files.filter { $0.privacyLevel != "safe" }
        case .filtered:
            return result.files.filter { !$0.shouldIngest }
        }
    }

    // MARK: - Queue View

    private var queueView: some View {
        VStack(spacing: 0) {
            if let state = queueState {
                // Current
                if let current = state.current {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("正在入库")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        HStack {
                            Text(fileName(from: current.path))
                                .font(.system(size: 12))
                            Spacer()
                            Text("\(Int(current.progress * 100))%")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        ProgressView(value: current.progress)
                            .progressViewStyle(.linear)
                    }
                    .padding()
                    .background(.thinMaterial)
                }

                // Stats
                HStack(spacing: 16) {
                    StatBadge(label: "排队", count: state.pending.count, color: .blue)
                    StatBadge(label: "完成", count: state.done.count, color: .green)
                    StatBadge(label: "错误", count: state.error.count, color: .red)
                }
                .padding(.horizontal)
                .padding(.top, 8)

                // Pending list
                if !state.pending.isEmpty {
                    List(state.pending) { task in
                        HStack {
                            Toggle("", isOn: Binding(
                                get: { task.selected },
                                set: { _ in }
                            ))
                            .toggleStyle(.checkbox)
                            .labelsHidden()
                            .disabled(true)

                            Text(fileName(from: task.path))
                                .font(.system(size: 12))
                            Spacer()
                            Button("移除") {
                                removeFromQueue(task.path)
                            }
                            .font(.caption)
                        }
                    }
                    .listStyle(.plain)
                } else {
                    Spacer()
                    Text(state.done.isEmpty ? "队列为空" : "全部完成")
                        .foregroundStyle(.secondary)
                    Spacer()
                }

                // Controls
                HStack {
                    Button("清空队列") {
                        clearQueue()
                    }
                    .font(.caption)
                    Spacer()
                    if state.paused {
                        Button("继续") {
                            resumeQueue()
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                    } else if state.current != nil || !state.pending.isEmpty {
                        Button("暂停") {
                            pauseQueue()
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                    }
                }
                .padding()
            } else {
                Spacer()
                ProgressView("加载中...")
                Spacer()
            }
        }
    }

    // MARK: - Watcher View

    private var watcherView: some View {
        VStack(spacing: 0) {
            if let result = scanResult, !result.folders.isEmpty {
                Text("扫描发现的文件夹")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal)
                    .padding(.top, 8)

                List(result.folders) { folder in
                    HStack(spacing: 8) {
                        Toggle("", isOn: Binding(
                            get: { folder.checked },
                            set: { newValue in
                                updateFolderChecked(folder.path, checked: newValue)
                            }
                        ))
                        .toggleStyle(.checkbox)
                        .labelsHidden()

                        Image(systemName: folder.isAgentSession ? "bubble.left.and.bubble.right" : "folder")
                            .foregroundStyle(.secondary)
                            .font(.system(size: 12))

                        VStack(alignment: .leading, spacing: 2) {
                            Text(fileName(from: folder.path))
                                .font(.system(size: 12))
                                .lineLimit(1)
                            Text("\(folder.knowledgeFileCount) 个知识文件")
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        Text(byteString(folder.totalSize))
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 2)
                }
                .listStyle(.plain)

                HStack {
                    Button("保存设置") {
                        saveWatcherFolders()
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                }
                .padding()
            } else {
                Spacer()
                VStack(spacing: 16) {
                    Image(systemName: "folder.badge.gearshape")
                        .font(.system(size: 48))
                        .foregroundStyle(.secondary.opacity(0.3))
                    Text("先扫描，再选择要监听的文件夹")
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
        }
    }

    // MARK: - History View

    private var historyView: some View {
        VStack(spacing: 0) {
            if historyRecords.isEmpty {
                Spacer()
                Text("暂无导入记录")
                    .foregroundStyle(.secondary)
                Spacer()
            } else {
                List(historyRecords) { record in
                    HStack(spacing: 8) {
                        Image(systemName: record.status == "ok" ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundStyle(record.status == "ok" ? .green : .red)
                            .font(.system(size: 12))

                        VStack(alignment: .leading, spacing: 2) {
                            Text(fileName(from: record.path))
                                .font(.system(size: 12))
                                .lineLimit(1)
                            HStack(spacing: 4) {
                                Text(record.timestamp.prefix(16))
                                    .font(.system(size: 10))
                                if !record.slug.isEmpty {
                                    Text("→ \(record.slug)")
                                        .font(.system(size: 10))
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .foregroundStyle(.secondary)
                        }

                        Spacer()
                    }
                    .padding(.vertical, 2)
                }
                .listStyle(.plain)
            }
        }
    }

    // MARK: - Actions

    private func startScan() {
        isScanning = true
        scanResult = nil
        scanError = nil

        GMindAPI.shared.taotieScan { result in
            DispatchQueue.main.async {
                isScanning = false
                switch result {
                case .success(let scanResult):
                    var result = scanResult
                    // Default select all safe files, deselect unsafe
                    for i in result.files.indices {
                        result.files[i].selected = result.files[i].privacyLevel == "safe"
                    }
                    self.scanResult = result
                case .failure(let error):
                    scanError = error.localizedDescription
                }
            }
        }
    }

    private func toggleFileSelection(_ path: String, selected: Bool) {
        guard var result = scanResult else { return }
        if let index = result.files.firstIndex(where: { $0.path == path }) {
            result.files[index].selected = selected
            self.scanResult = result
        }
    }

    private func selectedFiles() -> [TaotieFile] {
        scanResult?.files.filter { $0.selected } ?? []
    }

    private func markSelectedAsBlacklist() {
        let selected = selectedFiles()
        for file in selected {
            GMindAPI.shared.taotieQueueRemove(path: file.path) { _ in }
        }
        if var result = scanResult {
            let selectedPaths = Set(selected.map { $0.path })
            result.files.removeAll { selectedPaths.contains($0.path) }
            scanResult = result
        }
    }

    private func addSelectedToQueue() {
        let selected = selectedFiles()
        guard !selected.isEmpty else { return }
        GMindAPI.shared.taotieQueueAdd(files: selected) { result in
            DispatchQueue.main.async {
                switch result {
                case .success:
                    selectedTab = .queue
                    startQueue()
                case .failure:
                    break
                }
            }
        }
    }

    private func startQueue() {
        GMindAPI.shared.taotieQueueStart { _ in }
        startQueueRefresh()
    }

    private func pauseQueue() {
        GMindAPI.shared.taotieQueuePause { _ in }
    }

    private func resumeQueue() {
        GMindAPI.shared.taotieQueueStart { _ in }
    }

    private func clearQueue() {
        GMindAPI.shared.taotieQueueClear { _ in }
    }

    private func removeFromQueue(_ path: String) {
        GMindAPI.shared.taotieQueueRemove(path: path) { _ in }
    }

    private func startQueueRefresh() {
        queueTimer?.invalidate()
        refreshQueue()
        queueTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { _ in
            refreshQueue()
        }
    }

    private func refreshQueue() {
        GMindAPI.shared.taotieQueueState { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let state):
                    self.queueState = state
                case .failure:
                    break
                }
            }
        }
    }

    private func loadWatcher() {
        GMindAPI.shared.taotieWatcher { folders in
            DispatchQueue.main.async {
                self.watcherFolders = folders
            }
        }
    }

    private func saveWatcherFolders() {
        guard let result = scanResult else { return }
        for folder in result.folders where folder.checked {
            GMindAPI.shared.taotieWatcherAdd(path: folder.path) { _ in }
        }
    }

    private func updateFolderChecked(_ path: String, checked: Bool) {
        if var result = scanResult {
            if let index = result.folders.firstIndex(where: { $0.path == path }) {
                var folder = result.folders[index]
                folder.checked = checked
                result.folders[index] = folder
                scanResult = result
            }
        }
    }

    private func loadHistory() {
        GMindAPI.shared.taotieHistory(limit: 50) { records in
            DispatchQueue.main.async {
                self.historyRecords = records
            }
        }
    }

    // MARK: - Helpers

    private func fileName(from path: String) -> String {
        (path as NSString).lastPathComponent
    }

    private func byteString(_ bytes: Int) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(bytes))
    }

    private func fileIcon(for ext: String) -> Image {
        switch ext {
        case ".md":
            return Image(systemName: "doc.text")
        case ".pdf":
            return Image(systemName: "doc.richtext")
        case ".docx":
            return Image(systemName: "doc.wordprocessing")
        case ".txt":
            return Image(systemName: "doc.plaintext")
        default:
            return Image(systemName: "doc")
        }
    }
}

struct StatBadge: View {
    let label: String
    let count: Int
    let color: Color

    var body: some View {
        VStack {
            Text("\(count)")
                .font(.system(size: 16, weight: .bold))
            Text(label)
                .font(.caption2)
        }
        .frame(width: 60, height: 40)
        .background(color.opacity(0.1))
        .cornerRadius(6)
    }
}
