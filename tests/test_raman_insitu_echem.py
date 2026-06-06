import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    import wx
    from ca_app.gui.panels.raman_panel import RamanAnalysisPanel, RamanInsituEchemPanel
except ImportError:
    wx = None
    RamanAnalysisPanel = None
    RamanInsituEchemPanel = None

from ca_app.core.raman_insitu_echem import (
    PeakWindow,
    RamanInsituError,
    analyze_insitu_sequence,
    build_intensity_ratios,
    extract_peak_in_window,
    filter_raman_range,
    load_raman_sequence,
    peak_summary_rows,
    raman_dataset_to_sequence,
    ratio_rows,
    save_peak_summary_csv,
    save_ratio_csv,
    selected_sequence_values,
)
from ca_app.core.raman_electrical import (
    DRAIN_CURRENT_COL,
    DRAIN_TIME_COL,
    DRAIN_VOLTAGE_COL,
    GATE_CURRENT_COL,
    GATE_TIME_COL,
    GATE_VOLTAGE_COL,
)


class RamanInsituEchemCoreTests(unittest.TestCase):
    def test_load_raman_sequence_maps_sequence_codes_and_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sequence.txt"
            self.write_sequence_file(path)

            data = load_raman_sequence(path, time_offset_s=5.0, time_per_sequence_s=2.0)

            self.assertEqual(data.name, "sequence.txt")
            self.assertEqual(data.sequence_values.tolist(), [1, 2, 3])
            self.assertEqual(len(data.intensity), 15)
            self.assertAlmostEqual(float(data.time_s[data.sequence_index == 1][0]), 7.0)
            self.assertAlmostEqual(float(data.time_s[data.sequence_index == 3][0]), 11.0)

    def test_extract_peak_in_window_returns_one_peak_per_sequence(self):
        data = self.synthetic_data()

        peak = extract_peak_in_window(data, PeakWindow(1423, 3))

        self.assertEqual(peak.sequence_index.tolist(), [1, 2, 3])
        np.testing.assert_allclose(peak.peak_position_cm1, [1423, 1423, 1423])
        np.testing.assert_allclose(peak.peak_intensity, [100, 120, 140])

    def test_analyze_insitu_sequence_builds_peak_summary_and_ratios(self):
        data = self.synthetic_data()

        result = analyze_insitu_sequence(data, [PeakWindow(1371, 3), PeakWindow(1423, 3)], 1423)

        self.assertEqual(result.normalized_peak_cm1, 1423)
        self.assertEqual(len(result.peak_series), 2)
        rows = peak_summary_rows(result)
        self.assertIn("peak1371_position_cm1", rows[0])
        self.assertIn("peak1423_intensity", rows[0])
        ratio_data = ratio_rows(result)
        self.assertIn("ratio_1371_to_1423", ratio_data[0])
        self.assertIn("ratio_1423_to_1423", ratio_data[0])
        np.testing.assert_allclose([row["ratio_1423_to_1423"] for row in ratio_data], [1, 1, 1])

    def test_build_intensity_ratios_rejects_empty_series(self):
        with self.assertRaises(RamanInsituError):
            build_intensity_ratios([], 1423)

    def test_invalid_peak_window_is_rejected(self):
        data = self.synthetic_data()

        with self.assertRaises(RamanInsituError):
            analyze_insitu_sequence(data, [PeakWindow(1423, 0)], 1423)

    def test_missing_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.txt"
            path.write_text("#Time\t#Wave\n0\t1423\n", encoding="utf-8")

            with self.assertRaises(RamanInsituError):
                load_raman_sequence(path)

    def test_load_raman_sequence_accepts_sequence_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "selected_sequence.txt"
            path.write_text(
                "\n".join(
                    [
                        "#Sequence\t#Wave\t#Intensity",
                        "45\t1420\t10",
                        "45\t1423\t100",
                        "60\t1420\t12",
                        "60\t1423\t120",
                    ]
                ),
                encoding="utf-8",
            )

            data = load_raman_sequence(path)

            self.assertEqual(data.sequence_source, "sequence")
            self.assertEqual(data.sequence_values.tolist(), [45, 60])
            np.testing.assert_allclose(data.time_s[data.sequence_index == 60], [60, 60])

    def test_raman_dataset_to_sequence_uses_selected_spectra(self):
        from ca_app.core.raman_mapping import read_wire_txt

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.txt"
            path.write_text(
                "\n".join(
                    [
                        "#X\t#Y\t#Wave\t#Intensity",
                        "1\t2\t1420\t10",
                        "1\t2\t1423\t100",
                        "3\t4\t1420\t30",
                        "3\t4\t1423\t300",
                    ]
                ),
                encoding="utf-8",
            )
            dataset = read_wire_txt(path)

            data = raman_dataset_to_sequence(dataset, selected_indices=[1], name="selected")

            self.assertEqual(data.name, "selected")
            self.assertEqual(data.sequence_source, "sequence")
            self.assertEqual(data.sequence_values.tolist(), [2])
            np.testing.assert_allclose(data.time_s[data.sequence_index == 2], [2, 2])
            np.testing.assert_allclose(data.intensity, [30, 300])

    def test_selected_sequence_values_uses_every_n(self):
        data = self.synthetic_data()

        self.assertEqual(selected_sequence_values(data, 2).tolist(), [1, 3])

    def test_filter_raman_range_keeps_inclusive_bounds(self):
        data = self.synthetic_data()

        filtered = filter_raman_range(data, 1371, 1423)

        self.assertGreater(len(filtered.raman_cm1), 0)
        self.assertGreaterEqual(float(np.min(filtered.raman_cm1)), 1371)
        self.assertLessEqual(float(np.max(filtered.raman_cm1)), 1423)
        self.assertIn(1371, filtered.raman_cm1.tolist())
        self.assertIn(1423, filtered.raman_cm1.tolist())

    def test_filter_raman_range_rejects_invalid_or_empty_range(self):
        data = self.synthetic_data()

        with self.assertRaises(RamanInsituError):
            filter_raman_range(data, 1700, 1300)
        with self.assertRaises(RamanInsituError):
            filter_raman_range(data, 1500, 1510)

    def test_save_csv_outputs_peak_and_ratio_data(self):
        data = self.synthetic_data()
        result = analyze_insitu_sequence(data, [PeakWindow(1371, 3), PeakWindow(1423, 3)], 1423)
        with tempfile.TemporaryDirectory() as tmp:
            peak_path = save_peak_summary_csv(result, Path(tmp) / "peaks.csv")
            ratio_path = save_ratio_csv(result, Path(tmp) / "ratios.csv")

            self.assertTrue(peak_path.exists())
            self.assertTrue(ratio_path.exists())
            self.assertIn("peak1371_position_cm1", peak_path.read_text(encoding="utf-8-sig"))
            self.assertIn("ratio_1371_to_1423", ratio_path.read_text(encoding="utf-8-sig"))

    @staticmethod
    def synthetic_data():
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sequence.txt"
            RamanInsituEchemCoreTests.write_sequence_file(path)
            return load_raman_sequence(path, time_offset_s=5.0, time_per_sequence_s=2.0)

    @staticmethod
    def write_sequence_file(path):
        rows = [["#Time", "#Wave", "#Intensity"]]
        for seq_code, scale in [(0, 1.0), (2, 1.2), (4, 1.4)]:
            for wave in [1368, 1371, 1374, 1420, 1423]:
                base = 10
                if wave == 1371:
                    intensity = 50 * scale
                elif wave == 1423:
                    intensity = 100 * scale
                else:
                    intensity = base * scale
                rows.append([str(seq_code), str(wave), f"{intensity:.6g}"])
        path.write_text("\n".join("\t".join(row) for row in rows), encoding="utf-8")



@unittest.skipIf(wx is None, "wxPython is not available")
class RamanInsituEchemGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def test_draw_insitu_previews_handles_loaded_result(self):
        frame = wx.Frame(None)
        try:
            panel = RamanInsituEchemPanel(frame)
            data = RamanInsituEchemCoreTests.synthetic_data()
            panel.data = data
            panel.result = analyze_insitu_sequence(data, [PeakWindow(1371, 3), PeakWindow(1423, 3)], 1423)

            panel.draw_insitu_previews()

            self.assertGreaterEqual(len(panel.figure_windows.axes), 1)
            self.assertEqual(len(panel.figure_analysis.axes), 4)
        finally:
            frame.Destroy()

    def test_raman_notebook_has_mapping_insitu_and_electrical_tabs(self):
        frame = wx.Frame(None)
        try:
            panel = RamanAnalysisPanel(frame)

            self.assertEqual(
                [panel.notebook.GetPageText(index) for index in range(panel.notebook.GetPageCount())],
                ["Baseline", "Mapping", "Insitu EChem", "Electrical"],
            )
            self.assertEqual(panel.substrate_page.btn_load_raw.GetLabel(), "Load txt")
            self.assertEqual(panel.insitu_page.btn_load_insitu.GetLabel(), "Load wdf/txt")
        finally:
            frame.Destroy()

    def test_mapping_preview_tabs_and_every_n_legend_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.txt"
            rows = ["#X\t#Y\t#Wave\t#Intensity"]
            for seq, (x, y, scale) in enumerate([(1, 2, 1), (3, 4, 2), (5, 6, 3), (7, 8, 4)], start=1):
                for wave in [100, 99, 98]:
                    rows.append(f"{x}\t{y}\t{wave}\t{scale * wave}")
            path.write_text("\n".join(rows), encoding="utf-8")
            frame = wx.Frame(None)
            try:
                panel = RamanAnalysisPanel(frame)
                mapping = panel.mapping_page
                mapping.load_dataset(path)

                self.assertEqual(
                    [mapping.mapping_notebook.GetPageText(index) for index in range(mapping.mapping_notebook.GetPageCount())],
                    ["Avg./Norm.", "Raw data", "Location", "Selected"],
                )
                self.assertEqual(mapping.grid_raw_preview.GetColLabelValue(0), "Wavenumber")
                self.assertEqual(mapping.grid_avg_preview.GetColLabelValue(1), "Averaged Intensity")
                self.assertFalse(mapping.cb_raw_legend.IsEnabled())
                self.assertEqual(len(mapping.figure_raw.axes[0].lines), 4)

                mapping.tc_preview_every_n.SetValue("2")
                mapping.cb_raw_legend.SetValue(True)
                mapping.update_previews()

                self.assertTrue(mapping.cb_raw_legend.IsEnabled())
                self.assertEqual(len(mapping.figure_raw.axes[0].lines), 2)
                self.assertIsNotNone(mapping.figure_raw.axes[0].get_legend())
            finally:
                frame.Destroy()

    def test_electrical_load_populates_previews_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "electrical.csv"
            self.write_electrical_csv(path)
            frame = wx.Frame(None)
            try:
                panel = RamanAnalysisPanel(frame)
                electrical = panel.electrical_page

                electrical.load_data(path)

                self.assertEqual(
                    [
                        electrical.electrical_notebook.GetPageText(index)
                        for index in range(electrical.electrical_notebook.GetPageCount())
                    ],
                    ["Raw data", "V_Gate/V_Drain"],
                )
                self.assertEqual(electrical.electrical_notebook.GetSelection(), 1)
                self.assertEqual(len(electrical.figure_electrical_raw.axes), 4)
                self.assertEqual(
                    [ax.get_title() for ax in electrical.figure_electrical_raw.axes],
                    ["Gate V", "Drain V", "Gate I", "Drain I"],
                )
                self.assertTrue(
                    all(
                        electrical.RAW_TRACE_LINEWIDTH_MIN <= line.get_linewidth() <= electrical.RAW_TRACE_LINEWIDTH_MAX
                        for ax in electrical.figure_electrical_raw.axes
                        for line in ax.lines
                    )
                )
                self.assertGreaterEqual(len(electrical.figure_vgvd.axes), 2)
                self.assertEqual(electrical.grid_summary.GetCellValue(0, 0), "n_rows")
                self.assertEqual(electrical.grid_summary.GetCellValue(2, 0), "V_Gate")
                self.assertEqual(electrical.grid_summary.GetCellValue(3, 0), "V_Drain")
                self.assertEqual(electrical.tc_raw_preview_s.GetValue(), "1")
                self.assertEqual(electrical.lbl_raw_preview_range.GetLabel(), "first 1.0 s")
            finally:
                frame.Destroy()

    def test_electrical_raw_linewidth_decreases_for_longer_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "electrical.csv"
            self.write_electrical_csv(path, row_count=2000, dt_s=0.1)
            frame = wx.Frame(None)
            try:
                panel = RamanAnalysisPanel(frame)
                electrical = panel.electrical_page
                electrical.load_data(path)

                electrical.tc_raw_preview_s.SetValue("1.0")
                electrical.update_previews()
                short_width = electrical.figure_electrical_raw.axes[0].lines[0].get_linewidth()

                electrical.tc_raw_preview_s.SetValue("100.0")
                electrical.update_previews()
                long_width = electrical.figure_electrical_raw.axes[0].lines[0].get_linewidth()

                self.assertGreater(short_width, long_width)
                self.assertLessEqual(short_width, electrical.RAW_TRACE_LINEWIDTH_MAX)
                self.assertGreaterEqual(long_width, electrical.RAW_TRACE_LINEWIDTH_MIN)
                self.assertEqual(electrical.figure_vgvd.axes[0].lines[0].get_linewidth(), 1.5)
            finally:
                frame.Destroy()

    def test_electrical_slider_display_uses_one_decimal_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "electrical.csv"
            self.write_electrical_csv(path, row_count=20, dt_s=0.1)
            frame = wx.Frame(None)
            try:
                panel = RamanAnalysisPanel(frame)
                electrical = panel.electrical_page
                electrical.load_data(path)

                for slider, ctrl, label in [
                    (electrical.slider_raw_preview, electrical.tc_raw_preview_s, electrical.lbl_raw_preview_range),
                    (electrical.slider_vg_preview, electrical.tc_vg_preview_s, electrical.lbl_vg_preview_range),
                    (electrical.slider_vd_preview, electrical.tc_vd_preview_s, electrical.lbl_vd_preview_range),
                ]:
                    slider.SetValue(70)
                    event = wx.CommandEvent(wx.EVT_SLIDER.typeId)
                    event.SetEventObject(slider)
                    electrical.on_preview_slider(event)

                    self.assertRegex(ctrl.GetValue(), r"^\d+\.\d$")
                    self.assertIn(ctrl.GetValue(), label.GetLabel())
            finally:
                frame.Destroy()

    def test_electrical_raw_preview_seconds_filters_all_raw_axes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "electrical.csv"
            self.write_electrical_csv(path, row_count=20, dt_s=0.1)
            frame = wx.Frame(None)
            try:
                panel = RamanAnalysisPanel(frame)
                electrical = panel.electrical_page
                electrical.load_data(path)

                electrical.tc_raw_preview_s.SetValue("0.5")
                electrical.update_previews()

                for ax in electrical.figure_electrical_raw.axes:
                    self.assertEqual(len(ax.lines), 1)
                    xdata = ax.lines[0].get_xdata()
                    self.assertEqual(len(xdata), 6)
                    self.assertLessEqual(float(max(xdata)), 0.5)
            finally:
                frame.Destroy()

    def test_electrical_app_restore_preserves_preview_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "electrical.csv"
            self.write_electrical_csv(path)
            frame = wx.Frame(None)
            try:
                panel = RamanAnalysisPanel(frame)

                panel.electrical_page.apply_app_parameters(
                    {
                        "raw_path": str(path),
                        "raw_preview_s": "0.75",
                        "vg_preview_s": "0.25",
                        "vd_preview_s": "0.5",
                    }
                )

                self.assertEqual(panel.electrical_page.tc_raw_preview_s.GetValue(), "0.75")
                self.assertEqual(panel.electrical_page.tc_vg_preview_s.GetValue(), "0.25")
                self.assertEqual(panel.electrical_page.tc_vd_preview_s.GetValue(), "0.5")
                self.assertIsNotNone(panel.electrical_page.data)
            finally:
                frame.Destroy()

    @staticmethod
    def write_electrical_csv(path, row_count=10, dt_s=0.01):
        headers = [
            GATE_TIME_COL,
            GATE_VOLTAGE_COL,
            GATE_CURRENT_COL,
            DRAIN_TIME_COL,
            DRAIN_VOLTAGE_COL,
            DRAIN_CURRENT_COL,
        ]
        rows = []
        for index in range(row_count):
            time_s = index * dt_s
            rows.append([time_s, 1.0 if index < 5 else 2.0, 1e-9, time_s, 0.01, 2e-9])
        path.write_text(
            "\n".join([",".join(headers)] + [",".join(f"{value:.12g}" for value in row) for row in rows]),
            encoding="utf-8",
        )

    def test_mapping_selected_preview_uses_short_numeric_legend(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.txt"
            path.write_text(
                "\n".join(
                    [
                        "#X\t#Y\t#Wave\t#Intensity",
                        "1\t2\t100\t10",
                        "1\t2\t99\t20",
                        "3\t4\t100\t30",
                        "3\t4\t99\t40",
                    ]
                ),
                encoding="utf-8",
            )
            frame = wx.Frame(None)
            try:
                panel = RamanAnalysisPanel(frame)
                mapping = panel.mapping_page
                mapping.load_dataset(path)
                mapping.tc_selected.SetValue("1,2")
                mapping.update_previews()

                axes = mapping.figure_selected.axes
                self.assertEqual(len(axes), 1)
                legend = axes[0].get_legend()
                self.assertIsNotNone(legend)
                self.assertEqual([text.get_text() for text in legend.get_texts()], ["1", "2"])
            finally:
                frame.Destroy()

    def test_mapping_app_restore_preserves_saved_range_and_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.txt"
            path.write_text(
                "\n".join(
                    [
                        "#X\t#Y\t#Wave\t#Intensity",
                        "1\t2\t100\t10",
                        "1\t2\t99\t20",
                        "3\t4\t100\t30",
                        "3\t4\t99\t40",
                    ]
                ),
                encoding="utf-8",
            )
            frame = wx.Frame(None)
            try:
                panel = RamanAnalysisPanel(frame)

                panel.mapping_page.apply_app_parameters(
                    {
                        "raw_path": str(path),
                        "raman_range_min_cm1": "99",
                        "raman_range_max_cm1": "100",
                        "selected_columns": "2",
                        "preview_every_n": "2",
                        "raw_legend": True,
                    }
                )

                self.assertEqual(panel.mapping_page.tc_range_min.GetValue(), "99")
                self.assertEqual(panel.mapping_page.tc_range_max.GetValue(), "100")
                self.assertEqual(panel.mapping_page.tc_selected.GetValue(), "2")
                self.assertEqual(panel.mapping_page.tc_preview_every_n.GetValue(), "2")
                self.assertTrue(panel.mapping_page.cb_raw_legend.GetValue())
            finally:
                frame.Destroy()


    def test_reload_data_uses_typed_raman_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sequence.txt"
            RamanInsituEchemCoreTests.write_sequence_file(path)
            frame = wx.Frame(None)
            try:
                panel = RamanInsituEchemPanel(frame)
                panel.raw_path = str(path)
                panel.tc_raman_range_min.SetValue("1371")
                panel.tc_raman_range_max.SetValue("1423")
                for index, (_, center_ctrl, tolerance_ctrl) in enumerate(panel.window_rows):
                    if index == 0:
                        center_ctrl.SetValue("1371")
                        tolerance_ctrl.SetValue("3")
                    elif index == 1:
                        center_ctrl.SetValue("1423")
                        tolerance_ctrl.SetValue("3")
                    else:
                        center_ctrl.SetValue("")
                        tolerance_ctrl.SetValue("")
                panel.update_normalized_peak_choices()
                panel.choice_normalized_peak.SetStringSelection("1423")

                panel.reload_data_and_update()

                self.assertIsNotNone(panel.result)
                self.assertGreaterEqual(float(np.min(panel.result.data.raman_cm1)), 1371)
                self.assertLessEqual(float(np.max(panel.result.data.raman_cm1)), 1423)
            finally:
                frame.Destroy()

    def test_sequence_source_disables_time_x_axis(self):
        frame = wx.Frame(None)
        try:
            panel = RamanInsituEchemPanel(frame)
            data = RamanInsituEchemCoreTests.synthetic_data()
            data.sequence_source = "sequence"

            panel.load_sequence_data(data, source_label="Mapping: selected")

            self.assertTrue(panel.rb_sequence.GetValue())
            self.assertFalse(panel.rb_time.IsEnabled())
        finally:
            frame.Destroy()


    def test_insitu_parameters_round_trip(self):
        frame = wx.Frame(None)
        target_frame = wx.Frame(None)
        try:
            panel = RamanInsituEchemPanel(frame)
            panel.rb_sequence.SetValue(False)
            panel.rb_time.SetValue(True)
            panel.tc_time_offset.SetValue("12.5")
            panel.tc_time_per_sequence.SetValue("3.25")
            panel.tc_raman_range_min.SetValue("1310")
            panel.tc_raman_range_max.SetValue("1660")
            panel.tc_window_every_n.SetValue("7")
            panel.tc_result_every_n.SetValue("9")
            panel.clear_peak_window_rows()
            panel.add_peak_window_row("1371", "4")
            panel.add_peak_window_row("1606", "8")
            panel.update_normalized_peak_choices()
            panel.choice_normalized_peak.SetStringSelection("1606")

            params = panel.collect_parameters()
            target = RamanInsituEchemPanel(target_frame)
            target.apply_parameters(params)

            self.assertEqual(params["x_mode"], "time")
            self.assertEqual(params["time_offset_s"], "12.5")
            self.assertEqual(params["time_per_sequence_s"], "3.25")
            self.assertEqual(params["raman_range_min_cm1"], "1310")
            self.assertEqual(params["raman_range_max_cm1"], "1660")
            self.assertEqual(params["window_preview_every_n"], "7")
            self.assertEqual(params["result_spectra_every_n"], "9")
            self.assertEqual(params["normalized_peak_cm1"], "1606")
            self.assertEqual(len(params["peak_windows"]), 2)
            self.assertTrue(target.rb_time.GetValue())
            self.assertEqual(target.tc_time_offset.GetValue(), "12.5")
            self.assertEqual(target.tc_time_per_sequence.GetValue(), "3.25")
            self.assertEqual(target.tc_raman_range_min.GetValue(), "1310")
            self.assertEqual(target.tc_raman_range_max.GetValue(), "1660")
            self.assertEqual(target.tc_window_every_n.GetValue(), "7")
            self.assertEqual(target.tc_result_every_n.GetValue(), "9")
            self.assertEqual(len(target.window_rows), 2)
            self.assertEqual(target.choice_normalized_peak.GetStringSelection(), "1606")
        finally:
            frame.Destroy()
            target_frame.Destroy()

    def test_apply_parameters_rejects_missing_required_fields(self):
        frame = wx.Frame(None)
        try:
            panel = RamanInsituEchemPanel(frame)
            with self.assertRaises(RamanInsituError):
                panel.apply_parameters({"x_mode": "sequence"})
        finally:
            frame.Destroy()

if __name__ == "__main__":
    unittest.main()





