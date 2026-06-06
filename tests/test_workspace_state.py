import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ca_app.gui.main_frame import (
    CaAppFrame,
    DEFAULT_RESTORE_LEVEL,
    DEFAULT_WORKSPACE,
    RESTORE_PARAMETERS,
    RESTORE_TAB,
    RESTORE_VIEW,
    load_app_state,
    load_workspace_state,
    save_app_state,
    save_workspace_state,
)

try:
    import wx
except ImportError:
    wx = None


class WorkspaceStateTests(unittest.TestCase):
    def test_missing_or_invalid_workspace_state_defaults_to_afm_kpfm(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "app_state.json"
            self.assertEqual(load_workspace_state(missing), DEFAULT_WORKSPACE)

            missing.write_text("{invalid", encoding="utf-8")
            self.assertEqual(load_workspace_state(missing), DEFAULT_WORKSPACE)

            missing.write_text('{"last_workspace": "Unknown"}', encoding="utf-8")
            self.assertEqual(load_workspace_state(missing), DEFAULT_WORKSPACE)

    def test_valid_workspace_state_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "app_state.json"

            save_workspace_state(path, "APS")

            self.assertEqual(load_workspace_state(path), "APS")

            save_workspace_state(path, "Raman")

            self.assertEqual(load_workspace_state(path), "Raman")

    def test_app_state_defaults_and_legacy_workspace_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app_state.json"

            self.assertEqual(load_app_state(path)["last_workspace"], DEFAULT_WORKSPACE)
            self.assertEqual(load_app_state(path)["restore_level"], DEFAULT_RESTORE_LEVEL)

            path.write_text('{"last_workspace": "APS"}', encoding="utf-8")
            state = load_app_state(path)

            self.assertEqual(state["last_workspace"], "APS")
            self.assertEqual(state["restore_level"], DEFAULT_RESTORE_LEVEL)
            self.assertEqual(state["tabs"], {})
            self.assertEqual(state["parameters"], {})

    def test_app_state_round_trips_restore_level_tabs_and_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app_state.json"
            payload = {
                "restore_level": RESTORE_PARAMETERS,
                "last_workspace": "Raman",
                "tabs": {"Raman": [{"selection": 2, "pages": ["A", "B", "C"]}]},
                "parameters": {"TPC": {"setting_current_mA": "12"}},
            }

            save_app_state(path, payload)
            state = load_app_state(path)

            self.assertEqual(state["restore_level"], RESTORE_PARAMETERS)
            self.assertEqual(state["last_workspace"], "Raman")
            self.assertEqual(state["tabs"]["Raman"][0]["selection"], 2)
            self.assertEqual(state["parameters"]["TPC"]["setting_current_mA"], "12")


@unittest.skipIf(wx is None, "wxPython is not available")
class AppStateGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def make_frame(self, state_path):
        class TestFrame(CaAppFrame):
            def state_file_path(self_inner):
                return state_path

        return TestFrame()

    def test_view_menu_is_before_restore_and_updates_restore_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = self.make_frame(Path(tmp) / "app_state.json")
            try:
                menu_bar = frame.GetMenuBar()
                self.assertEqual(menu_bar.GetMenuLabel(0), "&View")
                self.assertEqual(menu_bar.GetMenuLabel(1), "Restore")
                self.assertEqual(menu_bar.GetMenuLabel(2), "&About")

                frame.on_restore_level(None, RESTORE_TAB)

                self.assertEqual(frame.restore_level, RESTORE_TAB)
                self.assertTrue(frame.restore_menu_items[RESTORE_TAB].IsChecked())
            finally:
                frame.Destroy()

    def test_tab_restore_matches_notebooks_by_page_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = self.make_frame(Path(tmp) / "app_state.json")
            try:
                raman = frame.workspace_panels["Raman"]
                old_state = [
                    {"selection": 2, "pages": ["Substrate Baseline", "Mapping", "Insitu EChem"]},
                    {"selection": 1, "pages": ["Peak windows", "Analysis"]},
                ]

                frame.apply_panel_tab_state(raman, old_state)

                self.assertEqual(raman.notebook.GetSelection(), 2)
                self.assertEqual(raman.insitu_page.insitu_notebook.GetSelection(), 1)
                self.assertEqual(raman.mapping_page.mapping_notebook.GetSelection(), 0)
            finally:
                frame.Destroy()

    def test_tpc_parameter_restore_does_not_restore_output_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame = self.make_frame(Path(tmp) / "app_state.json")
            try:
                panel = frame.workspace_panels["TPC"]
                panel.output_is_on = True
                panel.command_running = True

                panel.apply_app_parameters({
                    "red_ld": True,
                    "green_ld": False,
                    "com_port": "COM9",
                    "baudrate": "57600",
                    "setting_current_mA": "11",
                })

                self.assertFalse(panel.output_is_on)
                self.assertFalse(panel.command_running)
                self.assertTrue(panel.red_ld.IsChecked())
                self.assertEqual(panel.tc_com_port.GetValue(), "COM9")
            finally:
                frame.Destroy()
