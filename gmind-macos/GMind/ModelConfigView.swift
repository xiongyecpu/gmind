import SwiftUI

struct ModelConfigView: View {
    let onClose: () -> Void

    @State private var provider = "openai"
    @State private var model = "deepseek-ai/DeepSeek-V4-Flash"
    @State private var apiKey = ""
    @State private var baseURL = "https://api.siliconflow.cn/v1"
    @State private var status = ""
    @State private var isSaving = false

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("模型配置")
                    .font(.headline)
                Spacer()
                Button(action: onClose) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 16))
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding([.horizontal, .top], 20)
            .padding(.bottom, 16)

            // Form
            VStack(spacing: 16) {
                Picker("Provider", selection: $provider) {
                    Text("SiliconFlow / OpenAI").tag("openai")
                    Text("Ollama (本地)").tag("ollama")
                }
                .pickerStyle(.segmented)

                VStack(alignment: .leading, spacing: 6) {
                    Text("Model")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextField("", text: $model)
                        .textFieldStyle(.roundedBorder)
                }

                if provider == "openai" {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("API Key")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        SecureField("", text: $apiKey)
                            .textFieldStyle(.roundedBorder)
                    }
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text("Base URL")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextField("", text: $baseURL)
                        .textFieldStyle(.roundedBorder)
                }
            }
            .padding(.horizontal, 20)

            Spacer()

            // Footer
            HStack {
                if !status.isEmpty {
                    Text(status)
                        .font(.caption)
                        .foregroundColor(status.hasPrefix("✅") ? .green : .red)
                }
                Spacer()
                Button("取消") { onClose() }
                Button(action: save) {
                    if isSaving {
                        ProgressView().scaleEffect(0.6)
                    } else {
                        Text("保存")
                    }
                }
                .disabled(isSaving)
                .buttonStyle(.borderedProminent)
            }
            .padding(20)
        }
        .frame(width: 400, height: 320)
        .background(Color.clear)
        .onAppear {
            loadConfig()
        }
    }

    private func loadConfig() {
        let path = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".gmind/config.toml")
        guard let content = try? String(contentsOf: path) else { return }

        for line in content.components(separatedBy: .newlines) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("provider = ") {
                provider = trimmed.replacingOccurrences(of: "provider = \"", with: "")
                    .replacingOccurrences(of: "\"", with: "")
            } else if trimmed.hasPrefix("model = ") {
                model = trimmed.replacingOccurrences(of: "model = \"", with: "")
                    .replacingOccurrences(of: "\"", with: "")
            } else if trimmed.hasPrefix("api_key = ") {
                apiKey = trimmed.replacingOccurrences(of: "api_key = \"", with: "")
                    .replacingOccurrences(of: "\"", with: "")
            } else if trimmed.hasPrefix("base_url = ") {
                baseURL = trimmed.replacingOccurrences(of: "base_url = \"", with: "")
                    .replacingOccurrences(of: "\"", with: "")
            }
        }
    }

    private func save() {
        isSaving = true
        status = ""

        let configPath = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".gmind/config.toml")

        guard let content = try? String(contentsOf: configPath) else {
            status = "❌ 找不到配置文件"
            isSaving = false
            return
        }

        var lines = content.components(separatedBy: .newlines)
        var newLines: [String] = []
        var inLLM = false

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed == "[llm]" {
                inLLM = true
                newLines.append(line)
            } else if trimmed.hasPrefix("[") && trimmed != "[llm]" {
                inLLM = false
                newLines.append(line)
            } else if inLLM && trimmed.hasPrefix("provider = ") {
                newLines.append("provider = \"\(provider)\"")
            } else if inLLM && trimmed.hasPrefix("model = ") {
                newLines.append("model = \"\(model)\"")
            } else if inLLM && trimmed.hasPrefix("api_key = ") {
                newLines.append("api_key = \"\(apiKey)\"")
            } else if inLLM && trimmed.hasPrefix("base_url = ") {
                newLines.append("base_url = \"\(baseURL)\"")
            } else {
                newLines.append(line)
            }
        }

        if !newLines.contains(where: { $0.trimmingCharacters(in: .whitespaces) == "[llm]" }) {
            newLines.append("")
            newLines.append("[llm]")
            newLines.append("provider = \"\(provider)\"")
        }

        let newContent = newLines.joined(separator: "\n")
        do {
            try newContent.write(to: configPath, atomically: true, encoding: .utf8)
            status = "✅ 已保存"
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                onClose()
            }
        } catch {
            status = "❌ 保存失败"
        }
        isSaving = false
    }
}
