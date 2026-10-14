#!/usr/bin/python3
"""进入启用 profile 时切换 InputStudio；用 macOS kqueue 监听配置变化。"""
import json
from contextlib import closing
import os
from pathlib import Path
import plistlib
import select
import shutil
import subprocess
import sys
import tempfile

LABEL = "com.liuhao.keymap.input-source"
SOURCE = "com.liuhao.inputmethod.InputStudio.Wubi"
CONFIG = Path(os.environ.get("KEYMAP_CONFIG_DIR", str(Path.home() / ".config/karabiner"))) / "karabiner.json"
SCRIPT = Path(os.environ.get("KEYMAP_BIN_DIR", str(Path.home() / ".local/bin"))) / "karabiner-input-source.py"
SELECTOR = SCRIPT.with_name("keymap-select-input-source")
PLIST = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")


def enabled_profile(profiles):
    # 与 karabiner-toggle.sh 一致，profile 改名后仍可使用。
    return max(profiles, key=lambda p: (
        len(p.get("complex_modifications", {}).get("rules", []))
        + len(p.get("simple_modifications", []))
        + len(p.get("fn_function_keys", []))
    ))["name"]


def sync_profile(config, previous, switch):
    profiles = config["profiles"]
    current = next((p["name"] for p in profiles if p.get("selected")), None)
    if current is not None and current != previous and current == enabled_profile(profiles):
        switch()
    return current if current is not None else previous


def switch_input_source():
    try:
        subprocess.run([str(SELECTOR), SOURCE], check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as error:
        print("InputStudio 切换失败: " + str(error), file=sys.stderr, flush=True)


def watch():
    previous = None
    watched = {}
    with closing(select.kqueue()) as queue:
        while True:
            # 同时监听文件与目录，兼容原地写入和原子替换 karabiner.json。
            for path in (CONFIG.parent, CONFIG):
                try:
                    stat = path.stat()
                    identity = (stat.st_dev, stat.st_ino)
                    if path in watched and watched[path][1] == identity:
                        continue
                    if path in watched:
                        os.close(watched.pop(path)[0])
                    fd = os.open(str(path), os.O_RDONLY)
                    event = select.kevent(
                        fd, filter=select.KQ_FILTER_VNODE,
                        flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                        fflags=select.KQ_NOTE_WRITE | select.KQ_NOTE_RENAME | select.KQ_NOTE_DELETE,
                    )
                    queue.control([event], 0, 0)
                    watched[path] = (fd, identity)
                except FileNotFoundError:
                    if path in watched:
                        os.close(watched.pop(path)[0])
            try:
                with CONFIG.open() as stream:
                    previous = sync_profile(json.load(stream), previous, switch_input_source)
            except (OSError, ValueError, KeyError, TypeError) as error:
                # 写入中或文件暂时缺失时保留上次状态，下一轮重读。
                print("等待有效 Karabiner 配置: " + str(error), file=sys.stderr, flush=True)
            # 超时用于恢复短暂缺失的文件/目录；正常切换由原生事件立即唤醒。
            queue.control(None, 8, 1)


def manage(mode):
    domain = "gui/" + str(os.getuid())
    if mode == "install":
        SCRIPT.parent.mkdir(parents=True, exist_ok=True)
        source = Path(os.environ.get("KEYMAP_INPUT_SOURCE_SWIFT", str(Path(__file__).with_name("select-input-source.swift"))))
        compiled = SELECTOR.with_suffix(".new")
        # setup.sh 远程下载使用无后缀临时文件；swiftc 需要 .swift 后缀。
        with tempfile.TemporaryDirectory(prefix="keymap-build-") as build:
            swift = Path(build) / "select-input-source.swift"
            shutil.copyfile(source, swift)
            subprocess.run(["/usr/bin/xcrun", "swiftc", "-O", str(swift), "-o", str(compiled)], check=True)
        compiled.replace(SELECTOR)
    subprocess.run(["/bin/launchctl", "bootout", domain + "/" + LABEL],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if mode == "uninstall":
        PLIST.unlink(missing_ok=True)
        SCRIPT.unlink(missing_ok=True)
        SELECTOR.unlink(missing_ok=True)
        return
    SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    if Path(__file__).resolve() != SCRIPT.resolve():
        shutil.copyfile(__file__, SCRIPT)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    log = Path.home() / "Library/Logs/keymap-input-source.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with PLIST.open("wb") as stream:
        plistlib.dump({
            "Label": LABEL,
            "ProgramArguments": ["/usr/bin/python3", str(SCRIPT)],
            "EnvironmentVariables": {"KEYMAP_CONFIG_DIR": str(CONFIG.parent), "KEYMAP_BIN_DIR": str(SCRIPT.parent)},
            "RunAtLoad": True,
            "KeepAlive": True,
            "StandardErrorPath": str(log),
        }, stream)
    subprocess.run(["/bin/launchctl", "bootstrap", domain, str(PLIST)], check=True)
    print("已启用菜单栏 profile → InputStudio 联动")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        watch()
    elif sys.argv[1:] in (["install"], ["uninstall"]):
        manage(sys.argv[1])
    else:
        sys.exit("用法: karabiner-input-source.py [install|uninstall]")
