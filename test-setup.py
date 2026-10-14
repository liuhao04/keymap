"""离线安装前检查：python3 -B test-setup.py（不会改动本机 Karabiner）。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("installer", ROOT / "karabiner-input-source.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="keymap-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = self.root / "config"
        self.bin = self.root / "bin"
        self.cfg.mkdir()
        self.bin.mkdir()
        self.original = {"profiles": [{"name": "Owner A"}, {"name": "Owner B", "selected": True}]}
        (self.cfg / "karabiner.json").write_text(json.dumps(self.original))
        (self.bin / "karabiner-toggle.sh").write_text("previous toggle\n")
        self.env = dict(os.environ, KEYMAP_SKIP_APP="1", KEYMAP_CONFIG_DIR=str(self.cfg),
                        KEYMAP_BIN_DIR=str(self.bin), KEYMAP_CACHE_DIR=str(self.root / "cache"))

    def run_setup(self, mode="install", env=None):
        return subprocess.run(["bash", str(ROOT / "setup.sh"), mode], env=env or self.env,
                              capture_output=True, text=True)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def test_check_does_not_change_files(self):
        before = self.snapshot()
        result = self.run_setup("check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_config_leaves_existing_install_untouched(self):
        (self.cfg / "karabiner.json").write_text("{")
        before = self.snapshot()
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_foreign_on_profile_is_not_overwritten(self):
        (self.cfg / "karabiner.json").write_text(json.dumps({"profiles": [{"name": "on"}]}))
        before = self.snapshot()
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("同名 profile", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_reinstall_preserves_original_selection_for_restore(self):
        for _ in range(2):
            result = self.run_setup()
            self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((self.cfg / ".keymap-state.json").read_text())
        self.assertEqual(state["previous_selected"], "Owner B")
        result = self.run_setup("restore")
        self.assertEqual(result.returncode, 0, result.stderr)
        profiles = json.loads((self.cfg / "karabiner.json").read_text())["profiles"]
        self.assertEqual([p["name"] for p in profiles], ["Owner A", "Owner B"])
        self.assertEqual([p["name"] for p in profiles if p.get("selected")], ["Owner B"])

    def test_missing_python_stops_before_mutation(self):
        commands = self.root / "commands"
        commands.mkdir()
        python = commands / "python3"
        python.write_text("#!/bin/sh\nexit 1\n")
        python.chmod(0o755)
        before = self.snapshot()
        result = self.run_setup(env=dict(self.env, PATH=str(commands) + os.pathsep + os.environ["PATH"]))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 3.8", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_missing_command_line_tools_stops_before_mutation(self):
        commands = self.root / "commands"
        commands.mkdir()
        for name, body in {"uname": "echo Darwin", "id": "echo 501", "xcode-select": "exit 1"}.items():
            executable = commands / name
            executable.write_text("#!/bin/sh\n" + body + "\n")
            executable.chmod(0o755)
        before = self.snapshot()
        env = dict(self.env, KEYMAP_SKIP_APP="0", PATH=str(commands) + os.pathsep + os.environ["PATH"])
        result = self.run_setup(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("xcode-select --install", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_remote_resource_failure_stops_before_mutation(self):
        # 只有 bootstrap，没有相邻资源，模拟 curl | bash 的下载分支。
        bootstrap = self.root / "bootstrap"
        bootstrap.mkdir()
        script = bootstrap / "setup.sh"
        script.write_bytes((ROOT / "setup.sh").read_bytes())
        commands = self.root / "commands"
        commands.mkdir()
        curl = commands / "curl"
        curl.write_text("#!" + sys.executable + "\n"
                        "import pathlib, sys\n"
                        "name = next(a for a in sys.argv if a.startswith('https://')).rsplit('/', 1)[-1]\n"
                        "if name == 'profiles.json': sys.exit(22)\n"
                        "pathlib.Path(sys.argv[sys.argv.index('-o') + 1]).write_bytes("
                        + repr((ROOT / "karabiner-toggle.sh").read_bytes()) + ")\n")
        curl.chmod(0o755)
        before = {p: p.read_bytes() for folder in (self.cfg, self.bin) for p in folder.iterdir()}
        result = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                                env=dict(self.env, PATH=str(commands) + os.pathsep + os.environ["PATH"]))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("下载 profiles.json 失败", result.stderr)
        after = {p: p.read_bytes() for folder in (self.cfg, self.bin) for p in folder.iterdir()}
        self.assertEqual(after, before)

    def test_compile_or_input_source_failure_does_not_replace_agent(self):
        for fail_at in ("compile", "sources", "session"):
            with self.subTest(fail_at=fail_at):
                calls = []
                def fake_run(command, **kwargs):
                    calls.append(command)
                    if command[0] == "/bin/launchctl" and fail_at == "session":
                        raise subprocess.CalledProcessError(1, command)
                    if command[0] == "/usr/bin/xcrun":
                        if fail_at == "compile":
                            raise subprocess.CalledProcessError(1, command)
                        Path(command[-1]).write_text("compiled")
                    if command[-1] == "--check-input-sources" and fail_at == "sources":
                        raise subprocess.CalledProcessError(1, command)
                    return subprocess.CompletedProcess(command, 0)
                before = self.snapshot()
                with patch.object(installer, "BIN", self.bin), \
                     patch.object(installer, "AGENT", self.bin / "keymap-input-source"), \
                     patch.object(installer.sys, "platform", "darwin"), \
                     patch.object(installer.os, "getuid", return_value=501), \
                     patch.object(installer.subprocess, "run", side_effect=fake_run), \
                     patch.dict(os.environ, {"KEYMAP_INPUT_SOURCE_SWIFT": str(ROOT / "karabiner-input-source.swift")}), \
                     self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    installer.manage("install")
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(any("bootout" in c or "bootstrap" in c for c in calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
