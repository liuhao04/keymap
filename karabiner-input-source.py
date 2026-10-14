#!/usr/bin/python3
"""仅用于安装/移除原生联动程序；运行时不启动 Python。"""
import os
import json
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


def validate_configuration(profiles_path):
    """只读检查，必须早于备份、复制脚本和改写 Karabiner 配置。"""
    incoming = json.loads(Path(profiles_path).read_text())
    cfg = CONFIG / "karabiner.json"
    existing = json.loads(cfg.read_text()) if cfg.exists() else {"profiles": []}
    profiles = existing.get("profiles") if isinstance(existing, dict) else None
    for items in (incoming, profiles):
        if not isinstance(items, list) or any(
            not isinstance(p, dict) or not isinstance(p.get("name"), str) for p in items
        ):
            raise ValueError("profiles 必须是带 name 的 profile 数组")
        if len({p["name"] for p in items}) != len(items):
            raise ValueError("profile 名称重复，请先在 Karabiner 中整理")
    if {p["name"] for p in incoming} != {"on", "off"}:
        raise ValueError("下载的配置必须包含 on 和 off 两个 profile")
    for profile in profiles:
        if profile["name"] in {"on", "off"} and "karabiner-toggle.sh" not in json.dumps(profile):
            raise ValueError("已有同名 profile 属于其他配置，请先重命名：" + profile["name"])
    state = CONFIG / ".keymap-state.json"
    if state.exists():
        saved = json.loads(state.read_text())
        if not isinstance(saved, dict) or not isinstance(saved.get("installed"), list):
            raise ValueError("已有安装记录无效，请先检查 .keymap-state.json")
    for directory in (CONFIG, BIN, PLIST.parent):
        parent = directory
        while not parent.exists():
            parent = parent.parent
        if not parent.is_dir():
            raise ValueError("目标目录被普通文件占用：" + str(parent))
    for target in (cfg, state, BIN, PLIST):
        parent = target if target.exists() else target.parent
        while not parent.exists():
            parent = parent.parent
        if not os.access(parent, os.W_OK):
            raise ValueError("没有写入权限：" + str(parent))
    print("配置和目标路径检查通过（未修改配置）")


def prepare(output):
    """在暂存目录实际编译并检查输入源，失败时不改动已安装文件。"""
    if sys.platform != "darwin" or os.getuid() == 0:
        raise ValueError("请在目标 Mac 的已登录用户 Terminal 中执行，不要使用 sudo")
    try:
        subprocess.run(["/bin/launchctl", "print", "gui/" + str(os.getuid())],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        raise ValueError("未找到当前用户的图形登录会话，请登录桌面后在 Terminal 中重试") from None
    source = Path(os.environ.get("KEYMAP_INPUT_SOURCE_SWIFT",
                                str(Path(__file__).with_suffix(".swift"))))
    with tempfile.TemporaryDirectory(prefix="keymap-build-") as build:
        swift = Path(build) / "keymap.swift"
        shutil.copyfile(source, swift)
        compiled = Path(build) / "keymap-input-source"
        subprocess.run(["/usr/bin/xcrun", "swiftc", "-parse-as-library", "-O",
                        str(swift), "-o", str(compiled)], check=True)
        subprocess.run([str(compiled), "--check-input-sources"], check=True)
        shutil.copy2(compiled, output)
    print("原生程序编译及登录会话检查通过")


def manage(mode):
    domain = "gui/" + str(os.getuid())
    if mode == "install":
        with tempfile.TemporaryDirectory(prefix="keymap-install-") as build:
            prepared = os.environ.get("KEYMAP_PREPARED_AGENT")
            if not prepared:
                prepared = str(Path(build) / "keymap-input-source")
                prepare(prepared)
            BIN.mkdir(parents=True, exist_ok=True)
            compiled = AGENT.with_suffix(".new")
            shutil.copy2(prepared, compiled)
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
    try:
        if sys.argv[1:] in (["install"], ["uninstall"]):
            manage(sys.argv[1])
        elif len(sys.argv) == 3 and sys.argv[1] == "prepare":
            prepare(sys.argv[2])
        elif len(sys.argv) == 3 and sys.argv[1] == "validate":
            validate_configuration(sys.argv[2])
        else:
            sys.exit("用法: karabiner-input-source.py install|uninstall|prepare 输出路径|validate profiles.json")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit("安装失败：" + str(error) + "\n请修复上述问题后重试；编译工具可用 xcode-select --install 安装。")
