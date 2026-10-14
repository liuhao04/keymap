import Foundation

@main
struct ProfileSyncTests {
    static func main() throws {
        let template = try JSONSerialization.jsonObject(with: Data(contentsOf:
            URL(fileURLWithPath: CommandLine.arguments[1]))) as! [[String: Any]]
        func config(_ selected: String?, on: String = "on", off: String = "off") throws -> ProfileConfig {
            var profiles = template
            for index in profiles.indices {
                profiles[index]["name"] = profiles[index]["name"] as? String == "on" ? on : off
                profiles[index]["selected"] = profiles[index]["name"] as? String == selected
            }
            profiles.append(["name": "Owner", "selected": selected == "Owner",
                             "simple_modifications": Array(repeating: [:] as [String: Any], count: 100)])
            return try ProfileConfig(data: JSONSerialization.data(withJSONObject: ["profiles": profiles]))
        }
        let sync = ProfileSync()
        var calls: [String] = []
        for selected in ["off", "on", "on", "off", "off", "Owner", "on"] {
            try sync.update(config(selected)) { calls.append($0) }
        }
        precondition(calls == [systemPinyin, inputStudio, systemPinyin, inputStudio])
        print("PASS bidirectional transitions; repeated/foreign profiles do not switch")

        try sync.update(config(nil)) { _ in preconditionFailure("Missing selection must not switch") }
        try sync.update(config("on")) { _ in preconditionFailure("Unchanged profile must not switch") }
        print("PASS missing selection and unrelated config writes preserve manual input-source choice")

        let renamed = ProfileSync()
        var renamedCalls: [String] = []
        for name in ["Enabled", "Disabled"] {
            try renamed.update(config(name, on: "Enabled", off: "Disabled")) { renamedCalls.append($0) }
        }
        precondition(renamedCalls == [inputStudio, systemPinyin])
        print("PASS renamed owned profiles; foreign profile rule counts are ignored")

        let failed = ProfileSync()
        do {
            try failed.update(config("on")) { _ in throw SyncError.unavailableSource("test") }
            preconditionFailure("Selection error must propagate")
        } catch SyncError.unavailableSource { }
        try failed.update(config("on")) { _ in preconditionFailure("Must not repeatedly force input source") }
        do {
            _ = try ProfileConfig(data: Data("{\"profiles\":[]}".utf8))
            preconditionFailure("Missing owned profiles must fail safely")
        } catch SyncError.missingProfiles { }
        print("PASS unavailable source and missing owned profiles")
    }
}
