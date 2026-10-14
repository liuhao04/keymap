#!/usr/bin/python3
"""仅用于安装/移除原生联动程序；运行时不启动 Python。"""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

LABEL = "com.liuhao.keymap.input-source"
CONFIG = Path(os.environ.get("KEYMAP_CONFIG_DIR", str(Path.home() / ".config/karabiner")))
BIN = Path(os.environ.get("KEYMAP_BIN_DIR", str(Path.home() / ".local/bin")))
AGENT = BIN / "keymap-input-source"
PLIST = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")


def manage(mode):
    domain = "gui/" + str(os.getuid())
    if mode == "install":
        BIN.mkdir(parents=True, exist_ok=True)
        source = Path(os.environ.get("KEYMAP_INPUT_SOURCE_SWIFT",
                                    str(Path(__file__).with_suffix(".swift"))))
        # setup.sh 下载的临时文件可能没有 .swift 后缀。
        with tempfile.TemporaryDirectory(prefix="keymap-build-") as build:
            swift = Path(build) / "keymap.swift"
            shutil.copyfile(source, swift)
            compiled = AGENT.with_suffix(".new")
            subprocess.run(["/usr/bin/xcrun", "swiftc", "-parse-as-library", "-O",
                            str(swift), "-o", str(compiled)], check=True)
            compiled.replace(AGENT)
    subprocess.run(["/bin/launchctl", "bootout", domain + "/" + LABEL],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if mode == "uninstall":
        PLIST.unlink(missing_ok=True)
        AGENT.unlink(missing_ok=True)
    else:
        PLIST.parent.mkdir(parents=True, exist_ok=True)
        log = Path.home() / "Library/Logs/keymap-input-source.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with PLIST.open("wb") as stream:
            plistlib.dump({
                "Label": LABEL,
                "ProgramArguments": [str(AGENT), "--watch"],
                "EnvironmentVariables": {"KEYMAP_CONFIG_DIR": str(CONFIG)},
                "RunAtLoad": True,
                "KeepAlive": True,
                "StandardErrorPath": str(log),
            }, stream)
        subprocess.run(["/bin/launchctl", "bootstrap", domain, str(PLIST)], check=True)
        # 只保留安装入口，供 setup.sh restore 使用。
        installed = BIN / "karabiner-input-source.py"
        if Path(__file__).resolve() != installed.resolve():
            shutil.copyfile(__file__, installed)
        print("已启用原生双向联动：on → InputStudio；off → 系统简体拼音")
    # 清除上一版拆分的切换工具（原监听器已 bootout）。
    (BIN / "keymap-select-input-source").unlink(missing_ok=True)
    if mode == "uninstall":
        (BIN / "karabiner-input-source.py").unlink(missing_ok=True)


if __name__ == "__main__":
    if sys.argv[1:] in (["install"], ["uninstall"]):
        manage(sys.argv[1])
    else:
        sys.exit("用法: karabiner-input-source.py install|uninstall")
