import AppKit
import Darwin
import Foundation

final class SingleInstanceLock {
    static let shared = SingleInstanceLock()

    private var lockFileDescriptor: Int32 = -1

    private init() {}

    func acquire() -> Bool {
        let lockURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(
                "Library/Application Support/gmind/gmind-app.lock",
                isDirectory: false
            )

        do {
            try FileManager.default.createDirectory(
                at: lockURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
        } catch {
            return true
        }

        let descriptor = open(lockURL.path, O_CREAT | O_RDWR, S_IRUSR | S_IWUSR)
        guard descriptor >= 0 else {
            return true
        }

        if flock(descriptor, LOCK_EX | LOCK_NB) == 0 {
            lockFileDescriptor = descriptor
            return true
        }

        close(descriptor)
        return false
    }

    func activateExistingInstance() {
        guard let bundleIdentifier = Bundle.main.bundleIdentifier else {
            return
        }

        let currentProcessID = NSRunningApplication.current.processIdentifier
        let existing = NSRunningApplication
            .runningApplications(withBundleIdentifier: bundleIdentifier)
            .first { $0.processIdentifier != currentProcessID }

        existing?.activate(options: [.activateIgnoringOtherApps])
    }
}
