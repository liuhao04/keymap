import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "input_source", Path(__file__).with_name("karabiner-input-source.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProfileSyncTests(unittest.TestCase):
    def config(self, selected, on="on", off="off"):
        return {"profiles": [
            {"name": on, "selected": selected == on, "simple_modifications": [{}]},
            {"name": off, "selected": selected == off},
        ]}

    def test_only_switch_on_entry(self):
        calls = []
        previous = None
        for selected in ("off", "on", "on", "off", "off", "on"):
            previous = module.sync_profile(self.config(selected), previous, lambda: calls.append(1))
        self.assertEqual(calls, [1, 1])

    def test_initial_on_and_renamed_profiles(self):
        calls = []
        previous = module.sync_profile(
            self.config("Enabled", "Enabled", "Disabled"), None, lambda: calls.append(1))
        self.assertEqual(previous, "Enabled")
        self.assertEqual(calls, [1])

    def test_unrelated_config_edit_does_not_reset_input_source(self):
        config = self.config("on")
        config["global"] = {"show_profile_name_in_menu_bar": True}
        self.assertEqual(module.sync_profile(config, "on", self.fail), "on")

    def test_missing_selection_keeps_previous_state(self):
        self.assertEqual(module.sync_profile(self.config(None), "on", self.fail), "on")


if __name__ == "__main__":
    unittest.main()
