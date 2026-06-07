import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    import wx
    from ca_app.gui.panels.afm_controller_panel import AfmControllerPanel, SOURCE_INTENSITY
    from ca_app.gui.panels.afm_kpfm_panel import AfmKpfmPanel
    from ca_app.gui.panels.tpc_panel import TpcLaserDiodePanel
except ImportError:
    wx = None
    AfmControllerPanel = None
    AfmKpfmPanel = None
    TpcLaserDiodePanel = None
    SOURCE_INTENSITY = "Intensity"

from ca_app.constants import DEFAULT_BAUDRATE, DEFAULT_COM_PORT, SERIAL_TIMEOUT_S
from ca_app.core.intensity_profile_tools import CalibrationStats
from ca_app.hardware import tpc_keithley


class FakeKeithleySerial:
    def __init__(self, responses):
        self.responses = list(responses)
        self.writes = []
        self.reset_count = 0
        self.flush_count = 0
        self.is_open = True
        self.close_count = 0

    def write(self, data):
        self.writes.append(data)

    def reset_input_buffer(self):
        self.reset_count += 1

    def flush(self):
        self.flush_count += 1

    def read_until(self, terminator, size=None):
        if not self.responses:
            return b""
        return self.responses.pop(0)

    def close(self):
        self.close_count += 1
        self.is_open = False


class FakeCalibrationModel:
    def __init__(self, scale):
        self.scale = scale

    def current_for_intensity(self, values):
        return np.asarray(values, dtype=float) * self.scale


class ControllerComPortDefaultsTests(unittest.TestCase):
    def test_shared_serial_defaults_are_com3_38400_and_5s_timeout(self):
        self.assertEqual(DEFAULT_COM_PORT, "COM3")
        self.assertEqual(DEFAULT_BAUDRATE, 38400)
        self.assertEqual(SERIAL_TIMEOUT_S, 5.0)

    def test_tpc_open_serial_defaults_and_accepts_baudrate_override(self):
        with patch("ca_app.hardware.tpc_keithley.serial.Serial") as serial_cls:
            tpc_keithley.open_tpc_serial()
            kwargs = serial_cls.call_args.kwargs
            self.assertEqual(kwargs["port"], "COM3")
            self.assertEqual(kwargs["baudrate"], 38400)
            self.assertEqual(kwargs["timeout"], 5.0)
            self.assertFalse(kwargs["xonxoff"])
            self.assertFalse(kwargs["rtscts"])
            self.assertFalse(kwargs["dsrdtr"])

            tpc_keithley.open_tpc_serial("COM7", 57600)
            kwargs = serial_cls.call_args.kwargs
            self.assertEqual(kwargs["port"], "COM7")
            self.assertEqual(kwargs["baudrate"], 57600)

    def test_tpc_output_on_and_read_accepts_cr_and_lf_terminated_replies(self):
        with patch("ca_app.hardware.tpc_keithley.time.sleep"):
            ser = FakeKeithleySerial([b"1.23,0.004\r"])
            self.assertEqual(tpc_keithley.output_on_and_read(ser), (1.23, 0.004))
            self.assertIn(b":OUTP ON\r", ser.writes)
            self.assertIn(b":READ?\r", ser.writes)
            self.assertEqual(ser.reset_count, 1)
            self.assertEqual(ser.flush_count, 1)

            ser = FakeKeithleySerial([b"", b"2.0,0.005\n"])
            self.assertEqual(tpc_keithley.output_on_and_read(ser), (2.0, 0.005))


@unittest.skipIf(wx is None, "wxPython is not available")
class ControllerComPortGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def test_afm_controller_top_tabs_and_scrolled_sequence_panels(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)

            self.assertEqual(panel.top_settings_notebook.GetPageCount(), 2)
            self.assertEqual(panel.top_settings_notebook.GetPageText(0), "Global settings")
            self.assertEqual(panel.top_settings_notebook.GetPageText(1), "Quick Test")
            self.assertIs(panel.top_settings_notebook.GetPage(0), panel.global_settings_panel)
            self.assertIs(panel.top_settings_notebook.GetPage(1), panel.source_quick_panel)
            self.assertEqual(panel.top_settings_notebook.GetMinSize().GetHeight(), -1)
            self.assertLessEqual(panel.top_settings_notebook.GetBestSize().GetHeight(), 170)

            global_sizer = panel.global_settings_panel.GetSizer().GetItem(0).GetSizer()
            global_grid = global_sizer.GetItem(0).GetSizer()
            source_mode_row = global_sizer.GetItem(1).GetSizer()
            self.assertIsInstance(global_sizer, wx.BoxSizer)
            self.assertNotIsInstance(global_sizer, wx.StaticBoxSizer)
            self.assertIs(global_grid, panel.global_settings_grid)
            self.assertIs(source_mode_row, panel.source_mode_row)
            self.assertEqual(global_grid.GetRows(), 3)
            self.assertEqual(global_grid.GetCols(), 6)
            self.assertIs(global_grid.GetItem(13).GetWindow(), panel.tc_measured_voltage)
            self.assertIs(source_mode_row.GetItem(1).GetWindow(), panel.cb_current_mode)
            self.assertIs(source_mode_row.GetItem(2).GetWindow(), panel.cb_intensity_mode)
            self.assertFalse(hasattr(panel, "tc_step_status"))
            input_height = panel.tc_quick_value.GetBestSize().GetHeight()
            button_size = panel.btn_quick_toggle.GetMinSize()
            self.assertGreaterEqual(button_size.GetWidth(), 90)
            self.assertLessEqual(abs(button_size.GetHeight() - input_height), 2)
            self.assertIsInstance(panel.quick_test_row, wx.BoxSizer)
            self.assertIs(panel.quick_test_row.GetItem(0).GetWindow(), panel.st_quick_value_label)
            self.assertIs(panel.quick_test_row.GetItem(1).GetWindow(), panel.tc_quick_value)
            self.assertEqual(panel.quick_test_row.GetItem(1).GetProportion(), 1)
            self.assertIs(panel.quick_test_row.GetItem(3).GetWindow(), panel.btn_quick_toggle)
            quick_sizer = panel.source_quick_panel.GetSizer().GetItem(0).GetSizer()
            self.assertIsInstance(quick_sizer, wx.BoxSizer)
            self.assertNotIsInstance(quick_sizer, wx.StaticBoxSizer)
            self.assertLessEqual(panel.source_quick_panel.GetSizer().CalcMin().GetHeight(), 80)
            for preview_panel in [
                panel.source_preview_panel,
                panel.function_preview_panel,
                panel.calibration_preview_panel,
                panel.live_voltage_panel,
            ]:
                self.assertIsInstance(preview_panel.GetSizer(), wx.BoxSizer)
                self.assertNotIsInstance(preview_panel.GetSizer(), wx.StaticBoxSizer)
            self.assertEqual(panel.btn_save_keithley.GetLabel(), "Save Keithley CSV")
            self.assertFalse(panel.btn_save_keithley.IsEnabled())

            self.assertIsInstance(panel.recurrent_panel, wx.ScrolledWindow)
            self.assertIsInstance(panel.step_panel, wx.ScrolledWindow)
            self.assertIsInstance(panel.recurrent_panel.GetSizer(), wx.BoxSizer)
            self.assertNotIsInstance(panel.recurrent_panel.GetSizer(), wx.StaticBoxSizer)
            self.assertIsInstance(panel.step_panel.GetSizer(), wx.BoxSizer)
            self.assertNotIsInstance(panel.step_panel.GetSizer(), wx.StaticBoxSizer)
        finally:
            frame.Destroy()

    def test_afm_kpfm_outer_notebook_matches_workspace_bounds(self):
        frame = wx.Frame(None)
        try:
            panel = AfmKpfmPanel(frame)

            self.assertEqual(panel.notebook.GetPageText(0), "Controller")
            self.assertEqual(panel.notebook.GetPageText(1), "Analysis")
            notebook_item = panel.GetSizer().GetItem(0)
            self.assertIs(notebook_item.GetWindow(), panel.notebook)
            self.assertTrue(notebook_item.GetFlag() & wx.EXPAND)
            self.assertEqual(notebook_item.GetBorder(), 0)
        finally:
            frame.Destroy()

    def test_afm_calibration_stats_are_compact_static_labels(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            self.assertFalse(hasattr(panel, "calibration_stats_text"))
            self.assertEqual(len(panel.calibration_stats_labels), 6)
            self.assertTrue(all(isinstance(label, wx.StaticText) for label in panel.calibration_stats_labels))

            stats = CalibrationStats(
                r2=0.999579,
                rmse_mw=0.029442,
                mae_mw=0.0183699,
                max_error_mw=0.109803,
                current_min_ma=67.0,
                current_max_ma=94.0,
                intensity_min_mw=0.020575,
                intensity_max_mw=4.995,
            )
            panel.update_calibration_stats_labels(stats)

            self.assertEqual([label.GetLabel() for label in panel.calibration_stats_labels], [
                "R² = 0.999579",
                "RMSE = 0.029442 mW",
                "MAE = 0.0183699 mW",
                "Max error = 0.109803 mW",
                "Current range = 67 to 94 mA",
                "Intensity range = 0.020575 to 4.995 mW",
            ])
            self.assertEqual([label.GetLabel() for label in panel.function_range_labels], [
                "Current range = 67 to 94 mA",
                "Intensity range = 0.020575 to 4.995 mW",
            ])
        finally:
            frame.Destroy()

    def test_afm_intensity_function_section_is_compact(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            function_height = panel.function_controls_panel.GetSizer().CalcMin().GetHeight()
            notebook_height = panel.intensity_function_notebook.GetBestSize().GetHeight()
            intensity_function_panel = panel.intensity_function_notebook.GetParent()

            self.assertIsInstance(intensity_function_panel.GetSizer(), wx.BoxSizer)
            self.assertNotIsInstance(intensity_function_panel.GetSizer(), wx.StaticBoxSizer)
            self.assertEqual(panel.intensity_function_notebook.GetPageText(0), "Calibration")
            self.assertEqual(panel.intensity_function_notebook.GetPageText(1), "Function control")
            self.assertEqual(panel.lbl_function_expr.GetLabel(), "f(x) =")
            self.assertEqual(panel.btn_parameterise_function.GetLabel(), "Parameterise")
            self.assertEqual(panel.btn_parameterise_function.GetMinSize().Get(), panel.btn_fit_function.GetMinSize().Get())
            self.assertEqual([label.GetLabel() for label in panel.function_range_labels], [
                "Current range = -- to -- mA",
                "Intensity range = -- to -- mW",
            ])
            self.assertLessEqual(function_height, 120)
            self.assertLessEqual(notebook_height, 160)
        finally:
            frame.Destroy()

    def test_afm_function_parameterise_replaces_numeric_literals(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)

            expr, names = panel.parameterise_function_expression("x * 0.48 + 0.029")
            self.assertEqual(expr, "x * a + b")
            self.assertEqual(names, ["a", "b"])

            expr, names = panel.parameterise_function_expression("x * 0.48 + 0.48")
            self.assertEqual(expr, "x * a + b")
            self.assertEqual(names, ["a", "b"])

            panel.tc_function_expr.SetValue("x*a+b")
            with patch.object(panel, "show_warning") as warning:
                panel.on_parameterise_function(None)
            self.assertEqual(panel.tc_function_expr.GetValue(), "x*a+b")
            warning.assert_called_once()
            self.assertIn("No numeric constants", warning.call_args.args[0])
        finally:
            frame.Destroy()

    def test_afm_com_port_and_baudrate_are_editable_and_saved(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            self.assertEqual(panel.tc_com_port.GetValue(), "COM3")
            self.assertEqual(panel.choice_baudrate.GetStringSelection(), "38400")

            panel.tc_com_port.SetValue(" COM8 ")
            panel.choice_baudrate.SetStringSelection("9600")
            settings = panel.read_global_settings()
            params = panel.collect_parameters()

            self.assertEqual(settings["com_port"], "COM8")
            self.assertEqual(settings["baudrate"], 9600)
            self.assertEqual(params["com_port"], "COM8")
            self.assertEqual(params["baudrate"], 9600)

            panel.apply_parameters({"com_port": "COM9", "baudrate": 57600})
            self.assertEqual(panel.tc_com_port.GetValue(), "COM9")
            self.assertEqual(panel.choice_baudrate.GetStringSelection(), "57600")
        finally:
            frame.Destroy()

    def test_afm_rejects_empty_com_port(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            panel.tc_com_port.SetValue("  ")

            with self.assertRaises(ValueError):
                panel.read_global_settings()
        finally:
            frame.Destroy()

    def test_afm_save_keithley_button_requires_finished_run_data(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            self.assertFalse(panel.btn_save_keithley.IsEnabled())

            panel.data_rows = [{"Time_s": "0", "Source_Current_mA": "0"}]
            panel.running = False
            panel.quick_running = False
            panel.cb_quick_test.SetValue(False)
            panel.update_save_keithley_controls()
            self.assertTrue(panel.btn_save_keithley.IsEnabled())

            panel.running = True
            panel.update_save_keithley_controls()
            self.assertFalse(panel.btn_save_keithley.IsEnabled())

            panel.running = False
            panel.cb_quick_test.SetValue(True)
            panel.update_save_keithley_controls()
            self.assertFalse(panel.btn_save_keithley.IsEnabled())
        finally:
            frame.Destroy()

    def test_afm_save_run_data_csv_writes_only_when_called(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            panel.data_rows = [
                {
                    "Time_s": "0",
                    "Source_Current_mA": "0",
                    "Measured_Voltage_V": "",
                    "Measured_Current_mA": "",
                    "State": "OFF",
                }
            ]
            with tempfile.TemporaryDirectory() as tmpdir:
                path = os.path.join(tmpdir, "keithley_run_data_test.csv")
                panel.save_run_data_csv(path)
                with open(path, "r", encoding="utf-8-sig") as f:
                    text = f.read()

            self.assertIn("Time_s,Source_Current_mA,Measured_Voltage_V,Measured_Current_mA,State", text)
            self.assertIn("0,0,,,OFF", text)
        finally:
            frame.Destroy()

    def test_afm_sequence_worker_does_not_auto_save_run_data(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            settings = {"com_port": "COM3", "baudrate": 38400, "compliance_v": 5.0}
            sequence = [{"label": "OFF test", "state": "OFF", "duration_s": 0.0}]
            ser = FakeKeithleySerial([])

            def fail_save(*_args, **_kwargs):
                raise AssertionError("Run data must only save after the user clicks Save Keithley CSV")

            panel.save_run_data_csv = fail_save
            run_snapshot = {
                "settings": settings,
                "sequence": sequence,
                "lock_message": "Run locked: source mode = Current, calibration conversion not used",
            }
            with patch("ca_app.gui.panels.afm_controller_panel.serial.Serial", return_value=ser):
                panel.run_sequence_worker(run_snapshot)

            self.assertEqual(len(panel.data_rows), 1)
            self.assertEqual(ser.close_count, 1)
        finally:
            frame.Destroy()

    def test_afm_fixed_intensity_step_uses_frozen_calibration_model(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            settings = {"internal_max_current_ma": 110.0}
            step = panel.make_on_step(
                "Frozen ON",
                2.0,
                1.0,
                SOURCE_INTENSITY,
                settings,
                run_context={"calibration_model": FakeCalibrationModel(scale=10.0)},
            )
            panel.calibration_model = FakeCalibrationModel(scale=99.0)

            self.assertEqual(step["source_current_mA"], 20.0)
            self.assertEqual(step["target_intensity_mW"], 2.0)
        finally:
            frame.Destroy()

    def test_afm_function_step_uses_frozen_current_profile_after_calibration_changes(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            settings = {"internal_max_current_ma": 110.0}
            step = {
                "state": "ON_FUNCTION",
                "duration_s": 1.0,
                "label": "Frozen f(x)",
                "source_mode": SOURCE_INTENSITY,
                "expr": "x",
                "x_min": 0.0,
                "x_max": 1.0,
                "x_profile": [0.0, 1.0],
                "target_profile": [1.0, 3.0],
                "current_profile_mA": [10.0, 30.0],
            }

            def fail_target_to_current(*_args, **_kwargs):
                raise AssertionError("Worker must not convert through the live panel calibration model")

            panel.calibration_model = FakeCalibrationModel(scale=99.0)
            panel.target_to_current_ma = fail_target_to_current
            x, target, current_ma = panel.function_current_and_target_at_x(step, settings, 0.5)

            self.assertEqual(x, 0.5)
            self.assertEqual(target, 2.0)
            self.assertEqual(current_ma, 20.0)
        finally:
            frame.Destroy()

    def test_afm_sequence_worker_does_not_convert_function_current_during_run(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            settings = {"com_port": "COM3", "baudrate": 38400, "compliance_v": 5.0, "internal_max_current_ma": 110.0}
            sequence = [
                {
                    "state": "ON_FUNCTION",
                    "duration_s": 0.0,
                    "label": "Frozen f(x)",
                    "source_mode": SOURCE_INTENSITY,
                    "expr": "x",
                    "x_min": 0.0,
                    "x_max": 1.0,
                    "x_profile": [0.0, 1.0],
                    "target_profile": [1.0, 3.0],
                    "current_profile_mA": [10.0, 30.0],
                }
            ]
            ser = FakeKeithleySerial([])

            def fail_target_to_current(*_args, **_kwargs):
                raise AssertionError("Worker must not convert through the live panel calibration model")

            panel.target_to_current_ma = fail_target_to_current
            run_snapshot = {
                "settings": settings,
                "sequence": sequence,
                "lock_message": "Run locked: calibration method = Frozen, fit range = 67 to 94 mA",
            }
            with patch("ca_app.gui.panels.afm_controller_panel.serial.Serial", return_value=ser), patch(
                "ca_app.gui.panels.afm_controller_panel.time.sleep"
            ):
                panel.run_sequence_worker(run_snapshot)

            self.assertIn(b":SOUR:CURR:LEV 0.01\r", ser.writes)
            self.assertIn(b":OUTP ON\r", ser.writes)
            self.assertEqual(ser.close_count, 1)
        finally:
            frame.Destroy()

    def test_afm_live_plot_tracks_source_current_at_voltage_read_pace(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            panel.record_live_read(1.2, 15.0)
            panel.record_live_read(1.4, 16.5)
            panel.update_live_voltage_plot()

            self.assertEqual(len(panel.live_voltage_times), 2)
            self.assertEqual(panel.live_voltage_values, [1.2, 1.4])
            self.assertEqual(panel.live_source_current_values, [15.0, 16.5])
            self.assertEqual(len(panel.live_source_current_times), 2)
            self.assertIsNotNone(panel.ax_live_current)
            self.assertEqual(panel.ax_live_current.get_ylabel(), "Source current / mA")
        finally:
            frame.Destroy()

    def test_afm_live_plot_starts_with_zero_voltage_and_current(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            panel.live_voltage_times.clear()
            panel.live_voltage_values.clear()
            panel.live_source_current_times.clear()
            panel.live_source_current_values.clear()

            panel.record_live_initial_zero()

            self.assertEqual(panel.live_voltage_times, [0.0])
            self.assertEqual(panel.live_voltage_values, [0.0])
            self.assertEqual(panel.live_source_current_times, [0.0])
            self.assertEqual(panel.live_source_current_values, [0.0])
        finally:
            frame.Destroy()

    def test_afm_off_step_records_zero_source_current_without_reading_keithley(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            step = {"label": "OFF test", "state": "OFF", "duration_s": 0.0}

            def fail_read_voltage_current(_ser):
                raise AssertionError("OFF steps must not query Keithley measurements")

            panel.read_voltage_current = fail_read_voltage_current
            panel.run_off_step_measurements(object(), step, 0.0)

            self.assertEqual(panel.live_voltage_values, [0.0])
            self.assertEqual(panel.live_source_current_values, [0.0])
            self.assertEqual(panel.data_rows[0]["Source_Current_mA"], "0")
            self.assertEqual(panel.data_rows[0]["Measured_Voltage_V"], "")
            self.assertEqual(panel.data_rows[0]["Measured_Current_mA"], "")
            self.assertEqual(panel.data_rows[0]["State"], "OFF")
        finally:
            frame.Destroy()

    def test_afm_off_live_updates_emit_zero_points_every_quarter_second(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            panel.live_voltage_times.clear()
            panel.live_voltage_values.clear()
            panel.live_source_current_times.clear()
            panel.live_source_current_values.clear()
            panel.live_start_time = 0.0
            now = [0.0]

            def fake_time():
                return now[0]

            def fake_sleep(duration_s):
                now[0] += duration_s

            with patch("ca_app.gui.panels.afm_controller_panel.time.time", fake_time), patch(
                "ca_app.gui.panels.afm_controller_panel.time.sleep",
                fake_sleep,
            ):
                panel.run_off_live_updates(0.5)

            self.assertEqual(panel.live_voltage_times, [0.0, 0.25, 0.5])
            self.assertEqual(panel.live_voltage_values, [0.0, 0.0, 0.0])
            self.assertEqual(panel.live_source_current_times, [0.0, 0.25, 0.5])
            self.assertEqual(panel.live_source_current_values, [0.0, 0.0, 0.0])
        finally:
            frame.Destroy()

    def test_afm_safety_output_off_sets_current_zero_before_output_off(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            ser = FakeKeithleySerial([])
            panel.send_safety_output_off(ser)

            self.assertEqual(ser.writes, [b":SOUR:CURR:LEV 0\r", b":OUTP OFF\r"])
            self.assertEqual(panel.live_source_current_values, [0.0])
        finally:
            frame.Destroy()

    def test_afm_read_voltage_current_accepts_cr_and_lf_terminated_replies(self):
        frame = wx.Frame(None)
        try:
            panel = AfmControllerPanel(frame)
            ser = FakeKeithleySerial([b"1.23,0.004\r"])
            self.assertEqual(panel.read_voltage_current(ser), (1.23, 0.004))
            self.assertEqual(ser.writes, [b":READ?\r"])
            self.assertEqual(ser.reset_count, 1)
            self.assertEqual(ser.flush_count, 1)

            ser = FakeKeithleySerial([b"", b"2.0,0.005\n"])
            self.assertEqual(panel.read_voltage_current(ser), (2.0, 0.005))
        finally:
            frame.Destroy()

    def test_tpc_com_port_and_baudrate_are_editable(self):
        frame = wx.Frame(None)
        try:
            panel = TpcLaserDiodePanel(frame)
            self.assertEqual(panel.tc_com_port.GetValue(), "COM3")
            self.assertEqual(panel.choice_baudrate.GetStringSelection(), "38400")
            self.assertEqual(panel.read_baudrate(), 38400)

            panel.tc_com_port.SetValue(" COM6 ")
            panel.choice_baudrate.SetStringSelection("19200")
            self.assertEqual(panel.read_com_port(), "COM6")
            self.assertEqual(panel.read_baudrate(), 19200)

            panel.tc_com_port.SetValue("  ")
            with self.assertRaises(ValueError):
                panel.read_com_port()
        finally:
            frame.Destroy()


if __name__ == "__main__":
    unittest.main()








