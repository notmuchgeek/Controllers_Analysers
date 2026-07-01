import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    import wx
    from ca_app.core.raman_baseline import (
        RamanBaselineSettings,
        baseline_output_targets,
        fit_raman_baseline_input,
    )
    from ca_app.gui.panels import raman_panel as raman_panel_module
    from ca_app.gui.panels.raman_panel import RamanAnalysisPanel
except ImportError:
    wx = None
    RamanBaselineSettings = None
    baseline_output_targets = None
    fit_raman_baseline_input = None
    raman_panel_module = None
    RamanAnalysisPanel = None


@unittest.skipIf(wx is None, "wxPython is not available")
class RamanBaselineMultiFileGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    @staticmethod
    def write_single(path, offset=0.0):
        rows = ["#Wave\t#Intensity"]
        for index in range(40):
            x = 100.0 + index
            baseline = 0.02 * x + offset
            peak = 10.0 / (1.0 + ((x - 120.0) / 2.0) ** 2)
            rows.append(f"{x:.6f}\t{baseline + peak:.6f}")
        path.write_text("\n".join(rows), encoding="utf-8")

    @staticmethod
    def write_sequence(path):
        rows = ["#Sequence\t#Wave\t#Intensity"]
        for sequence in (1, 2):
            for index in range(40):
                x = 100.0 + index
                baseline = 0.02 * x + sequence
                peak = 10.0 / (1.0 + ((x - 120.0) / 2.0) ** 2)
                rows.append(f"{sequence}\t{x:.6f}\t{baseline + peak:.6f}")
        path.write_text("\n".join(rows), encoding="utf-8")

    @staticmethod
    def make_panel():
        frame = wx.Frame(None)
        panel = RamanAnalysisPanel(frame).substrate_page
        panel.rb_auto.SetValue(False)
        panel.rb_manual.SetValue(True)
        panel.update_parameter_controls()
        return frame, panel

    def wait_for_fit(self, panel, timeout_s=15):
        deadline = time.monotonic() + timeout_s
        while panel.fit_running and time.monotonic() < deadline:
            wx.Yield()
            time.sleep(0.01)
        wx.Yield()
        self.assertFalse(panel.fit_running, "Baseline fit did not finish before timeout")

    def test_list_preview_and_shared_columns_support_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            single = Path(tmp) / "single.txt"
            sequence = Path(tmp) / "sequence.txt"
            self.write_single(single)
            self.write_sequence(sequence)
            frame, panel = self.make_panel()
            try:
                panel.add_paths([single, sequence])

                self.assertEqual(panel.baseline_file_list.GetItemCount(), 2)
                self.assertEqual([item.n_spectra for item in panel.items], [1, 2])
                self.assertTrue(all(item.preview_enabled for item in panel.items))
                self.assertTrue(panel.tc_baseline_selected.IsEnabled())
                self.assertFalse(panel.btn_load_wire.IsEnabled())
                self.assertFalse(panel.tc_output_name.IsEnabled())
                self.assertFalse(panel.btn_save.IsEnabled())

                panel.tc_baseline_selected.SetValue("1-2")
                self.assertTrue(panel.redraw_preview(show_warning=True))
                self.assertEqual(len(panel.preview_entries()), 3)
                old_labels = [line.get_label() for line in panel.figure_preview.axes[0].lines]

                panel.tc_baseline_selected.SetValue("3")
                panel.show_warning = lambda message: None
                self.assertFalse(panel.redraw_preview(show_warning=True))
                self.assertEqual(
                    [line.get_label() for line in panel.figure_preview.axes[0].lines],
                    old_labels,
                )
            finally:
                frame.Destroy()

    def test_fit_processes_every_file_and_save_all_preserves_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.txt"
            second = Path(tmp) / "second.txt"
            self.write_single(first)
            self.write_single(second, offset=1.0)
            frame, panel = self.make_panel()
            try:
                panel.add_paths([first, second])
                panel.tc_param1.SetValue("1000")
                panel.tc_param2.SetValue("1.0")

                panel.start_fit("Test multi-file fit.")
                self.wait_for_fit(panel)

                self.assertTrue(all(item.result is not None for item in panel.items))
                self.assertTrue(panel.btn_save_all.IsEnabled())
                self.assertFalse(panel.btn_save.IsEnabled())

                output_dir = Path(tmp) / "corrected"
                targets = baseline_output_targets(panel.items, output_dir)
                succeeded, failed = panel.save_all_to_folder(targets)

                self.assertEqual((succeeded, failed), (2, 0))
                self.assertEqual(
                    sorted(path.name for path in output_dir.iterdir()),
                    ["first_Copy.txt", "second_Copy.txt"],
                )
            finally:
                frame.Destroy()

    def test_group_preview_check_and_delete_match_converting_list_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / f"spectrum_{index}.txt" for index in range(3)]
            for index, path in enumerate(paths):
                self.write_single(path, offset=float(index))
            frame, panel = self.make_panel()
            try:
                panel.add_paths(paths)
                panel.baseline_file_list.CheckItem(0, False)
                wx.Yield()

                self.assertEqual(
                    [item.preview_enabled for item in panel.items],
                    [False, False, False],
                )

                selected = panel.reorder_items([0], wx.NOT_FOUND)
                panel.refresh_file_list(selected=selected)
                self.assertEqual(
                    [item.source_path.name for item in panel.items],
                    ["spectrum_1.txt", "spectrum_2.txt", "spectrum_0.txt"],
                )

                for index in range(3):
                    panel.baseline_file_list.SetItemState(
                        index,
                        0,
                        wx.LIST_STATE_SELECTED,
                    )
                panel.baseline_file_list.SetItemState(
                    1,
                    wx.LIST_STATE_SELECTED,
                    wx.LIST_STATE_SELECTED,
                )
                panel.on_delete(None)

                self.assertEqual(
                    [item.source_path.name for item in panel.items],
                    ["spectrum_1.txt", "spectrum_0.txt"],
                )
            finally:
                frame.Destroy()

    def test_partial_fit_disables_save_all_and_save_failures_do_not_stop_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.txt"
            second = Path(tmp) / "second.txt"
            self.write_single(first)
            self.write_single(second)
            frame, panel = self.make_panel()
            try:
                panel.add_paths([first, second])
                settings = RamanBaselineSettings(
                    method="asPLS",
                    auto=False,
                    lambda_value=1000,
                    secondary_value=1.0,
                )
                first_result = fit_raman_baseline_input(panel.items[0].source, settings)
                panel.fit_running = True
                panel.fit_started_at = time.monotonic()
                panel.show_warning = lambda message: None

                panel.on_fit_batch_finished(
                    [(panel.items[0], first_result, ("first",))],
                    [(panel.items[1], "synthetic failure")],
                    settings,
                    0,
                )

                self.assertIsNotNone(panel.items[0].result)
                self.assertIsNone(panel.items[1].result)
                self.assertFalse(panel.btn_save_all.IsEnabled())

                panel.items[1].result = first_result
                targets = baseline_output_targets(panel.items, Path(tmp) / "out")
                original_save = raman_panel_module.save_corrected_baseline_input

                def fake_save(result, target):
                    if Path(target).name.startswith("second"):
                        raise OSError("synthetic write failure")
                    Path(target).parent.mkdir(parents=True, exist_ok=True)
                    Path(target).write_text("saved", encoding="utf-8")
                    return Path(target)

                raman_panel_module.save_corrected_baseline_input = fake_save
                try:
                    succeeded, failed = panel.save_all_to_folder(targets)
                finally:
                    raman_panel_module.save_corrected_baseline_input = original_save

                self.assertEqual((succeeded, failed), (1, 1))
                self.assertTrue(targets[0].exists())
            finally:
                frame.Destroy()

    def test_restore_preserves_order_checks_and_migrates_legacy_raw_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.txt"
            second = Path(tmp) / "second.txt"
            self.write_single(first)
            self.write_single(second)
            frame, panel = self.make_panel()
            restored_frame = legacy_frame = None
            try:
                panel.add_paths([first, second])
                panel.items[1].preview_enabled = False
                panel.tc_baseline_selected.SetValue("1")
                state = panel.collect_app_parameters()

                restored_frame, restored = self.make_panel()
                restored.apply_app_parameters(state)
                self.assertEqual(
                    [item.source_path.name for item in restored.items],
                    ["first.txt", "second.txt"],
                )
                self.assertEqual(
                    [item.preview_enabled for item in restored.items],
                    [True, False],
                )
                self.assertTrue(all(item.result is None for item in restored.items))

                legacy_frame, legacy = self.make_panel()
                legacy.apply_app_parameters(
                    {
                        "raw_path": str(first),
                        "selected_columns": "1",
                        "auto": False,
                    }
                )
                self.assertEqual(len(legacy.items), 1)
                self.assertEqual(legacy.items[0].source_path, first)
                self.assertIsNone(legacy.items[0].result)
            finally:
                if legacy_frame is not None:
                    legacy_frame.Destroy()
                if restored_frame is not None:
                    restored_frame.Destroy()
                frame.Destroy()

    def test_converting_transfer_adds_to_existing_baseline_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.txt"
            second = Path(tmp) / "second.txt"
            self.write_single(first)
            self.write_single(second)
            frame = wx.Frame(None)
            try:
                raman = RamanAnalysisPanel(frame)
                baseline = raman.substrate_page
                baseline.rb_auto.SetValue(False)
                baseline.rb_manual.SetValue(True)
                baseline.update_parameter_controls()
                baseline.add_paths([first])

                converting = raman.converting_page
                converting.rb_auto.SetValue(False)
                converting.rb_manual.SetValue(True)
                converting.update_parameter_controls()
                converting.add_paths([second])
                converting.on_load_to_baseline(None)

                self.assertEqual(
                    [item.source_path.name for item in baseline.items],
                    ["first.txt", "second.txt"],
                )
                self.assertFalse(baseline.rb_auto.GetValue())
            finally:
                frame.Destroy()


if __name__ == "__main__":
    unittest.main()
