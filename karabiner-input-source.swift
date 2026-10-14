import Carbon
import Foundation

let inputStudio = "com.liuhao.inputmethod.InputStudio.Wubi"
let systemPinyin = "com.apple.inputmethod.SCIM.ITABC"
let configURL = URL(fileURLWithPath: ProcessInfo.processInfo.environment["KEYMAP_CONFIG_DIR"]
    ?? NSHomeDirectory() + "/.config/karabiner").appendingPathComponent("karabiner.json")

enum SyncError: Error { case invalidConfig, missingProfiles, unavailableSource(String), selectionFailed(OSStatus) }

struct ProfileConfig {
    let selected: String?
    let on: String
    let off: String

    init(data: Data) throws {
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let profiles = root["profiles"] as? [[String: Any]] else { throw SyncError.invalidConfig }
        selected = profiles.first { $0["selected"] as? Bool == true }?["name"] as? String
        // 只识别本项目拥有的 profile，避免把借用机器的其他 profile 当成 on/off。
        let owned = profiles.filter { profile in
            let rules = (profile["complex_modifications"] as? [String: Any])?["rules"] as? [[String: Any]] ?? []
            return rules.contains { rule in
                (rule["manipulators"] as? [[String: Any]] ?? []).contains { manipulator in
                    (manipulator["to"] as? [[String: Any]] ?? []).contains {
                        ($0["shell_command"] as? String)?.hasSuffix("/karabiner-toggle.sh") == true
                        || $0["shell_command"] as? String == "__TOGGLE__"
                    }
                }
            }
        }
        guard owned.count == 2 else { throw SyncError.missingProfiles }
        func weight(_ p: [String: Any]) -> Int {
            let rules = (p["complex_modifications"] as? [String: Any])?["rules"] as? [Any] ?? []
            return rules.count + (p["simple_modifications"] as? [Any] ?? []).count
                + (p["fn_function_keys"] as? [Any] ?? []).count
        }
        let sorted = owned.sorted { weight($0) < weight($1) }
        guard let first = sorted.first?["name"] as? String,
              let last = sorted.last?["name"] as? String,
              first != last, weight(sorted[0]) != weight(sorted[1]) else { throw SyncError.missingProfiles }
        off = first
        on = last
    }

    var inputSource: String? {
        if selected == on { return inputStudio }
        if selected == off { return systemPinyin }
        return nil
    }
}

func sourceID(_ source: TISInputSource) -> String {
    Unmanaged<CFString>.fromOpaque(TISGetInputSourceProperty(source, kTISPropertyInputSourceID))
        .takeUnretainedValue() as String
}

func selectInputSource(_ requested: String) throws {
    let current = TISCopyCurrentKeyboardInputSource().takeRetainedValue()
    if sourceID(current) == requested { return }
    let sources = TISCreateInputSourceList(nil, false).takeRetainedValue() as! [TISInputSource]
    guard let source = sources.first(where: { sourceID($0) == requested }) else {
        throw SyncError.unavailableSource(requested)
    }
    let status = TISSelectInputSource(source)
    guard status == noErr else { throw SyncError.selectionFailed(status) }
}

final class ProfileSync {
    private var previous: String?
    func update(_ config: ProfileConfig, select: (String) throws -> Void) throws {
        guard let current = config.selected, current != previous else { return }
        // 一次进入只尝试一次；之后手动切换输入法不会被覆盖。
        previous = current
        if let source = config.inputSource { try select(source) }
    }
}

final class ProfileWatcher {
    private struct Watch {
        let device: dev_t
        let inode: ino_t
        let source: DispatchSourceFileSystemObject
    }
    private var watched: [String: Watch] = [:]
    private var pending: DispatchWorkItem?
    private var lastError: String?
    private let sync = ProfileSync()

    private func schedule(after delay: Double = 0.03) {
        pending?.cancel()
        let work = DispatchWorkItem { [weak self] in self?.reconcile() }
        pending = work
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: work)
    }

    private func watch(_ url: URL) throws {
        let path = url.path
        var info = stat()
        guard stat(path, &info) == 0 else {
            watched.removeValue(forKey: path)?.source.cancel()
            throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
        }
        if let existing = watched[path], existing.device == info.st_dev, existing.inode == info.st_ino { return }
        watched.removeValue(forKey: path)?.source.cancel()
        let fd = open(path, O_EVTONLY)
        guard fd >= 0 else { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO) }
        let source = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: fd, eventMask: [.write, .rename, .delete, .revoke], queue: .main)
        source.setEventHandler { [weak self] in self?.schedule() }
        source.setCancelHandler { close(fd) }
        watched[path] = Watch(device: info.st_dev, inode: info.st_ino, source: source)
        source.resume()
    }

    func reconcile() {
        do {
            // 目录处理原子替换，文件处理原地写入；空闲时没有轮询。
            try watch(configURL.deletingLastPathComponent())
            try watch(configURL)
            try sync.update(ProfileConfig(data: Data(contentsOf: configURL)), select: selectInputSource)
            lastError = nil
        } catch {
            let message = "keymap: \(error)\n"
            if message != lastError { fputs(message, stderr); lastError = message }
            // 仅在文件短暂缺失/写入中等错误期间重试，并保留上次 profile。
            schedule(after: 1)
        }
    }
}

#if !KEYMAP_TEST
@main
struct KeymapInputSource {
    static func main() {
        do {
            switch Array(CommandLine.arguments.dropFirst()) {
            case ["--watch"]:
                let watcher = ProfileWatcher()
                watcher.reconcile()
                withExtendedLifetime(watcher) { RunLoop.main.run() }
            case ["--toggle"]:
                let config = try ProfileConfig(data: Data(contentsOf: configURL))
                let process = Process()
                process.executableURL = URL(fileURLWithPath:
                    "/Library/Application Support/org.pqrs/Karabiner-Elements/bin/karabiner_cli")
                process.arguments = ["--select-profile", config.selected == config.off ? config.on : config.off]
                try process.run()
                process.waitUntilExit()
                exit(process.terminationStatus)
            case []:
                print(sourceID(TISCopyCurrentKeyboardInputSource().takeRetainedValue()))
            case let args where args.count == 1 && !args[0].hasPrefix("--"):
                try selectInputSource(args[0])
            default:
                fputs("用法: keymap-input-source [--watch|--toggle|输入源ID]\n", stderr)
                exit(1)
            }
        } catch {
            fputs("keymap: \(error)\n", stderr)
            exit(1)
        }
    }
}
#endif
