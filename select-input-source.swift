import Carbon
import Foundation

func sourceID(_ source: TISInputSource) -> String {
    Unmanaged<CFString>.fromOpaque(
        TISGetInputSourceProperty(source, kTISPropertyInputSourceID)
    ).takeUnretainedValue() as String
}

if CommandLine.arguments.count == 1 {
    print(sourceID(TISCopyCurrentKeyboardInputSource().takeRetainedValue()))
    exit(0)
}

let requested = CommandLine.arguments[1]
let sources = TISCreateInputSourceList(nil, false).takeRetainedValue() as! [TISInputSource]
guard let source = sources.first(where: { sourceID($0) == requested }) else {
    fputs("Input source is not enabled: \(requested)\n", stderr)
    exit(1)
}
let status = TISSelectInputSource(source)
guard status == noErr else {
    fputs("TISSelectInputSource failed: \(status)\n", stderr)
    exit(1)
}
