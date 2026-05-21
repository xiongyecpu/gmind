import Foundation

struct FinderServiceInstallState: Sendable {
    let installed: Bool
    let message: String
}

struct FinderServiceInstaller: Sendable {
    private let workflowName = "Send to Gmind.workflow"

    func registerAppBundle() -> FinderServiceInstallState {
        let servicesURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Services", isDirectory: true)
        let workflowURL = servicesURL.appendingPathComponent(
            workflowName,
            isDirectory: true
        )
        let contentsURL = workflowURL.appendingPathComponent(
            "Contents",
            isDirectory: true
        )
        let helperURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(
                "Library/Application Support/gmind/send-to-gmind.zsh",
                isDirectory: false
            )

        do {
            try FileManager.default.createDirectory(
                at: contentsURL,
                withIntermediateDirectories: true
            )
            try FileManager.default.createDirectory(
                at: helperURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try Self.helperScript.write(
                to: helperURL,
                atomically: true,
                encoding: .utf8
            )
            try FileManager.default.setAttributes(
                [.posixPermissions: 0o755],
                ofItemAtPath: helperURL.path
            )
            try infoPlist.write(
                to: contentsURL.appendingPathComponent("Info.plist"),
                atomically: true,
                encoding: .utf8
            )
            try documentWorkflow.write(
                to: contentsURL.appendingPathComponent("document.wflow"),
                atomically: true,
                encoding: .utf8
            )
            try? run(
                executable: "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister",
                arguments: ["-u", Bundle.main.bundleURL.path]
            )
            try run(
                executable: "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister",
                arguments: ["-f", workflowURL.path]
            )
            try run(
                executable: "/System/Library/CoreServices/pbs",
                arguments: ["-flush"]
            )
            return FinderServiceInstallState(
                installed: true,
                message: "已安装到 Finder 快速操作 / 服务"
            )
        } catch {
            return FinderServiceInstallState(
                installed: false,
                message: "注册失败：\(error.localizedDescription)"
            )
        }
    }

    private func run(executable: String, arguments: [String]) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.standardOutput = Pipe()
        process.standardError = Pipe()
        try process.run()
        process.waitUntilExit()

        guard process.terminationStatus == 0 else {
            throw NSError(
                domain: "dev.gmind.finder-service",
                code: Int(process.terminationStatus),
                userInfo: [NSLocalizedDescriptionKey: "\(executable) failed"]
            )
        }
    }

    private var infoPlist: String {
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>CFBundleIdentifier</key>
          <string>dev.gmind.finder-service</string>
          <key>CFBundleName</key>
          <string>Send to Gmind</string>
          <key>NSServices</key>
          <array>
            <dict>
              <key>NSMenuItem</key>
              <dict>
                <key>default</key>
                <string>Send to Gmind</string>
              </dict>
              <key>NSMessage</key>
              <string>runWorkflowAsService</string>
              <key>NSSendFileTypes</key>
              <array>
                <string>public.data</string>
              </array>
            </dict>
          </array>
        </dict>
        </plist>
        """
    }

    private var documentWorkflow: String {
        let script = Self.shellScript
        return """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>AMApplicationBuild</key>
          <string>521</string>
          <key>AMApplicationVersion</key>
          <string>2.10</string>
          <key>AMDocumentVersion</key>
          <string>2</string>
          <key>actions</key>
          <array>
            <dict>
              <key>action</key>
              <dict>
                <key>AMAccepts</key>
                <dict>
                  <key>Container</key>
                  <string>List</string>
                  <key>Optional</key>
                  <false/>
                  <key>Types</key>
                  <array>
                    <string>com.apple.cocoa.path</string>
                  </array>
                </dict>
                <key>AMActionVersion</key>
                <string>2.0.3</string>
                <key>AMApplication</key>
                <array>
                  <string>Automator</string>
                </array>
                <key>AMParameterProperties</key>
                <dict>
                  <key>COMMAND_STRING</key>
                  <dict/>
                  <key>inputMethod</key>
                  <dict/>
                  <key>shell</key>
                  <dict/>
                </dict>
                <key>AMProvides</key>
                <dict>
                  <key>Container</key>
                  <string>List</string>
                  <key>Types</key>
                  <array>
                    <string>com.apple.cocoa.string</string>
                  </array>
                </dict>
                <key>ActionBundlePath</key>
                <string>/System/Library/Automator/Run Shell Script.action</string>
                <key>ActionName</key>
                <string>Run Shell Script</string>
                <key>ActionParameters</key>
                <dict>
                  <key>COMMAND_STRING</key>
                  <string>\(script.xmlEscaped)</string>
                  <key>CheckedForUserDefaultShell</key>
                  <true/>
                  <key>inputMethod</key>
                  <integer>1</integer>
                  <key>shell</key>
                  <string>/bin/zsh</string>
                </dict>
              </dict>
              <key>isViewVisible</key>
              <true/>
            </dict>
          </array>
          <key>connectors</key>
          <dict/>
          <key>workflowMetaData</key>
          <dict>
            <key>applicationBundleIDsByPath</key>
            <dict>
              <key>/System/Library/CoreServices/Finder.app</key>
              <string>com.apple.finder</string>
            </dict>
            <key>serviceInputTypeIdentifier</key>
            <string>com.apple.Automator.fileSystemObject</string>
            <key>serviceOutputTypeIdentifier</key>
            <string>com.apple.Automator.nothing</string>
            <key>serviceProcessesInput</key>
            <integer>0</integer>
            <key>workflowTypeIdentifier</key>
            <string>com.apple.Automator.servicesMenu</string>
          </dict>
        </dict>
        </plist>
        """
    }

    private static var shellScript: String {
        #"""
        set -u

        helper="$HOME/Library/Application Support/gmind/send-to-gmind.zsh"

        if [[ ! -x "$helper" ]]; then
          /usr/bin/osascript -e 'display notification "需要先打开 Gmind 重新注册 Finder 菜单。" with title "Gmind"' >/dev/null 2>&1 || true
          exit 1
        fi

        /usr/bin/nohup /bin/zsh "$helper" "$@" >/tmp/gmind-send-to-gmind-launch.log 2>&1 &
        exit 0
        """#
    }

    private static var helperScript: String {
        #"""
        #!/bin/zsh
        set -u

        log_dir="$HOME/Library/Logs/gmind"
        /bin/mkdir -p "$log_dir"
        exec >>"$log_dir/send-to-gmind.log" 2>&1

        echo "---- $(/bin/date '+%Y-%m-%d %H:%M:%S') Send to Gmind ----"

        cli="$HOME/.local/bin/gmind"
        config="$HOME/.gmind/gmind.toml"
        api_key="$(/usr/bin/security find-generic-password -s gmind -a SILICONFLOW_API_KEY -w 2>/dev/null || true)"

        notify() {
          /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1 &
        }

        if [[ ! -x "$cli" ]]; then
          notify "Gmind" "需要先启动 Gmind 安装命令行工具。"
          exit 1
        fi

        if [[ ! -f "$config" ]]; then
          notify "Gmind" "需要先在 Gmind 设置里保存数据库配置。"
          exit 1
        fi

        if [[ -z "$api_key" ]]; then
          notify "Gmind" "需要先在 Gmind 设置里保存 AI 密钥。"
          exit 1
        fi

        ok=0
        failed=0
        skipped=0

        for file in "$@"; do
          [[ -f "$file" ]] || { skipped=$((skipped + 1)); continue; }
          name="${file:t}"
          title="${name%.*}"
          ext="${file:e:l}"

          case "$ext" in
            md|markdown) kind="markdown" ;;
            txt) kind="text" ;;
            *) skipped=$((skipped + 1)); continue ;;
          esac

          echo "Importing $kind: $file"
          if SILICONFLOW_API_KEY="$api_key" "$cli" add "$kind" --title "$title" --file "$file" --json --config "$config"; then
            ok=$((ok + 1))
          else
            failed=$((failed + 1))
          fi
        done

        if [[ "$failed" -eq 0 && "$skipped" -eq 0 ]]; then
          notify "Gmind" "已加入 $ok 个文件。"
        else
          notify "Gmind" "$ok 个文件已加入，$((failed + skipped)) 个文件未处理。"
        fi
        """#
    }
}

private extension String {
    var xmlEscaped: String {
        replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "\"", with: "&quot;")
            .replacingOccurrences(of: "'", with: "&apos;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
    }
}
