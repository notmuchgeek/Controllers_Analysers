"""
AFM/KPFM Keithley current / intensity source control panel.

Major structure
---------------
1. Quick Test remains available as a standalone test mode.
2. Source mode selects the meaning of ON values:
   - Current mode: values are source current in mA.
   - Intensity mode: values are target laser intensity in mW and are converted
     to current using a calibration CSV.
3. Control pattern selects the ON/OFF timing:
   - Recurrent control: repeated ON/OFF sequence.
   - Step control: manual step sequence, previously called Manual mode.
   Function control is an optional overlay that replaces each ON stage value
   with f(x), with normalized x from 0 to 1 during that ON stage.
4. Intensity calibration and f(x) evaluation are handled by intensity_profile_tools.py.
5. The Keithley execution layer always receives current in mA.

Please verify the COM port, baudrate, voltage compliance, current limit,
calibration CSV, and Keithley model before connecting a real device.
"""

from __future__ import annotations

import ast
import csv
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import wx
import serial

import matplotlib
matplotlib.use("WXAgg")
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

from ca_app.core.intensity_profile_tools import (
    CalibrationError,
    EMPIRICAL_CALIBRATION_METHODS,
    FunctionExpressionError,
    LaserCalibrationModel,
    evaluate_user_function,
    load_intensity_csv,
)
from ca_app.runtime.usage_logger import file_metadata, log_usage_event


DEFAULT_COM_PORT = "COM3"
DEFAULT_BAUDRATE = 38400
BAUDRATE_CHOICES = ("9600", "19200", "38400", "57600")
DEFAULT_COMPLIANCE_V = 5.0
DEFAULT_INTERNAL_MAX_CURRENT_MA = 110.0
DEFAULT_CALIBRATION_FILENAME = "default_intensity_calibration.csv"
DEFAULT_CALIBRATION_FIT_X_MIN_MA = "67"
DEFAULT_CALIBRATION_FIT_X_MAX_MA = "94"
DEFAULT_FUNCTION_EXPR = "x*m+b"
DEFAULT_FUNCTION_X_MIN = "0"
DEFAULT_FUNCTION_X_MAX = "180"
DEFAULT_FUNCTION_Y_MIN = "0.1"
DEFAULT_FUNCTION_Y_MAX = "4.99"
SERIAL_TIMEOUT_S = 5.0
QUICK_TEST_PREVIEW_TIME_S = 10.0
FUNCTION_PROFILE_POINTS = 300
FUNCTION_EXEC_MIN_INTERVAL_S = 0.05

FUNCTION_FIT_NAMESPACE = {
    "np": np,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "arcsin": np.arcsin,
    "arccos": np.arccos,
    "arctan": np.arctan,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "minimum": np.minimum,
    "maximum": np.maximum,
    "clip": np.clip,
    "pi": np.pi,
    "e": np.e,
}

FUNCTION_FIT_ALLOWED_AST_NODES = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Num,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Call,
    ast.Attribute,
}

SOURCE_CURRENT = "Current"
SOURCE_INTENSITY = "Intensity"

CONTROL_FUNCTION = "Function"
CONTROL_RECURRENT = "Recurrent"
CONTROL_STEP = "Step"


class AfmControllerPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        self.running = False
        self.quick_running = False
        self.stop_event = threading.Event()
        self.quick_stop_event = threading.Event()
        self.worker_thread = None
        self.quick_thread = None
        self.serial_lock = threading.Lock()
        self.active_serial = None
        self.data_rows = []
        self.live_voltage_times: List[float] = []
        self.live_voltage_values: List[float] = []
        self.live_source_current_times: List[float] = []
        self.live_source_current_values: List[float] = []
        self.live_start_time: Optional[float] = None
        self.step_status_text = ""

        self.calibration_path: str = ""
        self.calibration_model: Optional[LaserCalibrationModel] = None
        self.calibration_reload_timer = None
        self.calibration_loading = False
        self.calibration_load_generation = 0
        self.calibration_background_thread = None
        self.calibration_model_cache = {}

        self.manual_off_checks = {}
        self.manual_off_times = {}
        self.manual_on_checks = {}
        self.manual_on_values = {}
        self.manual_on_times = {}

        self.updating_function_fields = False
        self.function_driver_fields = []

        self.initialising = True
        self.build_ui()

        self.cb_current_mode.SetValue(True)
        self.cb_step_control.SetValue(True)
        self.initialising = False

        self.update_source_mode_controls()
        self.update_control_pattern_controls()
        self.update_quick_test_controls()
        self.update_preview()
        self.update_calibration_plot()
        self.update_function_preview_plot()
        wx.CallAfter(self.load_default_calibration_if_available)

    # ------------------------------------------------------------------
    # GUI construction
    # ------------------------------------------------------------------
    def build_ui(self):
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        left_panel = self.build_left_control_panel(self)
        right_panel = self.build_right_preview_panel(self)
        main_sizer.Add(left_panel, 0, wx.EXPAND | wx.ALL, 8)
        main_sizer.Add(right_panel, 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(main_sizer)
        self.SetMinSize((1260, 760))

    def build_left_control_panel(self, parent):
        panel = wx.Panel(parent)
        panel.SetMinSize((650, -1))

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.top_settings_notebook = self.build_top_settings_notebook(panel)
        sizer.Add(self.top_settings_notebook, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.build_intensity_function_section(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        sizer.Add(self.build_control_pattern(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        self.control_notebook = self.build_control_notebook(panel)
        sizer.Add(self.control_notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        sizer.Add(self.build_bottom_buttons(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        panel.SetSizer(sizer)
        return panel

    def build_right_preview_panel(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.preview_notebook = wx.Notebook(panel)
        self.source_preview_panel = self.build_source_preview_page(self.preview_notebook)
        self.function_preview_panel = self.build_function_preview_page(self.preview_notebook)
        self.calibration_preview_panel = self.build_calibration_preview_page(self.preview_notebook)
        self.live_voltage_panel = self.build_live_voltage_page(self.preview_notebook)
        self.preview_notebook.AddPage(self.source_preview_panel, "Source profile")
        self.preview_notebook.AddPage(self.function_preview_panel, "Function profile")
        self.preview_notebook.AddPage(self.calibration_preview_panel, "Intensity calibration")
        self.preview_notebook.AddPage(self.live_voltage_panel, "Live voltage")

        sizer.Add(self.preview_notebook, 4, wx.EXPAND | wx.BOTTOM, 8)
        sizer.Add(self.build_log(panel), 1, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel

    def build_top_settings_notebook(self, parent):
        notebook = wx.Notebook(parent)
        notebook.SetMinSize((610, -1))

        self.global_settings_panel = wx.Panel(notebook)
        global_sizer = wx.BoxSizer(wx.VERTICAL)
        global_sizer.Add(self.build_global_settings(self.global_settings_panel), 0, wx.EXPAND | wx.ALL, 6)
        self.global_settings_panel.SetSizer(global_sizer)

        self.source_quick_panel = wx.Panel(notebook)
        source_quick_sizer = wx.BoxSizer(wx.VERTICAL)
        source_quick_sizer.Add(self.build_quick_test(self.source_quick_panel), 0, wx.EXPAND | wx.ALL, 6)
        self.source_quick_panel.SetSizer(source_quick_sizer)

        notebook.AddPage(self.global_settings_panel, "Global settings")
        notebook.AddPage(self.source_quick_panel, "Quick Test")
        return notebook
    def build_global_settings(self, parent):
        box = wx.BoxSizer(wx.VERTICAL)
        self.global_settings_grid = wx.FlexGridSizer(rows=3, cols=6, vgap=6, hgap=6)
        self.global_settings_grid.AddGrowableCol(1, 1)
        self.global_settings_grid.AddGrowableCol(4, 1)

        self.tc_com_port = wx.TextCtrl(parent, value=DEFAULT_COM_PORT)
        self.choice_baudrate = wx.Choice(parent, choices=list(BAUDRATE_CHOICES))
        self.choice_baudrate.SetStringSelection(str(DEFAULT_BAUDRATE))
        self.tc_compliance = wx.TextCtrl(parent, value=str(DEFAULT_COMPLIANCE_V))
        self.tc_internal_max_current = wx.TextCtrl(parent, value=str(DEFAULT_INTERNAL_MAX_CURRENT_MA))
        self.tc_measured_voltage = wx.TextCtrl(parent, style=wx.TE_READONLY)

        self.add_labeled_pair_row(
            self.global_settings_grid,
            parent,
            "COM port",
            self.tc_com_port,
            "",
            "Baudrate",
            self.choice_baudrate,
            "",
        )
        self.add_labeled_pair_row(
            self.global_settings_grid,
            parent,
            "Voltage compliance",
            self.tc_compliance,
            "V",
            "Internal max current",
            self.tc_internal_max_current,
            "mA",
        )
        self.add_labeled_pair_row(
            self.global_settings_grid,
            parent,
            "Measured voltage",
            self.tc_measured_voltage,
            "V",
            "",
            wx.StaticText(parent, label=""),
            "",
        )

        self.source_mode_row = wx.BoxSizer(wx.HORIZONTAL)
        self.cb_current_mode = wx.RadioButton(parent, label="Current mode", style=wx.RB_GROUP)
        self.cb_intensity_mode = wx.RadioButton(parent, label="Intensity mode")
        self.cb_current_mode.Bind(wx.EVT_RADIOBUTTON, self.on_source_mode_checkbox)
        self.cb_intensity_mode.Bind(wx.EVT_RADIOBUTTON, self.on_source_mode_checkbox)
        self.source_mode_row.Add(wx.StaticText(parent, label="Source mode"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        self.source_mode_row.Add(self.cb_current_mode, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        self.source_mode_row.Add(self.cb_intensity_mode, 0, wx.ALIGN_CENTER_VERTICAL)

        box.Add(self.global_settings_grid, 0, wx.EXPAND)
        box.Add(self.source_mode_row, 0, wx.EXPAND | wx.TOP, 8)
        self.tc_com_port.Bind(wx.EVT_TEXT, self.on_any_input_change)
        self.choice_baudrate.Bind(wx.EVT_CHOICE, self.on_any_input_change)
        self.tc_compliance.Bind(wx.EVT_TEXT, self.on_any_input_change)
        self.tc_internal_max_current.Bind(wx.EVT_TEXT, self.on_any_input_change)
        return box

    def build_quick_test(self, parent):
        box = wx.BoxSizer(wx.VERTICAL)
        self.cb_quick_test = wx.CheckBox(parent, label="Enable Quick Test")
        self.cb_quick_test.Bind(wx.EVT_CHECKBOX, self.on_quick_test_checkbox)

        self.quick_test_row = wx.BoxSizer(wx.HORIZONTAL)
        self.st_quick_value_label = wx.StaticText(parent, label="Source current")
        self.st_quick_value_label.SetMinSize((105, -1))
        self.tc_quick_value = wx.TextCtrl(parent, value="")
        self.tc_quick_value.SetMinSize((80, -1))
        self.st_quick_unit = wx.StaticText(parent, label="mA")
        self.btn_quick_toggle = wx.Button(parent, label="ON")
        self.sync_quick_toggle_button_size()
        self.btn_quick_toggle.SetBackgroundColour(wx.Colour(0, 210, 0))
        self.btn_quick_toggle.Bind(wx.EVT_BUTTON, self.on_quick_toggle)

        self.quick_test_row.Add(self.st_quick_value_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.quick_test_row.Add(self.tc_quick_value, 1, wx.EXPAND | wx.RIGHT, 6)
        self.quick_test_row.Add(self.st_quick_unit, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.quick_test_row.Add(self.btn_quick_toggle, 0, wx.ALIGN_CENTER_VERTICAL)

        box.Add(self.cb_quick_test, 0, wx.BOTTOM, 8)
        box.Add(self.quick_test_row, 0, wx.EXPAND)
        self.tc_quick_value.Bind(wx.EVT_TEXT, self.on_any_input_change)
        return box

    def build_intensity_function_section(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.intensity_function_notebook = wx.Notebook(panel)
        self.calibration_controls_panel = self.build_intensity_calibration_page(self.intensity_function_notebook)
        self.function_controls_panel = self.build_function_control_page(self.intensity_function_notebook)
        self.intensity_function_notebook.AddPage(self.calibration_controls_panel, "Calibration")
        self.intensity_function_notebook.AddPage(self.function_controls_panel, "Function control")
        sizer.Add(self.intensity_function_notebook, 0, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel

    def build_intensity_calibration_page(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_load_calibration = wx.Button(panel, label="Load CSV")
        self.btn_load_calibration.Bind(wx.EVT_BUTTON, self.on_load_calibration_csv)
        self.calibration_file_label = wx.StaticText(panel, label="No calibration CSV loaded")
        row1.Add(self.btn_load_calibration, 0, wx.RIGHT, 8)
        row1.Add(self.calibration_file_label, 1, wx.ALIGN_CENTER_VERTICAL)

        fit_row = wx.FlexGridSizer(rows=1, cols=6, vgap=6, hgap=6)
        fit_row.AddGrowableCol(1, 1)
        self.fit_method_choice = wx.Choice(
            panel,
            choices=EMPIRICAL_CALIBRATION_METHODS + ["Interpolation", "Linear", "Quadratic", "Cubic"],
        )
        self.fit_method_choice.SetSelection(0)
        self.fit_method_choice.Bind(wx.EVT_CHOICE, self.on_fit_method_changed)
        self.tc_calibration_xmin = wx.TextCtrl(panel, value=DEFAULT_CALIBRATION_FIT_X_MIN_MA)
        self.tc_calibration_xmax = wx.TextCtrl(panel, value=DEFAULT_CALIBRATION_FIT_X_MAX_MA)
        self.tc_calibration_xmin.SetMinSize((64, -1))
        self.tc_calibration_xmax.SetMinSize((64, -1))
        fit_row.Add(wx.StaticText(panel, label="Fit method"), 0, wx.ALIGN_CENTER_VERTICAL)
        fit_row.Add(self.fit_method_choice, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        fit_row.Add(wx.StaticText(panel, label="Fit X min / mA"), 0, wx.ALIGN_CENTER_VERTICAL)
        fit_row.Add(self.tc_calibration_xmin, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        fit_row.Add(wx.StaticText(panel, label="Fit X max / mA"), 0, wx.ALIGN_CENTER_VERTICAL)
        fit_row.Add(self.tc_calibration_xmax, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        stats_grid = wx.FlexGridSizer(rows=2, cols=3, vgap=3, hgap=16)
        for col in range(3):
            stats_grid.AddGrowableCol(col, 1)
        self.calibration_stats_labels = [
            wx.StaticText(panel, label="R² = --"),
            wx.StaticText(panel, label="RMSE = -- mW"),
            wx.StaticText(panel, label="MAE = -- mW"),
            wx.StaticText(panel, label="Max error = -- mW"),
            wx.StaticText(panel, label="Current range = -- to -- mA"),
            wx.StaticText(panel, label="Intensity range = -- to -- mW"),
        ]
        for label in self.calibration_stats_labels:
            stats_grid.Add(label, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(row1, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(fit_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        sizer.Add(stats_grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        panel.SetSizer(sizer)
        self.tc_calibration_xmin.Bind(wx.EVT_TEXT, self.on_calibration_range_changed)
        self.tc_calibration_xmax.Bind(wx.EVT_TEXT, self.on_calibration_range_changed)
        return panel

    def build_function_control_page(self, parent):
        panel = wx.Panel(parent)
        self.cb_function_control = wx.CheckBox(panel, label="Enable Function control")
        self.cb_function_control.Bind(wx.EVT_CHECKBOX, self.on_function_control_checkbox)

        self.tc_function_expr = wx.TextCtrl(panel, value=DEFAULT_FUNCTION_EXPR)
        self.btn_fit_function = wx.Button(panel, label="Fit it")
        self.btn_parameterise_function = wx.Button(panel, label="Parameterise")
        self.btn_fit_function.Bind(wx.EVT_BUTTON, self.on_fit_function)
        self.btn_parameterise_function.Bind(wx.EVT_BUTTON, self.on_parameterise_function)
        self.tc_function_xmin = wx.TextCtrl(panel, value=DEFAULT_FUNCTION_X_MIN)
        self.tc_function_xmax = wx.TextCtrl(panel, value=DEFAULT_FUNCTION_X_MAX)
        self.tc_function_ymin = wx.TextCtrl(panel, value=DEFAULT_FUNCTION_Y_MIN)
        self.tc_function_ymax = wx.TextCtrl(panel, value=DEFAULT_FUNCTION_Y_MAX)
        self.sync_function_action_button_sizes()

        expr_row = wx.FlexGridSizer(rows=1, cols=4, vgap=4, hgap=6)
        expr_row.AddGrowableCol(1, 1)
        self.lbl_function_expr = wx.StaticText(panel, label="f(x) =")
        expr_row.Add(self.lbl_function_expr, 0, wx.ALIGN_CENTER_VERTICAL)
        expr_row.Add(self.tc_function_expr, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        expr_row.Add(self.btn_fit_function, 0, wx.ALIGN_CENTER_VERTICAL)
        expr_row.Add(self.btn_parameterise_function, 0, wx.ALIGN_CENTER_VERTICAL)

        bounds_row = wx.FlexGridSizer(rows=1, cols=8, vgap=4, hgap=6)
        for col in [1, 3, 5, 7]:
            bounds_row.AddGrowableCol(col, 1)
        for ctrl in [self.tc_function_xmin, self.tc_function_xmax, self.tc_function_ymin, self.tc_function_ymax]:
            ctrl.SetMinSize((52, -1))
        bounds_row.Add(wx.StaticText(panel, label="X min"), 0, wx.ALIGN_CENTER_VERTICAL)
        bounds_row.Add(self.tc_function_xmin, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        bounds_row.Add(wx.StaticText(panel, label="X max"), 0, wx.ALIGN_CENTER_VERTICAL)
        bounds_row.Add(self.tc_function_xmax, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        bounds_row.Add(wx.StaticText(panel, label="Y min"), 0, wx.ALIGN_CENTER_VERTICAL)
        bounds_row.Add(self.tc_function_ymin, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        bounds_row.Add(wx.StaticText(panel, label="Y max"), 0, wx.ALIGN_CENTER_VERTICAL)
        bounds_row.Add(self.tc_function_ymax, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        self.function_range_labels = [
            wx.StaticText(panel, label="Current range = -- to -- mA"),
            wx.StaticText(panel, label="Intensity range = -- to -- mW"),
        ]
        function_range_row = wx.FlexGridSizer(rows=1, cols=2, vgap=3, hgap=16)
        function_range_row.AddGrowableCol(0, 1)
        function_range_row.AddGrowableCol(1, 1)
        for label in self.function_range_labels:
            function_range_row.Add(label, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.cb_function_control, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 5)
        sizer.Add(expr_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        sizer.Add(bounds_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        sizer.Add(function_range_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        panel.SetSizer(sizer)

        self.function_input_controls = [
            self.tc_function_expr,
            self.tc_function_xmin,
            self.tc_function_xmax,
            self.tc_function_ymin,
            self.tc_function_ymax,
        ]
        self.function_bound_controls = {
            "x_min": self.tc_function_xmin,
            "x_max": self.tc_function_xmax,
            "y_min": self.tc_function_ymin,
            "y_max": self.tc_function_ymax,
        }
        for ctrl in self.function_input_controls:
            ctrl.Bind(wx.EVT_TEXT, self.on_function_input_change)
        return panel

    def build_control_pattern(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "Control pattern")
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.cb_recurrent_control = wx.CheckBox(parent, label="Recurrent control")
        self.cb_step_control = wx.CheckBox(parent, label="Step control")
        for cb in [self.cb_recurrent_control, self.cb_step_control]:
            cb.Bind(wx.EVT_CHECKBOX, self.on_control_pattern_checkbox)
            row.Add(cb, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        box.Add(row, 0, wx.EXPAND)
        return box

    def build_control_notebook(self, parent):
        notebook = wx.Notebook(parent)
        notebook.SetMinSize((610, 330))
        self.recurrent_panel = self.build_recurrent_panel(notebook)
        self.step_panel = self.build_step_panel(notebook)
        notebook.AddPage(self.recurrent_panel, "Recurrent control")
        notebook.AddPage(self.step_panel, "Step control")
        return notebook

    def build_recurrent_panel(self, parent):
        scrolled = wx.ScrolledWindow(parent, style=wx.VSCROLL)
        scrolled.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(rows=5, cols=3, vgap=8, hgap=6)
        grid.AddGrowableCol(1, 1)

        self.tc_initial_off_time = wx.TextCtrl(scrolled, value="5")
        self.tc_recurrent_on_value = wx.TextCtrl(scrolled, value="1")
        self.tc_recurrent_on_time = wx.TextCtrl(scrolled, value="1")
        self.tc_recurrent_off_time = wx.TextCtrl(scrolled, value="5")
        self.tc_recurrent_times = wx.TextCtrl(scrolled, value="3")
        self.st_recurrent_on_label = wx.StaticText(scrolled, label="Recurrent ON current")
        self.st_recurrent_on_unit = wx.StaticText(scrolled, label="mA")

        self.add_labeled_row(grid, scrolled, "Initial OFF time", self.tc_initial_off_time, "s")
        grid.Add(self.st_recurrent_on_label, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.tc_recurrent_on_value, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.st_recurrent_on_unit, 0, wx.ALIGN_CENTER_VERTICAL)
        self.add_labeled_row(grid, scrolled, "Recurrent ON time", self.tc_recurrent_on_time, "s")
        self.add_labeled_row(grid, scrolled, "Recurrent OFF time", self.tc_recurrent_off_time, "s")
        self.add_labeled_row(grid, scrolled, "Recurrent times", self.tc_recurrent_times, "")

        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        scrolled.SetSizer(sizer)
        for ctrl in [
            self.tc_initial_off_time,
            self.tc_recurrent_on_value,
            self.tc_recurrent_on_time,
            self.tc_recurrent_off_time,
            self.tc_recurrent_times,
        ]:
            ctrl.Bind(wx.EVT_TEXT, self.on_any_input_change)
        return scrolled

    def build_step_panel(self, parent):
        scrolled = wx.ScrolledWindow(parent, style=wx.VSCROLL)
        scrolled.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(rows=14, cols=4, vgap=5, hgap=6)
        grid.AddGrowableCol(2, 1)
        grid.AddGrowableCol(3, 1)

        self.st_step_value_header = wx.StaticText(scrolled, label="Current / mA")
        headers = [wx.StaticText(scrolled, label="Use?"), wx.StaticText(scrolled, label="Event"), self.st_step_value_header, wx.StaticText(scrolled, label="Time / s")]
        for text in headers:
            font = text.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            text.SetFont(font)
            grid.Add(text, 0, wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM, 4)

        for n in range(1, 7):
            off_check = wx.CheckBox(scrolled)
            off_time = wx.TextCtrl(scrolled, value="", size=(140, -1))
            self.manual_off_checks[n] = off_check
            self.manual_off_times[n] = off_time
            grid.Add(off_check, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(wx.StaticText(scrolled, label=f"{self.ordinal(n)} OFF"), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(wx.StaticText(scrolled, label="OFF"), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(off_time, 0, wx.EXPAND)

            on_check = wx.CheckBox(scrolled)
            on_value = wx.TextCtrl(scrolled, value="", size=(140, -1))
            on_time = wx.TextCtrl(scrolled, value="", size=(140, -1))
            self.manual_on_checks[n] = on_check
            self.manual_on_values[n] = on_value
            self.manual_on_times[n] = on_time
            grid.Add(on_check, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(wx.StaticText(scrolled, label=f"{self.ordinal(n)} ON"), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(on_value, 0, wx.EXPAND)
            grid.Add(on_time, 0, wx.EXPAND)

            off_check.Bind(wx.EVT_CHECKBOX, self.on_step_row_change)
            on_check.Bind(wx.EVT_CHECKBOX, self.on_step_row_change)
            off_time.Bind(wx.EVT_TEXT, self.on_any_input_change)
            on_value.Bind(wx.EVT_TEXT, self.on_any_input_change)
            on_time.Bind(wx.EVT_TEXT, self.on_any_input_change)

        off7_check = wx.CheckBox(scrolled)
        off7_time = wx.TextCtrl(scrolled, value="")
        self.manual_off_checks[7] = off7_check
        self.manual_off_times[7] = off7_time
        grid.Add(off7_check, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(scrolled, label="7th OFF"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(scrolled, label="OFF"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(off7_time, 0, wx.EXPAND)
        off7_check.Bind(wx.EVT_CHECKBOX, self.on_step_row_change)
        off7_time.Bind(wx.EVT_TEXT, self.on_any_input_change)

        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        scrolled.SetSizer(sizer)
        return scrolled

    def build_bottom_buttons(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_save_source = wx.Button(panel, label="Save CSV (Source)")
        self.btn_save_params = wx.Button(panel, label="Save Parameters")
        self.btn_load_params = wx.Button(panel, label="Load Parameters")
        self.btn_save_keithley = wx.Button(panel, label="Save Keithley CSV")
        self.btn_start = wx.Button(panel, label="START")
        self.btn_stop = wx.Button(panel, label="STOP")
        self.btn_start.SetBackgroundColour(wx.Colour(0, 210, 0))
        self.btn_stop.SetBackgroundColour(wx.Colour(240, 70, 70))
        for btn in [self.btn_save_source, self.btn_save_params, self.btn_load_params, self.btn_save_keithley, self.btn_start, self.btn_stop]:
            btn.SetMinSize((96, 28))
        for btn in [self.btn_save_source, self.btn_save_params, self.btn_load_params]:
            row1.Add(btn, 1, wx.EXPAND | wx.RIGHT, 5)
        for btn in [self.btn_save_keithley, self.btn_start, self.btn_stop]:
            row2.Add(btn, 1, wx.EXPAND | wx.RIGHT, 5)
        self.btn_save_source.Bind(wx.EVT_BUTTON, self.on_save_source_csv)
        self.btn_save_params.Bind(wx.EVT_BUTTON, self.on_save_parameters)
        self.btn_load_params.Bind(wx.EVT_BUTTON, self.on_load_parameters)
        self.btn_save_keithley.Bind(wx.EVT_BUTTON, self.on_save_keithley_csv)
        self.btn_save_keithley.Disable()
        self.btn_start.Bind(wx.EVT_BUTTON, self.on_start)
        self.btn_stop.Bind(wx.EVT_BUTTON, self.on_stop)
        sizer.Add(row1, 0, wx.EXPAND | wx.BOTTOM, 5)
        sizer.Add(row2, 0, wx.EXPAND)
        panel.SetSizer(sizer)
        return panel

    def build_source_preview_page(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.figure_source = Figure(figsize=(10.5, 4.9))
        self.ax_source = self.figure_source.add_subplot(111)
        self.ax_source_intensity = None
        self.canvas_source = FigureCanvasWxAgg(panel, -1, self.figure_source)
        self.canvas_source.SetMinSize((-1, 500))
        sizer.Add(self.canvas_source, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        return panel

    def build_function_preview_page(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.figure_function = Figure(figsize=(10.5, 4.9))
        self.ax_function = self.figure_function.add_subplot(111)
        self.canvas_function = FigureCanvasWxAgg(panel, -1, self.figure_function)
        self.canvas_function.SetMinSize((-1, 500))
        sizer.Add(self.canvas_function, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        return panel

    def build_calibration_preview_page(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.figure_calibration = Figure(figsize=(10.5, 4.9))
        self.ax_calibration = self.figure_calibration.add_subplot(111)
        self.canvas_calibration = FigureCanvasWxAgg(panel, -1, self.figure_calibration)
        self.canvas_calibration.SetMinSize((-1, 500))
        sizer.Add(self.canvas_calibration, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        return panel

    def build_live_voltage_page(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.figure_live = Figure(figsize=(10.5, 4.9))
        self.ax_live = self.figure_live.add_subplot(111)
        self.ax_live_current = None
        self.canvas_live = FigureCanvasWxAgg(panel, -1, self.figure_live)
        self.canvas_live.SetMinSize((-1, 500))
        sizer.Add(self.canvas_live, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        return panel

    def build_log(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "Status / log")
        self.log_box = wx.TextCtrl(parent, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.log_box.SetMinSize((-1, 145))
        box.Add(self.log_box, 1, wx.EXPAND | wx.ALL, 8)
        return box

    @staticmethod
    def add_labeled_row(grid, parent, label, ctrl, unit):
        grid.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=unit), 0, wx.ALIGN_CENTER_VERTICAL)

    @staticmethod
    def add_labeled_pair_row(grid, parent, left_label, left_ctrl, left_unit, right_label, right_ctrl, right_unit):
        grid.Add(wx.StaticText(parent, label=left_label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(left_ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=left_unit), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=right_label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(right_ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=right_unit), 0, wx.ALIGN_CENTER_VERTICAL)

    @staticmethod
    def add_labeled_single_row(grid, parent, label, ctrl, unit):
        grid.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=unit), 0, wx.ALIGN_CENTER_VERTICAL)
        for _ in range(3):
            grid.Add(wx.StaticText(parent, label=""), 0, wx.ALIGN_CENTER_VERTICAL)

    @staticmethod
    def ordinal(n):
        if n == 1:
            return "1st"
        if n == 2:
            return "2nd"
        if n == 3:
            return "3rd"
        return f"{n}th"

    # ------------------------------------------------------------------
    # GUI state
    # ------------------------------------------------------------------
    def current_source_mode(self) -> str:
        if self.cb_intensity_mode.GetValue():
            return SOURCE_INTENSITY
        if self.cb_current_mode.GetValue():
            return SOURCE_CURRENT
        raise ValueError("Please select Current mode or Intensity mode.")

    def current_control_pattern(self) -> str:
        if self.cb_recurrent_control.IsChecked():
            return CONTROL_RECURRENT
        if self.cb_step_control.IsChecked():
            return CONTROL_STEP
        raise ValueError("Please select Recurrent control or Step control.")

    def function_control_enabled(self) -> bool:
        return self.cb_function_control.IsChecked()

    def base_control_selected(self) -> bool:
        return self.cb_recurrent_control.IsChecked() or self.cb_step_control.IsChecked()

    def on_quick_test_checkbox(self, event):
        if self.cb_quick_test.IsChecked() and self.cb_function_control.IsChecked():
            self.cb_quick_test.SetValue(False)
            self.show_warning("Untick Function control before enabling Quick Test.")
            self.update_quick_test_controls()
            self.update_preview()
            return
        if not self.cb_quick_test.IsChecked() and self.quick_running:
            self.stop_quick_test()
        self.update_quick_test_controls()
        self.update_preview()
        if self.cb_quick_test.IsChecked() and hasattr(self, "preview_notebook"):
            self.preview_notebook.SetSelection(0)

    def on_source_mode_checkbox(self, event):
        self.update_source_mode_controls()
        if (
            self.cb_intensity_mode.GetValue()
            and self.calibration_model is None
            and not self.initialising
        ):
            if hasattr(self, "intensity_function_notebook"):
                self.intensity_function_notebook.SetSelection(0)
            self.show_warning("Intensity mode requires a calibration CSV. Load a current-intensity calibration before running or previewing intensity-controlled output.")
        self.update_preview()
        self.update_calibration_plot()

    def on_control_pattern_checkbox(self, event):
        self.update_control_pattern_controls()
        if self.cb_function_control.IsChecked() and not self.base_control_selected():
            self.cb_function_control.SetValue(False)
            if not self.initialising:
                self.show_warning("Function control requires Recurrent control or Step control to be selected.")
            self.update_function_control_controls()
            self.update_quick_test_controls()
        self.update_preview()

    def on_function_control_checkbox(self, event):
        if self.cb_function_control.IsChecked():
            if self.cb_quick_test.IsChecked():
                self.cb_function_control.SetValue(False)
                self.show_warning("Turn Quick Test off before enabling Function control.")
            elif not self.base_control_selected():
                self.cb_function_control.SetValue(False)
                self.show_warning("Select Recurrent control or Step control before enabling Function control.")
        self.update_control_pattern_controls()
        self.update_function_control_controls()
        self.update_quick_test_controls()
        self.update_preview()
        self.update_function_preview_plot()
        if self.cb_function_control.IsChecked() and hasattr(self, "preview_notebook"):
            self.preview_notebook.SetSelection(1)

    def on_step_row_change(self, event):
        self.update_step_row_enabled_state()
        self.update_preview()

    def on_any_input_change(self, event):
        if not self.initialising:
            self.update_preview()
        event.Skip()

    def on_function_input_change(self, event):
        if not self.initialising and not self.updating_function_fields:
            ctrl = event.GetEventObject()
            has_fit_parameters = self.function_expression_has_fit_parameters()
            if not has_fit_parameters:
                if ctrl is self.tc_function_expr:
                    self.autofill_function_y_from_x("x_min")
                    self.autofill_function_y_from_x("x_max")
                elif ctrl is self.tc_function_xmin:
                    self.autofill_function_y_from_x("x_min")
                elif ctrl is self.tc_function_xmax:
                    self.autofill_function_y_from_x("x_max")
                elif ctrl is self.tc_function_ymin:
                    self.autofill_function_x_from_y("y_min")
                elif ctrl is self.tc_function_ymax:
                    self.autofill_function_x_from_y("y_max")
                else:
                    self.try_autofill_function_bounds()
            self.update_preview()
            self.update_function_preview_plot()
        event.Skip()

    def sync_quick_toggle_button_size(self):
        if not hasattr(self, "btn_quick_toggle") or not hasattr(self, "tc_quick_value"):
            return
        input_height = max(self.tc_quick_value.GetBestSize().GetHeight(), self.tc_quick_value.GetMinSize().GetHeight())
        if input_height <= 0:
            input_height = -1
        self.btn_quick_toggle.SetMinSize((96, input_height))
        self.btn_quick_toggle.SetInitialSize((96, input_height))

    def sync_function_action_button_sizes(self):
        if not hasattr(self, "btn_fit_function") or not hasattr(self, "btn_parameterise_function"):
            return
        fit_size = self.btn_fit_function.GetBestSize()
        parameterise_size = self.btn_parameterise_function.GetBestSize()
        width = max(fit_size.GetWidth(), parameterise_size.GetWidth())
        height = max(fit_size.GetHeight(), parameterise_size.GetHeight())
        for button in [self.btn_fit_function, self.btn_parameterise_function]:
            button.SetMinSize((width, height))
            button.SetInitialSize((width, height))

    def update_quick_test_controls(self):
        quick_enabled = self.cb_quick_test.IsChecked()
        self.cb_quick_test.Enable(not self.cb_function_control.IsChecked() or quick_enabled)
        self.tc_quick_value.Enable(quick_enabled and not self.quick_running)
        self.btn_quick_toggle.Enable(quick_enabled)
        self.btn_quick_toggle.SetLabel("OFF" if self.quick_running else "ON")
        self.sync_quick_toggle_button_size()
        self.btn_quick_toggle.SetBackgroundColour(wx.Colour(240, 70, 70) if self.quick_running else wx.Colour(0, 210, 0))
        if hasattr(self, "source_quick_panel"):
            self.source_quick_panel.Layout()

        for w in [
            self.cb_current_mode,
            self.cb_intensity_mode,
            self.btn_load_calibration,
            self.fit_method_choice,
            self.cb_function_control,
            self.cb_recurrent_control,
            self.cb_step_control,
            self.control_notebook,
            self.btn_start,
            self.btn_stop,
            self.btn_save_source,
        ]:
            w.Enable(not quick_enabled)
        self.update_save_keithley_controls()

        if quick_enabled:
            self.set_panel_enabled(self.recurrent_panel, False)
            self.set_panel_enabled(self.step_panel, False)
            for ctrl in self.function_input_controls:
                ctrl.Enable(False)
            self.btn_fit_function.Enable(False)
            self.btn_parameterise_function.Enable(False)
        else:
            self.update_source_mode_controls()
            self.update_control_pattern_controls()
            self.update_function_control_controls()

    def update_source_mode_controls(self):
        mode = SOURCE_INTENSITY if self.cb_intensity_mode.GetValue() else SOURCE_CURRENT
        self.cb_current_mode.Enable()
        self.cb_intensity_mode.Enable()

        if self.cb_quick_test.IsChecked():
            return

        intensity_active = mode == SOURCE_INTENSITY
        self.btn_load_calibration.Enable(intensity_active)
        self.fit_method_choice.Enable(intensity_active)

        value_label = "Source current" if mode == SOURCE_CURRENT else "Target intensity"
        unit = "mA" if mode == SOURCE_CURRENT else "mW"
        self.st_quick_value_label.SetLabel(value_label)
        self.st_quick_unit.SetLabel(unit)
        self.st_recurrent_on_label.SetLabel("Recurrent ON current" if mode == SOURCE_CURRENT else "Recurrent ON intensity")
        self.st_recurrent_on_unit.SetLabel(unit)
        self.st_step_value_header.SetLabel("Current / mA" if mode == SOURCE_CURRENT else "Intensity / mW")
        self.Layout()

    def update_control_pattern_controls(self):
        if self.cb_quick_test.IsChecked():
            return
        selected = None
        if self.cb_recurrent_control.IsChecked():
            selected = CONTROL_RECURRENT
        elif self.cb_step_control.IsChecked():
            selected = CONTROL_STEP

        for cb in [self.cb_recurrent_control, self.cb_step_control]:
            cb.Enable(selected is None or cb.IsChecked())

        if selected == CONTROL_RECURRENT:
            self.control_notebook.SetSelection(0)
            self.set_panel_enabled(self.recurrent_panel, True)
            self.set_panel_enabled(self.step_panel, False)
        elif selected == CONTROL_STEP:
            self.control_notebook.SetSelection(1)
            self.set_panel_enabled(self.recurrent_panel, False)
            self.set_panel_enabled(self.step_panel, True)
        else:
            self.set_panel_enabled(self.recurrent_panel, False)
            self.set_panel_enabled(self.step_panel, False)
        self.update_recurrent_on_value_enabled_state()
        self.update_step_row_enabled_state()
        self.update_function_control_controls()

    def update_function_control_controls(self):
        quick_enabled = self.cb_quick_test.IsChecked()
        function_enabled = self.cb_function_control.IsChecked()
        self.cb_function_control.Enable(not quick_enabled)
        for ctrl in self.function_input_controls:
            ctrl.Enable(function_enabled and not quick_enabled)
        self.btn_fit_function.Enable(function_enabled and not quick_enabled)
        self.btn_parameterise_function.Enable(function_enabled and not quick_enabled)

    def set_panel_enabled(self, window, enabled):
        window.Enable(enabled)
        for child in window.GetChildren():
            self.set_panel_enabled(child, enabled)

    def update_recurrent_on_value_enabled_state(self):
        recurrent_active = self.cb_recurrent_control.IsChecked() and not self.cb_quick_test.IsChecked()
        function_enabled = self.cb_function_control.IsChecked()
        enabled = recurrent_active and not function_enabled
        for ctrl in [self.st_recurrent_on_label, self.tc_recurrent_on_value, self.st_recurrent_on_unit]:
            ctrl.Enable(enabled)

    def update_step_row_enabled_state(self):
        step_active = self.cb_step_control.IsChecked() and not self.cb_quick_test.IsChecked()
        function_enabled = self.cb_function_control.IsChecked()
        self.st_step_value_header.Enable(step_active and not function_enabled)
        for n in range(1, 8):
            off_check = self.manual_off_checks[n]
            off_time = self.manual_off_times[n]
            off_check.Enable(step_active)
            off_time.Enable(step_active and off_check.IsChecked())
        for n in range(1, 7):
            on_check = self.manual_on_checks[n]
            on_value = self.manual_on_values[n]
            on_time = self.manual_on_times[n]
            on_check.Enable(step_active)
            on_value.Enable(step_active and on_check.IsChecked() and not function_enabled)
            on_time.Enable(step_active and on_check.IsChecked())

    # ------------------------------------------------------------------
    # Parsing and conversion
    # ------------------------------------------------------------------
    def show_warning(self, message):
        wx.MessageBox(message, "Input or safety warning", wx.OK | wx.ICON_WARNING)

    @staticmethod
    def parse_float_from_ctrl(ctrl, name, allow_zero=False, allow_negative=False):
        text = ctrl.GetValue().strip()
        if text == "":
            raise ValueError(f"{name} is empty.")
        try:
            value = float(text)
        except ValueError:
            raise ValueError(f"{name} must be a number.")
        if not allow_negative and value < 0:
            raise ValueError(f"{name} must not be negative.")
        if allow_zero:
            if value < 0:
                raise ValueError(f"{name} must be >= 0.")
        else:
            if value <= 0:
                raise ValueError(f"{name} must be > 0.")
        return value

    @staticmethod
    def parse_value_from_ctrl(ctrl, name):
        text = ctrl.GetValue().strip()
        if text == "":
            raise ValueError(f"{name} is empty.")
        try:
            value = float(text)
        except ValueError:
            raise ValueError(f"{name} must be a number.")
        return value

    @staticmethod
    def parse_optional_float_from_ctrl(ctrl, name):
        text = ctrl.GetValue().strip()
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"{name} must be a number.")

    @staticmethod
    def format_float_for_ctrl(value):
        return f"{float(value):.9g}"

    def read_global_settings(self):
        com_port = self.tc_com_port.GetValue().strip()
        if not com_port:
            raise ValueError("COM port must not be empty.")
        baudrate_text = self.choice_baudrate.GetStringSelection() or str(DEFAULT_BAUDRATE)
        try:
            baudrate = int(baudrate_text)
        except ValueError as exc:
            raise ValueError("Baudrate must be one of 9600, 19200, 38400, or 57600.") from exc
        compliance_v = self.parse_float_from_ctrl(self.tc_compliance, "Voltage compliance", allow_zero=False, allow_negative=False)
        internal_max_current_ma = self.parse_float_from_ctrl(self.tc_internal_max_current, "Internal max current", allow_zero=False, allow_negative=False)
        return {
            "com_port": com_port,
            "baudrate": baudrate,
            "compliance_v": compliance_v,
            "internal_max_current_ma": internal_max_current_ma,
        }

    def validate_current_against_internal_max(self, current_ma, max_current_ma, context):
        arr = np.asarray(current_ma, dtype=float)
        if np.any(np.abs(arr) > max_current_ma):
            worst = float(np.max(np.abs(arr)))
            raise ValueError(
                f"{context} requires current up to {worst:.6g} mA, which exceeds the Internal max current value "
                f"of {max_current_ma:.6g} mA. Output will not start. Increase the Internal max current / mA value "
                f"only if this is safe for your device."
            )

    def require_calibration(self) -> LaserCalibrationModel:
        if self.calibration_loading:
            raise ValueError("Intensity mode requires the calibration fit to finish loading first.")
        if self.calibration_model is None:
            raise ValueError("Intensity mode requires a calibration CSV to be loaded first.")
        return self.calibration_model

    def target_to_current_ma(self, value, source_mode, context, calibration_model=None):
        if source_mode == SOURCE_CURRENT:
            return np.asarray(value, dtype=float)
        model = calibration_model or self.require_calibration()
        return model.current_for_intensity(np.asarray(value, dtype=float))

    @staticmethod
    def normalise_function_expression(expr):
        return (expr or "").strip().replace("^", "**")

    def parse_function_fit_template(self, expr):
        expr = self.normalise_function_expression(expr)
        if not expr:
            raise ValueError("Function f(x) is empty.")
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Invalid f(x) syntax: {exc}") from exc

        parameter_names = []
        for node in ast.walk(tree):
            if type(node) not in FUNCTION_FIT_ALLOWED_AST_NODES:
                raise ValueError(f"Unsupported expression element: {type(node).__name__}.")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id not in FUNCTION_FIT_NAMESPACE:
                        raise ValueError(f"Unknown function '{node.func.id}'. Fit parameters cannot be called as functions.")
                elif isinstance(node.func, ast.Attribute):
                    if not isinstance(node.func.value, ast.Name) or node.func.value.id != "np":
                        raise ValueError("Only np.<function> attributes are allowed.")
                else:
                    raise ValueError("Unsupported function call in f(x).")
            if isinstance(node, ast.Attribute):
                if not isinstance(node.value, ast.Name) or node.value.id != "np":
                    raise ValueError("Only np.<function> attributes are allowed.")
            if isinstance(node, ast.Name):
                if node.id == "x" or node.id in FUNCTION_FIT_NAMESPACE:
                    continue
                if node.id not in parameter_names:
                    parameter_names.append(node.id)
        return expr, tree, parameter_names

    def function_expression_has_fit_parameters(self):
        try:
            _, _, parameter_names = self.parse_function_fit_template(self.tc_function_expr.GetValue())
        except Exception:
            return False
        return bool(parameter_names)

    def evaluate_function_fit_template(self, expr, x_values, parameters):
        expr, tree, _ = self.parse_function_fit_template(expr)
        x = np.asarray(list(x_values), dtype=float)
        namespace = dict(FUNCTION_FIT_NAMESPACE)
        namespace["x"] = x
        namespace.update({name: float(value) for name, value in parameters.items()})
        try:
            result = eval(compile(tree, "<fit f(x)>", "eval"), {"__builtins__": {}}, namespace)
        except Exception as exc:
            raise ValueError(f"Could not evaluate f(x) fit template: {exc}") from exc
        y = np.asarray(result, dtype=float)
        if y.ndim == 0:
            y = np.full_like(x, float(y), dtype=float)
        if y.shape != x.shape:
            try:
                y = np.broadcast_to(y, x.shape).astype(float)
            except ValueError as exc:
                raise ValueError("f(x) did not return a scalar or an array matching x.") from exc
        if not np.all(np.isfinite(y)):
            raise ValueError("f(x) produced NaN or infinite values.")
        return y

    def expression_with_fitted_parameters(self, expr, parameters):
        expr, tree, _ = self.parse_function_fit_template(expr)

        class ParameterReplacer(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id in parameters:
                    return ast.copy_location(ast.Constant(value=float(parameters[node.id])), node)
                return node

        fitted_tree = ParameterReplacer().visit(tree)
        ast.fix_missing_locations(fitted_tree)
        return ast.unparse(fitted_tree)

    @staticmethod
    def parameter_name_for_index(index):
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        name = ""
        current = int(index)
        while True:
            name = alphabet[current % len(alphabet)] + name
            current = current // len(alphabet) - 1
            if current < 0:
                return name

    def parameterise_function_expression(self, expr):
        expr, tree, existing_parameters = self.parse_function_fit_template(expr)
        used_names = set(existing_parameters) | {"x"} | set(FUNCTION_FIT_NAMESPACE)
        replacements = []
        next_index = 0

        def next_parameter_name():
            nonlocal next_index
            while True:
                name = self.parameter_name_for_index(next_index)
                next_index += 1
                if name not in used_names:
                    used_names.add(name)
                    return name

        def parameter_node(source_node):
            name = next_parameter_name()
            replacements.append(name)
            return ast.copy_location(ast.Name(id=name, ctx=ast.Load()), source_node)

        class NumericParameteriser(ast.NodeTransformer):
            def visit_UnaryOp(self, node):
                if isinstance(node.op, (ast.UAdd, ast.USub)) and isinstance(node.operand, ast.Constant):
                    value = node.operand.value
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        return parameter_node(node)
                return self.generic_visit(node)

            def visit_Constant(self, node):
                value = node.value
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return parameter_node(node)
                return node

        parameterised_tree = NumericParameteriser().visit(tree)
        if not replacements:
            raise ValueError("No numeric constants found in f(x) to parameterise.")
        ast.fix_missing_locations(parameterised_tree)
        return ast.unparse(parameterised_tree), replacements

    def fit_function_expression_to_bounds(self):
        expr = self.tc_function_expr.GetValue().strip()
        normalised_expr, _, parameter_names = self.parse_function_fit_template(expr)
        if not parameter_names:
            raise ValueError("No fit parameters found in f(x). Use names such as m, b, a, or c.")

        values = self.current_function_bound_values()
        missing = [name for name, value in values.items() if value is None]
        if missing:
            labels = ", ".join(name.replace("_", " ").upper() for name in missing)
            raise ValueError(f"Fit it needs all endpoint fields filled: {labels}.")
        if values["x_max"] <= values["x_min"]:
            raise ValueError("Function X max must be larger than X min.")

        x_points = np.asarray([values["x_min"], values["x_max"]], dtype=float)
        y_targets = np.asarray([values["y_min"], values["y_max"]], dtype=float)
        zero_parameters = {name: 0.0 for name in parameter_names}
        base = self.evaluate_function_fit_template(normalised_expr, x_points, zero_parameters)

        columns = []
        for name in parameter_names:
            trial = dict(zero_parameters)
            trial[name] = 1.0
            columns.append(self.evaluate_function_fit_template(normalised_expr, x_points, trial) - base)
        design = np.column_stack(columns)
        solution, _, rank, _ = np.linalg.lstsq(design, y_targets - base, rcond=None)
        fitted_parameters = {name: float(value) for name, value in zip(parameter_names, solution)}
        fitted_y = self.evaluate_function_fit_template(normalised_expr, x_points, fitted_parameters)

        tolerance = max(1e-7, 1e-6 * max(float(np.max(np.abs(y_targets))), 1.0))
        errors = fitted_y - y_targets
        if np.max(np.abs(errors)) > tolerance:
            raise ValueError(
                "The selected f(x) template cannot fit both endpoint points. "
                f"Endpoint errors: {errors[0]:.6g}, {errors[1]:.6g}."
            )

        fitted_expr = self.expression_with_fitted_parameters(normalised_expr, fitted_parameters)
        return fitted_expr, fitted_parameters, rank < len(parameter_names)

    def on_fit_function(self, event):
        started = time.monotonic()
        log_usage_event(self, "afm_function_fit_started")
        try:
            self.log("Fit it started for Function control endpoints.")
            wx.YieldIfNeeded()
            fitted_expr, fitted_parameters, underdetermined = self.fit_function_expression_to_bounds()
        except Exception as exc:
            log_usage_event(self, "afm_function_fit_failed", {"error": type(exc).__name__})
            self.show_warning(str(exc))
            return

        self.updating_function_fields = True
        try:
            self.tc_function_expr.SetValue(fitted_expr)
        finally:
            self.updating_function_fields = False

        parameter_text = ", ".join(f"{name}={value:.9g}" for name, value in fitted_parameters.items())
        if underdetermined:
            self.log(f"Fit it solved an underdetermined template using the minimum-norm solution: {parameter_text}")
        else:
            self.log(f"Fit it solved function parameters: {parameter_text}")
        self.update_preview()
        self.update_function_preview_plot()
        log_usage_event(
            self,
            "afm_function_fit_finished",
            {"duration_ms": int((time.monotonic() - started) * 1000), "underdetermined": underdetermined},
        )

    def on_parameterise_function(self, event):
        try:
            parameterised_expr, replacements = self.parameterise_function_expression(self.tc_function_expr.GetValue())
        except Exception as exc:
            self.show_warning(str(exc))
            return

        self.updating_function_fields = True
        try:
            self.tc_function_expr.SetValue(parameterised_expr)
        finally:
            self.updating_function_fields = False

        self.log(
            "Parameterise replaced numeric constants with independent parameters: "
            + ", ".join(replacements)
            + ". Equal numeric values are treated as separate parameters."
        )
        self.update_preview()
        self.update_function_preview_plot()
        self.show_warning(
            "Parameterise treats each numeric value as an independent parameter, "
            "even if two values are the same."
        )

    def solve_x_for_function_y(self, expr, target_y, search_min=0.0, search_max=10.0):
        if search_max <= search_min:
            raise ValueError("Function X search range must have X max greater than X min.")
        x = np.linspace(search_min, search_max, 3001)
        y = evaluate_user_function(expr, x)
        diff = y - target_y
        roots = []
        tolerance = max(1e-7, 1e-7 * max(abs(float(np.nanmax(y))), abs(float(np.nanmin(y))), abs(float(target_y)), 1.0))
        exact_indices = np.where(np.abs(diff) <= tolerance)[0]
        for idx in exact_indices:
            roots.append(float(x[idx]))
        for idx in range(len(x) - 1):
            d0 = float(diff[idx])
            d1 = float(diff[idx + 1])
            if not np.isfinite(d0) or not np.isfinite(d1):
                continue
            if d0 == 0.0:
                roots.append(float(x[idx]))
            elif d0 * d1 < 0:
                fraction = abs(d0) / (abs(d0) + abs(d1))
                roots.append(float(x[idx] + fraction * (x[idx + 1] - x[idx])))
        unique_roots = []
        for root in sorted(roots):
            if not unique_roots or abs(root - unique_roots[-1]) > 1e-4:
                unique_roots.append(root)
        if not unique_roots:
            raise ValueError(f"No x value in {search_min:.6g} to {search_max:.6g} gives y = {target_y:.6g}.")
        if len(unique_roots) > 1:
            raise ValueError(
                f"f(x) gives y = {target_y:.6g} at multiple x values. Enter the matching X value directly."
            )
        return unique_roots[0]

    def current_function_bound_values(self):
        values = {
            "x_min": self.parse_optional_float_from_ctrl(self.tc_function_xmin, "Function X min"),
            "x_max": self.parse_optional_float_from_ctrl(self.tc_function_xmax, "Function X max"),
            "y_min": self.parse_optional_float_from_ctrl(self.tc_function_ymin, "Function Y min"),
            "y_max": self.parse_optional_float_from_ctrl(self.tc_function_ymax, "Function Y max"),
        }
        for name, value in values.items():
            if value is not None and value < 0:
                label = name.replace("_", " ").upper()
                raise ValueError(f"Function {label} must not be below zero.")
        return values

    def set_function_bound_value(self, key, value):
        ctrl = self.function_bound_controls[key]
        self.updating_function_fields = True
        try:
            ctrl.SetValue(self.format_float_for_ctrl(value))
        finally:
            self.updating_function_fields = False

    def autofill_function_y_from_x(self, x_key):
        x_ctrl = self.function_bound_controls[x_key]
        if x_ctrl.GetValue().strip() == "":
            return
        try:
            expr = self.tc_function_expr.GetValue().strip()
            x_value = self.parse_optional_float_from_ctrl(x_ctrl, f"Function {x_key.replace('_', ' ')}")
            if x_value is None or x_value < 0:
                return
            y_value = float(evaluate_user_function(expr, [x_value])[0])
            if y_value < 0:
                return
        except Exception:
            return
        self.set_function_bound_value("y_min" if x_key == "x_min" else "y_max", y_value)

    def autofill_function_x_from_y(self, y_key):
        y_ctrl = self.function_bound_controls[y_key]
        if y_ctrl.GetValue().strip() == "":
            return
        try:
            expr = self.tc_function_expr.GetValue().strip()
            y_value = self.parse_optional_float_from_ctrl(y_ctrl, f"Function {y_key.replace('_', ' ')}")
            if y_value is None or y_value < 0:
                return
            x_value = self.solve_x_for_function_y(expr, y_value)
            if x_value < 0:
                return
        except Exception:
            return
        self.set_function_bound_value("x_min" if y_key == "y_min" else "x_max", x_value)

    def resolve_function_bounds(self, driver_keys=None):
        expr = self.tc_function_expr.GetValue().strip()
        if expr == "":
            raise ValueError("Function f(x) is empty.")
        try:
            _, _, parameter_names = self.parse_function_fit_template(expr)
        except Exception:
            parameter_names = []
        if parameter_names:
            raise ValueError(
                "f(x) contains fit parameter(s): "
                + ", ".join(parameter_names)
                + ". Fill X/Y min/max and press Fit it before previewing or running."
            )
        all_values = self.current_function_bound_values()
        if driver_keys:
            values = {key: (all_values[key] if key in driver_keys else None) for key in all_values}
        else:
            values = all_values.copy()

        provided = [key for key, value in values.items() if value is not None]
        if len(provided) < 2:
            raise ValueError("Enter at least two of X min, X max, Y min, and Y max for Function control.")

        if values["x_min"] is not None and values["y_min"] is not None:
            expected = float(evaluate_user_function(expr, [values["x_min"]])[0])
            if not np.isclose(expected, values["y_min"], rtol=1e-5, atol=1e-7):
                raise ValueError("Function Y min does not match f(X min).")
        if values["x_max"] is not None and values["y_max"] is not None:
            expected = float(evaluate_user_function(expr, [values["x_max"]])[0])
            if not np.isclose(expected, values["y_max"], rtol=1e-5, atol=1e-7):
                raise ValueError("Function Y max does not match f(X max).")

        if values["x_min"] is None and values["y_min"] is not None:
            values["x_min"] = self.solve_x_for_function_y(expr, values["y_min"])
        if values["x_max"] is None and values["y_max"] is not None:
            values["x_max"] = self.solve_x_for_function_y(expr, values["y_max"])
        if values["y_min"] is None and values["x_min"] is not None:
            values["y_min"] = float(evaluate_user_function(expr, [values["x_min"]])[0])
        if values["y_max"] is None and values["x_max"] is not None:
            values["y_max"] = float(evaluate_user_function(expr, [values["x_max"]])[0])

        missing = [key for key, value in values.items() if value is None]
        if missing:
            raise ValueError(
                "The selected Function control values only define one endpoint. Enter one value for the other endpoint."
            )
        if values["x_max"] <= values["x_min"]:
            raise ValueError("Function X max must be larger than X min.")
        return {
            "expr": expr,
            "x_min": values["x_min"],
            "x_max": values["x_max"],
            "y_min": values["y_min"],
            "y_max": values["y_max"],
        }

    def try_autofill_function_bounds(self, driver_keys=None):
        active_drivers = driver_keys or self.function_driver_fields
        if len(active_drivers) < 2:
            return
        try:
            resolved = self.resolve_function_bounds(driver_keys=active_drivers)
        except Exception:
            return
        self.updating_function_fields = True
        try:
            for key, ctrl in self.function_bound_controls.items():
                if key not in active_drivers:
                    ctrl.SetValue(self.format_float_for_ctrl(resolved[key]))
        finally:
            self.updating_function_fields = False

    def make_on_step(self, label, value, duration_s, source_mode, settings, run_context=None):
        calibration_model = run_context.get("calibration_model") if run_context else None
        current_ma = float(np.asarray(self.target_to_current_ma(value, source_mode, label, calibration_model=calibration_model)).item())
        self.validate_current_against_internal_max(current_ma, settings["internal_max_current_ma"], label)
        step = {
            "state": "ON",
            "duration_s": duration_s,
            "label": label,
            "source_mode": source_mode,
            "value": float(value),
            "source_current_mA": current_ma,
        }
        if source_mode == SOURCE_INTENSITY:
            step["target_intensity_mW"] = float(value)
        return step

    def read_function_settings(self, settings, source_mode, run_context=None):
        bounds = self.resolve_function_bounds()
        expr = bounds["expr"]
        x = np.linspace(bounds["x_min"], bounds["x_max"], FUNCTION_PROFILE_POINTS)
        y = evaluate_user_function(expr, x)
        calibration_model = run_context.get("calibration_model") if run_context else None
        current_profile = self.target_to_current_ma(y, source_mode, "Function control", calibration_model=calibration_model)
        self.validate_current_against_internal_max(current_profile, settings["internal_max_current_ma"], "Function control")
        return {
            "expr": expr,
            "x_min": bounds["x_min"],
            "x_max": bounds["x_max"],
            "y_min": bounds["y_min"],
            "y_max": bounds["y_max"],
            "x_profile": np.asarray(x, dtype=float).tolist(),
            "target_profile": np.asarray(y, dtype=float).tolist(),
            "current_profile_mA": np.asarray(current_profile, dtype=float).tolist(),
        }

    def make_function_on_step(self, label, duration_s, source_mode, function_settings, base_value=None):
        step = {
            "state": "ON_FUNCTION",
            "duration_s": duration_s,
            "label": label,
            "source_mode": source_mode,
            "expr": function_settings["expr"],
            "x_min": function_settings["x_min"],
            "x_max": function_settings["x_max"],
            "y_min": function_settings["y_min"],
            "y_max": function_settings["y_max"],
            "x_profile": list(function_settings["x_profile"]),
            "target_profile": list(function_settings["target_profile"]),
            "current_profile_mA": list(function_settings["current_profile_mA"]),
        }
        if base_value is not None:
            step["base_value"] = float(base_value)
        return step

    # ------------------------------------------------------------------
    # Sequence construction
    # ------------------------------------------------------------------
    def build_active_sequence(self, settings, run_context=None):
        source_mode = run_context.get("source_mode") if run_context else self.current_source_mode()
        pattern = self.current_control_pattern()
        if pattern == CONTROL_RECURRENT:
            return self.build_recurrent_sequence(settings, source_mode, run_context=run_context)
        if pattern == CONTROL_STEP:
            return self.build_step_sequence(settings, source_mode, run_context=run_context)
        raise ValueError("Please select a control pattern.")

    def build_recurrent_sequence(self, settings, source_mode, run_context=None):
        initial_off_time = self.parse_float_from_ctrl(self.tc_initial_off_time, "Initial OFF time", allow_zero=True, allow_negative=False)
        on_time = self.parse_float_from_ctrl(self.tc_recurrent_on_time, "Recurrent ON time", allow_zero=False, allow_negative=False)
        off_time = self.parse_float_from_ctrl(self.tc_recurrent_off_time, "Recurrent OFF time", allow_zero=False, allow_negative=False)
        times_text = self.tc_recurrent_times.GetValue().strip()
        if not times_text:
            raise ValueError("Recurrent times is empty.")
        try:
            recurrent_times = int(times_text)
        except ValueError:
            raise ValueError("Recurrent times must be an integer.")
        if recurrent_times <= 0:
            raise ValueError("Recurrent times must be > 0.")

        function_settings = self.read_function_settings(settings, source_mode, run_context=run_context) if self.function_control_enabled() else None
        on_value = None if function_settings is not None else self.parse_value_from_ctrl(self.tc_recurrent_on_value, "Recurrent ON value")
        sequence = []
        if initial_off_time > 0:
            sequence.append({"state": "OFF", "duration_s": initial_off_time, "label": "Initial OFF"})
        for n in range(1, recurrent_times + 1):
            if function_settings is not None:
                sequence.append(self.make_function_on_step(f"ON {n} f(x)", on_time, source_mode, function_settings))
            else:
                sequence.append(self.make_on_step(f"ON {n}", on_value, on_time, source_mode, settings, run_context=run_context))
            sequence.append({"state": "OFF", "duration_s": off_time, "label": f"OFF {n}"})
        return sequence

    def build_step_sequence(self, settings, source_mode, run_context=None):
        function_settings = self.read_function_settings(settings, source_mode, run_context=run_context) if self.function_control_enabled() else None
        sequence = []
        has_on_step = False
        for n in range(1, 7):
            if self.manual_off_checks[n].IsChecked():
                off_time = self.parse_float_from_ctrl(self.manual_off_times[n], f"{n} OFF time", allow_zero=False, allow_negative=False)
                sequence.append({"state": "OFF", "duration_s": off_time, "label": f"{n} OFF"})
            if self.manual_on_checks[n].IsChecked():
                has_on_step = True
                on_time = self.parse_float_from_ctrl(self.manual_on_times[n], f"{n} ON time", allow_zero=False, allow_negative=False)
                if function_settings is not None:
                    sequence.append(self.make_function_on_step(f"{n} ON f(x)", on_time, source_mode, function_settings))
                else:
                    on_value = self.parse_value_from_ctrl(self.manual_on_values[n], f"{n} ON value")
                    sequence.append(self.make_on_step(f"{n} ON", on_value, on_time, source_mode, settings, run_context=run_context))
        if self.manual_off_checks[7].IsChecked():
            off_time = self.parse_float_from_ctrl(self.manual_off_times[7], "7 OFF time", allow_zero=False, allow_negative=False)
            sequence.append({"state": "OFF", "duration_s": off_time, "label": "7 OFF"})
        if not sequence:
            raise ValueError("Step control has no checked OFF/ON steps.")
        if function_settings is not None and not has_on_step:
            raise ValueError("Function control needs at least one checked ON row in Step control.")
        return sequence

    # ------------------------------------------------------------------
    # Preview plots and source CSV
    # ------------------------------------------------------------------
    def update_preview(self, show_errors=False):
        if not hasattr(self, "ax_source"):
            return
        try:
            settings = self.read_global_settings()
            source_mode = self.current_source_mode()
            intensity_y = None
            if self.cb_quick_test.IsChecked():
                value = self.parse_value_from_ctrl(self.tc_quick_value, "Quick Test value")
                if source_mode == SOURCE_CURRENT:
                    current_ma = value
                else:
                    current_ma = float(np.asarray(self.target_to_current_ma(value, source_mode, "Quick Test")).item())
                self.validate_current_against_internal_max(current_ma, settings["internal_max_current_ma"], "Quick Test")
                if self.calibration_model is None:
                    t, y, ylabel, title = self.quick_test_plot_arrays(value, source_mode)
                else:
                    t, y, intensity_y, title = self.quick_test_dual_plot_arrays(value, source_mode, current_ma)
                    ylabel = "Source current / mA"
            else:
                sequence = self.build_active_sequence(settings)
                if self.calibration_model is None:
                    t, y, ylabel, title = self.sequence_to_plot_arrays(sequence, source_mode)
                else:
                    t, y, intensity_y, title = self.sequence_to_dual_plot_arrays(sequence)
                    ylabel = "Source current / mA"
        except Exception as exc:
            message = str(exc) if str(exc) else "No valid source profile to preview"
            self.clear_source_secondary_axis()
            self.ax_source.clear()
            self.ax_source.set_xlim(0, 1)
            self.ax_source.set_ylim(0, 1)
            self.ax_source.set_xlabel("Time / s")
            self.ax_source.set_ylabel("Source")
            self.ax_source.grid(True)
            self.ax_source.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
            self.figure_source.tight_layout(pad=1.6)
            self.canvas_source.draw()
            self.update_function_preview_plot()
            if show_errors:
                self.show_warning(message)
            return

        self.draw_source_profile(t, y, ylabel, title, intensity_y=intensity_y)
        self.update_function_preview_plot()

    def clear_source_secondary_axis(self):
        if getattr(self, "ax_source_intensity", None) is not None:
            try:
                self.ax_source_intensity.remove()
            except ValueError:
                pass
            self.ax_source_intensity = None

    @staticmethod
    def apply_axis_limits_from_values(axis, values):
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if len(arr) == 0:
            return
        y_min = float(np.nanmin(arr))
        y_max = float(np.nanmax(arr))
        ymax = max(abs(y_min), abs(y_max), 1.0)
        axis.set_ylim(y_min - 0.08 * ymax, y_max + 0.18 * ymax)

    def draw_source_profile(self, t, y, ylabel, title, intensity_y=None):
        self.clear_source_secondary_axis()
        self.ax_source.clear()
        if title.startswith("Function"):
            current_line = self.ax_source.plot(t, y, color="tab:blue", label="Current")[0]
        else:
            current_line = self.ax_source.step(t, y, where="post", color="tab:blue", label="Current")[0]
        self.ax_source.set_xlabel("Time / s")
        self.ax_source.set_ylabel(ylabel)
        self.ax_source.set_title(title)
        self.ax_source.grid(True)
        if len(t) > 0:
            self.ax_source.set_xlim(min(t), max(t) if max(t) > min(t) else min(t) + 1)
        if len(y) > 0:
            self.apply_axis_limits_from_values(self.ax_source, y)
        lines = [current_line]
        if intensity_y is not None:
            self.ax_source_intensity = self.ax_source.twinx()
            if title.startswith("Function"):
                intensity_line = self.ax_source_intensity.plot(
                    t,
                    intensity_y,
                    color="tab:orange",
                    label="Intensity",
                )[0]
            else:
                intensity_line = self.ax_source_intensity.step(
                    t,
                    intensity_y,
                    where="post",
                    color="tab:orange",
                    label="Intensity",
                )[0]
            self.ax_source_intensity.set_ylabel("Intensity / mW")
            self.apply_axis_limits_from_values(self.ax_source_intensity, intensity_y)
            lines.append(intensity_line)
        if intensity_y is not None:
            self.ax_source.legend(lines, [line.get_label() for line in lines], loc="best")
        self.figure_source.tight_layout(pad=1.6)
        self.canvas_source.draw()

    def quick_test_plot_arrays(self, value, source_mode):
        ylabel = "Source current / mA" if source_mode == SOURCE_CURRENT else "Target intensity / mW"
        title = "Quick Test constant source until OFF"
        return [0.0, QUICK_TEST_PREVIEW_TIME_S], [value, value], ylabel, title

    def quick_test_dual_plot_arrays(self, value, source_mode, current_ma):
        t = [0.0, QUICK_TEST_PREVIEW_TIME_S]
        if source_mode == SOURCE_INTENSITY:
            return t, [current_ma, current_ma], [value, value], "Quick Test constant source until OFF"
        intensity = self.calibration_model.predict_intensity([current_ma, current_ma])
        return t, [current_ma, current_ma], intensity.tolist(), "Quick Test constant source until OFF"

    def sequence_to_plot_arrays(self, sequence, source_mode):
        t = [0.0]
        y = [0.0]
        current_time = 0.0
        has_function = False
        for step in sequence:
            if step["state"] == "OFF":
                val = 0.0
                t.append(current_time)
                y.append(val)
                current_time += step["duration_s"]
                t.append(current_time)
                y.append(val)
                continue
            if step["state"] == "ON_FUNCTION":
                has_function = True
                x = np.linspace(step["x_min"], step["x_max"], FUNCTION_PROFILE_POINTS)
                val_profile = evaluate_user_function(step["expr"], x)
                normalized = np.linspace(0, 1, FUNCTION_PROFILE_POINTS)
                times = current_time + normalized * step["duration_s"]
                t.extend(times.tolist())
                y.extend(val_profile.tolist())
                current_time += step["duration_s"]
                continue
            else:
                val = step["value"] if source_mode == SOURCE_INTENSITY else step["source_current_mA"]
            t.append(current_time)
            y.append(val)
            current_time += step["duration_s"]
            t.append(current_time)
            y.append(val)
        ylabel = "Source current / mA" if source_mode == SOURCE_CURRENT else "Target intensity / mW"
        title = "Function-replaced source profile" if has_function else "Planned source profile"
        return t, y, ylabel, title

    def sequence_to_dual_plot_arrays(self, sequence):
        t = [0.0]
        current_y = [0.0]
        intensity_y = [0.0]
        current_time = 0.0
        has_function = False
        for step in sequence:
            if step["state"] == "OFF":
                for t_val in [current_time, current_time + step["duration_s"]]:
                    t.append(t_val)
                    current_y.append(0.0)
                    intensity_y.append(0.0)
                current_time += step["duration_s"]
                continue
            if step["state"] == "ON_FUNCTION":
                has_function = True
                x = np.linspace(step["x_min"], step["x_max"], FUNCTION_PROFILE_POINTS)
                function_profile = evaluate_user_function(step["expr"], x)
                normalized = np.linspace(0, 1, FUNCTION_PROFILE_POINTS)
                times = current_time + normalized * step["duration_s"]
                if step["source_mode"] == SOURCE_INTENSITY:
                    current_profile = self.target_to_current_ma(function_profile, SOURCE_INTENSITY, "Function control")
                    intensity_profile = function_profile
                else:
                    current_profile = function_profile
                    intensity_profile = self.calibration_model.predict_intensity(current_profile)
                t.extend(times.tolist())
                current_y.extend(np.asarray(current_profile, dtype=float).tolist())
                intensity_y.extend(np.asarray(intensity_profile, dtype=float).tolist())
                current_time += step["duration_s"]
                continue

            current_val = float(step["source_current_mA"])
            if step["source_mode"] == SOURCE_INTENSITY:
                intensity_val = float(step["target_intensity_mW"])
            else:
                intensity_val = float(np.asarray(self.calibration_model.predict_intensity([current_val])).item())
            t.append(current_time)
            current_y.append(current_val)
            intensity_y.append(intensity_val)
            current_time += step["duration_s"]
            t.append(current_time)
            current_y.append(current_val)
            intensity_y.append(intensity_val)
        title = "Function-replaced source profile" if has_function else "Planned source profile"
        return t, current_y, intensity_y, title

    def update_calibration_plot(self):
        if not hasattr(self, "ax_calibration"):
            return
        self.ax_calibration.clear()
        if self.calibration_model is None:
            self.ax_calibration.set_xlim(0, 1)
            self.ax_calibration.set_ylim(0, 1)
            message = "Loading intensity calibration..." if self.calibration_loading else "No intensity calibration loaded"
            self.ax_calibration.text(0.5, 0.5, message, ha="center", va="center")
            self.ax_calibration.set_xlabel("Current / mA")
            self.ax_calibration.set_ylabel("Intensity / mW")
            self.ax_calibration.grid(True)
            self.update_calibration_stats_labels(None)
        else:
            model = self.calibration_model
            curve_current, curve_intensity = model.curve_for_plot()
            self.ax_calibration.plot(model.current_mA, model.intensity_mW, "o", label="Raw data")
            self.ax_calibration.plot(curve_current, curve_intensity, label=f"Fit: {model.method}")
            self.ax_calibration.set_xlabel("Current / mA")
            self.ax_calibration.set_ylabel("Intensity / mW")
            self.ax_calibration.grid(True)
            self.ax_calibration.legend()
            self.update_calibration_stats_labels(model.stats())
        self.figure_calibration.tight_layout(pad=1.6)
        self.canvas_calibration.draw()
        self.Layout()
        self.Layout()

    def update_calibration_stats_labels(self, stats):
        if not hasattr(self, "calibration_stats_labels"):
            return
        if stats is None:
            values = [
                "R² = --",
                "RMSE = -- mW",
                "MAE = -- mW",
                "Max error = -- mW",
                "Current range = -- to -- mA",
                "Intensity range = -- to -- mW",
            ]
        else:
            values = [
                f"R² = {stats.r2:.6g}",
                f"RMSE = {stats.rmse_mw:.6g} mW",
                f"MAE = {stats.mae_mw:.6g} mW",
                f"Max error = {stats.max_error_mw:.6g} mW",
                f"Current range = {stats.current_min_ma:.6g} to {stats.current_max_ma:.6g} mA",
                f"Intensity range = {stats.intensity_min_mw:.6g} to {stats.intensity_max_mw:.6g} mW",
            ]
        for label, value in zip(self.calibration_stats_labels, values):
            label.SetLabel(value)
        if hasattr(self, "function_range_labels"):
            for label, value in zip(self.function_range_labels, values[-2:]):
                label.SetLabel(value)

    def update_function_preview_plot(self):
        if not hasattr(self, "ax_function"):
            return
        self.ax_function.clear()
        try:
            source_mode = self.current_source_mode()
            bounds = self.resolve_function_bounds()
            x = np.linspace(bounds["x_min"], bounds["x_max"], FUNCTION_PROFILE_POINTS)
            y = evaluate_user_function(bounds["expr"], x)
            self.ax_function.plot(x, y)
            self.ax_function.plot([bounds["x_min"], bounds["x_max"]], [bounds["y_min"], bounds["y_max"]], "o")
            self.ax_function.set_xlabel("x")
            self.ax_function.set_ylabel("Source current / mA" if source_mode == SOURCE_CURRENT else "Target intensity / mW")
            self.ax_function.set_title("Function profile")
            self.ax_function.grid(True)
            if len(x) > 0:
                self.ax_function.set_xlim(float(np.nanmin(x)), float(np.nanmax(x)))
            if len(y) > 0:
                ymax = max(abs(float(np.nanmin(y))), abs(float(np.nanmax(y))), 1.0)
                self.ax_function.set_ylim(float(np.nanmin(y)) - 0.08 * ymax, float(np.nanmax(y)) + 0.18 * ymax)
        except Exception as exc:
            message = str(exc) if str(exc) else "No valid function profile to preview"
            self.ax_function.set_xlim(0, 1)
            self.ax_function.set_ylim(0, 1)
            self.ax_function.set_xlabel("x")
            self.ax_function.set_ylabel("f(x)")
            self.ax_function.grid(True)
            self.ax_function.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
        self.figure_function.tight_layout(pad=1.6)
        self.canvas_function.draw()

    def on_load_calibration_csv(self, event):
        with wx.FileDialog(
            self,
            "Load current-intensity calibration CSV",
            wildcard="CSV files (*.csv)|*.csv|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        self.calibration_path = path
        metadata = file_metadata(path)
        if self.reload_calibration_model() and hasattr(self, "preview_notebook"):
            self.preview_notebook.SetSelection(2)
            log_usage_event(self, "afm_calibration_loaded", metadata)
        else:
            log_usage_event(self, "afm_calibration_load_failed", metadata)

    def on_fit_method_changed(self, event):
        if self.calibration_path:
            self.reload_calibration_model()

    def on_calibration_range_changed(self, event):
        if not self.initialising and self.calibration_path:
            if self.calibration_reload_timer is not None and self.calibration_reload_timer.IsRunning():
                self.calibration_reload_timer.Stop()
            self.calibration_reload_timer = wx.CallLater(800, self.delayed_reload_calibration_model)
        event.Skip()

    def delayed_reload_calibration_model(self):
        try:
            self.reload_calibration_model(show_errors=False)
        except TypeError:
            self.reload_calibration_model()

    def calibration_fit_progress(self, message):
        self.log(message)
        try:
            wx.YieldIfNeeded()
        except Exception:
            pass

    @staticmethod
    def build_calibration_model(path, method, x_min, x_max, progress_callback=None):
        current, intensity = load_intensity_csv(path)
        if x_min is not None and x_min < 0:
            raise ValueError("Calibration fit X min must not be below zero.")
        if x_max is not None and x_max < 0:
            raise ValueError("Calibration fit X max must not be below zero.")
        if x_min is not None or x_max is not None:
            lo = float(np.min(current)) if x_min is None else x_min
            hi = float(np.max(current)) if x_max is None else x_max
            if hi <= lo:
                raise ValueError("Calibration fit X max must be larger than X min.")
            mask = (current >= lo) & (current <= hi)
            if np.count_nonzero(mask) < 2:
                raise ValueError("Calibration fit range must include at least two calibration points.")
            current = current[mask]
            intensity = intensity[mask]
            if progress_callback is not None:
                progress_callback(f"Calibration fit range applied: {lo:.6g} to {hi:.6g} mA, {len(current)} points.")
        return LaserCalibrationModel(
            current,
            intensity,
            method=method,
            progress_callback=progress_callback if method in EMPIRICAL_CALIBRATION_METHODS else None,
        )

    def current_calibration_fit_range(self):
        return (
            self.parse_optional_float_from_ctrl(self.tc_calibration_xmin, "Calibration fit X min"),
            self.parse_optional_float_from_ctrl(self.tc_calibration_xmax, "Calibration fit X max"),
        )

    def build_calibration_model_from_path(self, path, method):
        x_min, x_max = self.current_calibration_fit_range()
        key = self.calibration_cache_key(path, method, x_min, x_max)
        if key in self.calibration_model_cache:
            self.log(f"Reused cached calibration fit: {os.path.basename(path)} using {method}.")
            return self.calibration_model_cache[key]
        model = self.build_calibration_model(
            path,
            method,
            x_min,
            x_max,
            progress_callback=self.calibration_fit_progress if method in EMPIRICAL_CALIBRATION_METHODS else None,
        )
        self.calibration_model_cache[key] = model
        return model

    @staticmethod
    def calibration_cache_key(path, method, x_min, x_max):
        stat = os.stat(path)
        normalized_range = (
            None if x_min is None else round(float(x_min), 12),
            None if x_max is None else round(float(x_max), 12),
        )
        return (
            os.path.abspath(path),
            stat.st_mtime_ns,
            stat.st_size,
            method,
            normalized_range,
        )

    def reload_calibration_model(self, show_errors=True):
        if not self.calibration_path:
            return False
        self.calibration_load_generation += 1
        self.calibration_loading = False
        method = self.fit_method_choice.GetStringSelection()
        try:
            self.calibration_model = self.build_calibration_model_from_path(self.calibration_path, method)
        except Exception as exc:
            self.calibration_model = None
            if show_errors:
                self.show_warning(f"Could not load or fit calibration CSV:\n{exc}")
            self.calibration_file_label.SetLabel("No calibration CSV loaded")
            self.update_calibration_plot()
            self.update_preview()
            return False
        self.calibration_file_label.SetLabel(os.path.basename(self.calibration_path))
        self.log(f"Loaded calibration CSV: {self.calibration_path} using {method}.")
        self.update_calibration_plot()
        self.update_preview()
        return True

    def load_default_calibration_if_available(self):
        package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_path = os.path.join(package_root, "resources", DEFAULT_CALIBRATION_FILENAME)
        if not os.path.exists(default_path):
            return
        self.calibration_path = default_path
        method = self.fit_method_choice.GetStringSelection()
        try:
            x_min, x_max = self.current_calibration_fit_range()
        except Exception as exc:
            self.calibration_model = None
            self.calibration_file_label.SetLabel("No calibration CSV loaded")
            self.log(f"Could not auto-load {DEFAULT_CALIBRATION_FILENAME}: {exc}")
            return
        self.start_background_calibration_load(default_path, method, x_min, x_max)

    def start_background_calibration_load(self, path, method, x_min, x_max):
        self.calibration_load_generation += 1
        generation = self.calibration_load_generation
        self.calibration_loading = True
        self.calibration_model = None
        self.calibration_file_label.SetLabel(f"Loading {os.path.basename(path)}...")
        self.log(f"Loading default calibration CSV in background: {path} using {method}.")
        cache_key = self.calibration_cache_key(path, method, x_min, x_max)
        cached_model = self.calibration_model_cache.get(cache_key)
        if cached_model is not None:
            wx.CallAfter(self.on_background_calibration_finished, generation, path, method, cached_model, None)
            return

        def progress(message):
            wx.CallAfter(self.log_background_calibration_progress, generation, message)

        def worker():
            try:
                model = self.build_calibration_model(path, method, x_min, x_max, progress_callback=progress)
                self.calibration_model_cache[cache_key] = model
            except Exception as exc:
                wx.CallAfter(self.on_background_calibration_finished, generation, path, method, None, exc)
                return
            wx.CallAfter(self.on_background_calibration_finished, generation, path, method, model, None)

        self.calibration_background_thread = threading.Thread(target=worker, daemon=True)
        self.calibration_background_thread.start()

    def log_background_calibration_progress(self, generation, message):
        if generation == self.calibration_load_generation:
            self.log(message)

    def on_background_calibration_finished(self, generation, path, method, model, error):
        if generation != self.calibration_load_generation:
            return
        if path != self.calibration_path or method != self.fit_method_choice.GetStringSelection():
            return
        self.calibration_loading = False
        if error is not None:
            self.calibration_model = None
            self.calibration_file_label.SetLabel("No calibration CSV loaded")
            self.log(f"Could not auto-load {DEFAULT_CALIBRATION_FILENAME}: {error}")
            self.update_calibration_plot()
            self.update_preview()
            return
        self.calibration_model = model
        self.calibration_file_label.SetLabel(os.path.basename(path))
        self.log(f"Auto-loaded calibration CSV: {path} using {method}.")
        self.update_calibration_plot()
        self.update_preview()

    def on_save_source_csv(self, event):
        if self.cb_quick_test.IsChecked():
            self.show_warning("Source CSV export is only for Function, Recurrent, or Step control. Quick Test is not saved as a source CSV.")
            return
        try:
            settings = self.read_global_settings()
            source_mode = self.current_source_mode()
            pattern = self.current_control_pattern()
            sequence = self.build_active_sequence(settings)
            rows = self.sequence_to_origin_source_rows(sequence, source_mode, pattern)
        except Exception as exc:
            self.show_warning(str(exc))
            return

        default_name = f"source_sequence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with wx.FileDialog(
            self,
            "Save source CSV",
            wildcard="CSV files (*.csv)|*.csv",
            defaultFile=default_name,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                if source_mode == SOURCE_CURRENT:
                    fieldnames = ["Time_s", "Source_Current_mA", "State", "Step_Label", "Step_Index"]
                else:
                    fieldnames = ["Time_s", "Target_Intensity_mW", "Required_Current_mA", "State", "Step_Label", "Step_Index"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:
            self.show_warning(f"Could not save source CSV:\n{exc}")
            return
        self.log(f"Saved Origin-friendly source CSV: {path}")
        log_usage_event(self, "afm_source_csv_saved", file_metadata(path))

    def sequence_to_origin_source_rows(self, sequence, source_mode, pattern):
        rows = []
        current_time = 0.0
        for step_index, step in enumerate(sequence, start=1):
            if step["state"] == "ON_FUNCTION":
                duration = step["duration_s"]
                x = np.linspace(step["x_min"], step["x_max"], FUNCTION_PROFILE_POINTS)
                normalized = np.linspace(0, 1, FUNCTION_PROFILE_POINTS)
                y = evaluate_user_function(step["expr"], x)
                current_ma = self.target_to_current_ma(y, source_mode, "Function control")
                times = current_time + normalized * duration
                for t_val, y_val, c_val in zip(times, y, current_ma):
                    if source_mode == SOURCE_CURRENT:
                        rows.append({
                            "Time_s": f"{t_val:.9g}",
                            "Source_Current_mA": f"{c_val:.9g}",
                            "State": "ON_FUNCTION",
                            "Step_Label": step["label"],
                            "Step_Index": step_index,
                        })
                    else:
                        rows.append({
                            "Time_s": f"{t_val:.9g}",
                            "Target_Intensity_mW": f"{y_val:.9g}",
                            "Required_Current_mA": f"{c_val:.9g}",
                            "State": "ON_FUNCTION",
                            "Step_Label": step["label"],
                            "Step_Index": step_index,
                        })
                current_time += duration
                continue

            if step["state"] == "OFF":
                current_ma = 0.0
                target_intensity = 0.0
            else:
                current_ma = step["source_current_mA"]
                target_intensity = step.get("target_intensity_mW", "")
            for t_val in [current_time, current_time + step["duration_s"]]:
                if source_mode == SOURCE_CURRENT:
                    rows.append({
                        "Time_s": f"{t_val:.9g}",
                        "Source_Current_mA": f"{current_ma:.9g}",
                        "State": step["state"],
                        "Step_Label": step["label"],
                        "Step_Index": step_index,
                    })
                else:
                    rows.append({
                        "Time_s": f"{t_val:.9g}",
                        "Target_Intensity_mW": f"{target_intensity if isinstance(target_intensity, str) else float(target_intensity):.9g}" if target_intensity != "" else "",
                        "Required_Current_mA": f"{current_ma:.9g}",
                        "State": step["state"],
                        "Step_Label": step["label"],
                        "Step_Index": step_index,
                    })
            current_time += step["duration_s"]
        return rows

    # ------------------------------------------------------------------
    # Save/load parameters
    # ------------------------------------------------------------------
    def collect_parameters(self):
        manual = []
        for n in range(1, 7):
            manual.append({
                "index": n,
                "off_use": self.manual_off_checks[n].IsChecked(),
                "off_time_s": self.manual_off_times[n].GetValue(),
                "on_use": self.manual_on_checks[n].IsChecked(),
                "on_value": self.manual_on_values[n].GetValue(),
                "on_time_s": self.manual_on_times[n].GetValue(),
            })
        manual.append({
            "index": 7,
            "off_use": self.manual_off_checks[7].IsChecked(),
            "off_time_s": self.manual_off_times[7].GetValue(),
        })
        return {
            "version": "v9_calibration_models",
            "com_port": self.tc_com_port.GetValue().strip() or DEFAULT_COM_PORT,
            "baudrate": int(self.choice_baudrate.GetStringSelection() or DEFAULT_BAUDRATE),
            "voltage_compliance_V": self.tc_compliance.GetValue(),
            "internal_max_current_mA": self.tc_internal_max_current.GetValue(),
            "source_mode": self.current_source_mode(),
            "calibration_path": self.calibration_path,
            "fit_method": self.fit_method_choice.GetStringSelection(),
            "calibration_fit_x_min_mA": self.tc_calibration_xmin.GetValue(),
            "calibration_fit_x_max_mA": self.tc_calibration_xmax.GetValue(),
            "quick_test": {
                "enabled": self.cb_quick_test.IsChecked(),
                "value": self.tc_quick_value.GetValue(),
            },
            "control_pattern": self.current_control_pattern() if (self.cb_recurrent_control.IsChecked() or self.cb_step_control.IsChecked()) else CONTROL_STEP,
            "function_control": {
                "enabled": self.cb_function_control.IsChecked(),
                "expr": self.tc_function_expr.GetValue(),
                "x_min": self.tc_function_xmin.GetValue(),
                "x_max": self.tc_function_xmax.GetValue(),
                "y_min": self.tc_function_ymin.GetValue(),
                "y_max": self.tc_function_ymax.GetValue(),
            },
            "recurrent_control": {
                "initial_off_time_s": self.tc_initial_off_time.GetValue(),
                "on_value": self.tc_recurrent_on_value.GetValue(),
                "on_time_s": self.tc_recurrent_on_time.GetValue(),
                "off_time_s": self.tc_recurrent_off_time.GetValue(),
                "times": self.tc_recurrent_times.GetValue(),
            },
            "step_control": manual,
        }

    def apply_parameters(self, params):
        if self.quick_running:
            self.stop_quick_test()
        if self.running:
            self.on_stop(None)
        self.initialising = True
        try:
            self.tc_com_port.SetValue(str(params.get("com_port", DEFAULT_COM_PORT)).strip() or DEFAULT_COM_PORT)
            baudrate = str(params.get("baudrate", DEFAULT_BAUDRATE))
            if self.choice_baudrate.FindString(baudrate) == wx.NOT_FOUND:
                baudrate = str(DEFAULT_BAUDRATE)
            self.choice_baudrate.SetStringSelection(baudrate)
            self.tc_compliance.SetValue(str(params.get("voltage_compliance_V", DEFAULT_COMPLIANCE_V)))
            self.tc_internal_max_current.SetValue(str(params.get("internal_max_current_mA", DEFAULT_INTERNAL_MAX_CURRENT_MA)))

            source_mode = params.get("source_mode", SOURCE_CURRENT)
            self.cb_current_mode.Enable()
            self.cb_intensity_mode.Enable()
            self.cb_current_mode.SetValue(source_mode == SOURCE_CURRENT)
            self.cb_intensity_mode.SetValue(source_mode == SOURCE_INTENSITY)
            self.calibration_path = params.get("calibration_path", "")
            fit_method = params.get("fit_method", "Interpolation")
            idx = self.fit_method_choice.FindString(fit_method)
            self.fit_method_choice.SetSelection(idx if idx != wx.NOT_FOUND else 0)
            self.tc_calibration_xmin.SetValue(str(params.get("calibration_fit_x_min_mA", DEFAULT_CALIBRATION_FIT_X_MIN_MA)))
            self.tc_calibration_xmax.SetValue(str(params.get("calibration_fit_x_max_mA", DEFAULT_CALIBRATION_FIT_X_MAX_MA)))

            quick = params.get("quick_test", {})
            self.cb_quick_test.SetValue(bool(quick.get("enabled", False)))
            self.tc_quick_value.SetValue(str(quick.get("value", "")))

            func = params.get("function_control", {})
            function_enabled = bool(func.get("enabled", False))
            self.tc_function_expr.SetValue(str(func.get("expr", DEFAULT_FUNCTION_EXPR)))
            self.tc_function_xmin.SetValue(str(func.get("x_min", DEFAULT_FUNCTION_X_MIN)))
            self.tc_function_xmax.SetValue(str(func.get("x_max", DEFAULT_FUNCTION_X_MAX)))
            self.tc_function_ymin.SetValue(str(func.get("y_min", DEFAULT_FUNCTION_Y_MIN)))
            self.tc_function_ymax.SetValue(str(func.get("y_max", DEFAULT_FUNCTION_Y_MAX)))
            self.try_autofill_function_bounds(["x_min", "x_max"])

            rec = params.get("recurrent_control", {})
            self.tc_initial_off_time.SetValue(str(rec.get("initial_off_time_s", "5")))
            self.tc_recurrent_on_value.SetValue(str(rec.get("on_value", "1")))
            self.tc_recurrent_on_time.SetValue(str(rec.get("on_time_s", "1")))
            self.tc_recurrent_off_time.SetValue(str(rec.get("off_time_s", "5")))
            self.tc_recurrent_times.SetValue(str(rec.get("times", "3")))

            for n in range(1, 8):
                self.manual_off_checks[n].SetValue(False)
                self.manual_off_times[n].SetValue("")
            for n in range(1, 7):
                self.manual_on_checks[n].SetValue(False)
                self.manual_on_values[n].SetValue("")
                self.manual_on_times[n].SetValue("")
            for item in params.get("step_control", []):
                n = int(item.get("index", 0))
                if 1 <= n <= 7:
                    self.manual_off_checks[n].SetValue(bool(item.get("off_use", False)))
                    self.manual_off_times[n].SetValue(str(item.get("off_time_s", "")))
                if 1 <= n <= 6:
                    self.manual_on_checks[n].SetValue(bool(item.get("on_use", False)))
                    self.manual_on_values[n].SetValue(str(item.get("on_value", "")))
                    self.manual_on_times[n].SetValue(str(item.get("on_time_s", "")))

            pattern = params.get("control_pattern", CONTROL_STEP)
            if pattern == CONTROL_FUNCTION:
                function_enabled = True
                pattern = CONTROL_STEP
            for cb in [self.cb_function_control, self.cb_recurrent_control, self.cb_step_control]:
                cb.Enable()
                cb.SetValue(False)
            self.cb_function_control.SetValue(function_enabled)
            self.cb_recurrent_control.SetValue(pattern == CONTROL_RECURRENT)
            self.cb_step_control.SetValue(pattern == CONTROL_STEP)
            if self.cb_function_control.IsChecked() and not (self.cb_recurrent_control.IsChecked() or self.cb_step_control.IsChecked()):
                self.cb_step_control.SetValue(True)
            if self.cb_function_control.IsChecked():
                self.cb_quick_test.SetValue(False)
        finally:
            self.initialising = False

        if self.calibration_path and os.path.exists(self.calibration_path):
            self.reload_calibration_model()
        else:
            self.calibration_model = None
            self.calibration_file_label.SetLabel("No calibration CSV loaded")
        self.update_quick_test_controls()
        self.update_source_mode_controls()
        self.update_control_pattern_controls()
        self.update_function_control_controls()
        self.update_step_row_enabled_state()
        self.update_preview()
        self.update_calibration_plot()

    def on_save_parameters(self, event):
        default_name = f"keithley_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with wx.FileDialog(self, "Save parameters", wildcard="JSON files (*.json)|*.json", defaultFile=default_name, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.collect_parameters(), f, indent=2)
        except Exception as exc:
            self.show_warning(f"Could not save parameters:\n{exc}")
            return
        self.log(f"Saved parameters: {path}")
        log_usage_event(self, "afm_controller_parameters_saved", file_metadata(path))

    def on_load_parameters(self, event):
        with wx.FileDialog(self, "Load parameters", wildcard="JSON files (*.json)|*.json", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            with open(path, "r", encoding="utf-8") as f:
                params = json.load(f)
            self.apply_parameters(params)
        except Exception as exc:
            self.show_warning(f"Could not load parameters:\n{exc}")
            return
        self.log(f"Loaded parameters: {path}")
        log_usage_event(self, "afm_controller_parameters_loaded", file_metadata(path))

    # ------------------------------------------------------------------
    # Keithley communication
    # ------------------------------------------------------------------
    @staticmethod
    def write_cmd(ser, command):
        if not command.endswith("\r"):
            command += "\r"
        ser.write(command.encode("ascii"))

    def configure_keithley(self, ser, compliance_v):
        self.write_cmd(ser, "*RST")
        time.sleep(0.2)
        self.write_cmd(ser, ":SOUR:FUNC CURR")
        self.write_cmd(ser, ":SOUR:CURR:MODE FIXED")
        self.write_cmd(ser, ':SENS:FUNC "VOLT"')
        self.write_cmd(ser, ":FORM:ELEM VOLT,CURR")
        self.write_cmd(ser, f":SENS:VOLT:PROT {compliance_v:.9g}")
        self.write_cmd(ser, ":SENS:VOLT:NPLC 0.1")

    def read_voltage_current(self, ser):
        if hasattr(ser, "reset_input_buffer"):
            ser.reset_input_buffer()
        self.write_cmd(ser, ":READ?")
        if hasattr(ser, "flush"):
            ser.flush()
        raw = ser.read_until(b"\r", 80)
        if not raw:
            raw = ser.read_until(b"\n", 80)
        if not raw:
            raise RuntimeError("No response from Keithley after :READ?.")
        text = raw.decode("ascii", errors="replace").strip()
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) < 2:
            raise RuntimeError(f"Could not parse Keithley response: {text!r}")
        voltage_v = float(parts[0])
        current_a = float(parts[1])
        return voltage_v, current_a

    def set_output_off(self):
        try:
            with self.serial_lock:
                if self.active_serial is not None and self.active_serial.is_open:
                    self.write_cmd(self.active_serial, ":OUTP OFF")
                    return
        except Exception as exc:
            self.log(f"Could not turn output off through active connection: {exc}")
        try:
            settings = self.read_global_settings()
            with serial.Serial(port=settings["com_port"], baudrate=settings["baudrate"], parity=serial.PARITY_NONE, bytesize=8, stopbits=1, timeout=SERIAL_TIMEOUT_S, xonxoff=False, rtscts=False, dsrdtr=False) as ser:
                self.write_cmd(ser, ":OUTP OFF")
        except Exception as exc:
            self.log(f"Could not open serial port to turn output off: {exc}")

    # ------------------------------------------------------------------
    # Quick Test
    # ------------------------------------------------------------------
    def on_quick_toggle(self, event):
        if not self.cb_quick_test.IsChecked():
            self.show_warning("Enable Quick Test first.")
            return
        if self.quick_running:
            self.stop_quick_test()
        else:
            self.start_quick_test()

    def start_quick_test(self):
        if self.running:
            self.show_warning("A sequence is already running.")
            return
        try:
            settings = self.read_global_settings()
            source_mode = self.current_source_mode()
            value = self.parse_value_from_ctrl(self.tc_quick_value, "Quick Test value")
            current_ma = float(np.asarray(self.target_to_current_ma(value, source_mode, "Quick Test")).item())
            self.validate_current_against_internal_max(current_ma, settings["internal_max_current_ma"], "Quick Test")
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.quick_stop_event.clear()
        self.quick_running = True
        self.live_voltage_times.clear()
        self.live_voltage_values.clear()
        self.live_source_current_times.clear()
        self.live_source_current_values.clear()
        self.live_start_time = time.time()
        self.update_quick_test_controls()
        self.update_preview()
        self.quick_thread = threading.Thread(target=self.quick_test_worker, args=(settings, current_ma, value, source_mode), daemon=True)
        self.quick_thread.start()
        log_usage_event(self, "afm_quick_test_started", {"source_mode": source_mode})

    def stop_quick_test(self):
        if not self.quick_running:
            return
        self.quick_stop_event.set()
        self.log("Quick Test stop requested. Sending output OFF.")
        self.set_output_off()

    def quick_test_worker(self, settings, current_ma, value, source_mode):
        try:
            ser = serial.Serial(port=settings["com_port"], baudrate=settings["baudrate"], parity=serial.PARITY_NONE, bytesize=8, stopbits=1, timeout=SERIAL_TIMEOUT_S, xonxoff=False, rtscts=False, dsrdtr=False)
            with self.serial_lock:
                self.active_serial = ser
            self.configure_keithley(ser, settings["compliance_v"])
            self.write_cmd(ser, f":SOUR:CURR:LEV {current_ma * 1e-3:.9g}")
            self.write_cmd(ser, ":OUTP ON")
            time.sleep(0.5)
            self.thread_log(f"Quick Test ON: requested {value:.6g} {'mA' if source_mode == SOURCE_CURRENT else 'mW'}, source current {current_ma:.6g} mA.")
            read_count = 0
            while not self.quick_stop_event.is_set():
                try:
                    voltage_v, current_a = self.read_voltage_current(ser)
                    read_count += 1
                    self.record_live_read(voltage_v, current_ma)
                    wx.CallAfter(self.tc_measured_voltage.SetValue, f"{voltage_v:.6g}")
                    wx.CallAfter(self.set_step_status, f"Quick Test ON | live read {read_count}")
                except Exception as exc:
                    self.thread_log(f"Quick Test measurement warning: {exc}")
                    time.sleep(0.1)
                time.sleep(0.25)
            self.write_cmd(ser, ":OUTP OFF")
            self.thread_log("Quick Test OFF sent.")
        except Exception as exc:
            self.thread_log(f"Quick Test ERROR: {exc}")
            try:
                with self.serial_lock:
                    if self.active_serial is not None and self.active_serial.is_open:
                        self.write_cmd(self.active_serial, ":OUTP OFF")
                        self.thread_log("Output OFF sent after Quick Test error.")
            except Exception as off_exc:
                self.thread_log(f"Could not send output OFF after Quick Test error: {off_exc}")
        finally:
            try:
                with self.serial_lock:
                    ser_to_close = self.active_serial
                if ser_to_close is not None and ser_to_close.is_open:
                    self.send_safety_output_off(ser_to_close)
                    ser_to_close.close()
                with self.serial_lock:
                    if self.active_serial is ser_to_close:
                        self.active_serial = None
            except Exception as cleanup_exc:
                self.thread_log(f"Cleanup error while closing serial connection: {cleanup_exc}")
            wx.CallAfter(self.on_quick_worker_finished)

    def on_quick_worker_finished(self):
        self.quick_running = False
        self.set_step_status("Quick Test OFF")
        self.update_quick_test_controls()
        self.update_preview()
        self.log("Quick Test ended.")
        log_usage_event(self, "afm_quick_test_finished")

    # ------------------------------------------------------------------
    # Sequence execution
    # ------------------------------------------------------------------
    def on_start(self, event):
        if self.cb_quick_test.IsChecked():
            self.show_warning("START is only for Function, Recurrent, or Step control. Use Quick Test ON/OFF for Quick Test.")
            return
        if self.running:
            self.show_warning("A sequence is already running.")
            return
        try:
            settings = self.read_global_settings()
            run_snapshot = self.build_run_snapshot(settings)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.update_preview()
        self.data_rows = []
        self.live_voltage_times.clear()
        self.live_voltage_values.clear()
        self.live_source_current_times.clear()
        self.live_source_current_values.clear()
        self.live_start_time = time.time()
        self.record_live_initial_zero()
        self.stop_event.clear()
        self.running = True
        self.btn_start.Disable()
        self.btn_save_source.Disable()
        self.btn_save_keithley.Disable()
        self.log("Starting sequence...")
        self.log(run_snapshot["lock_message"])
        log_usage_event(
            self,
            "afm_sequence_started",
            {"source_mode": run_snapshot.get("source_mode", ""), "pattern": run_snapshot.get("pattern", "")},
        )
        self.worker_thread = threading.Thread(target=self.run_sequence_worker, args=(run_snapshot,), daemon=True)
        self.worker_thread.start()

    def on_stop(self, event):
        self.stop_event.set()
        self.log("Stop requested. Sending output OFF.")
        log_usage_event(self, "afm_sequence_stop_clicked")
        self.set_output_off()

    def build_run_snapshot(self, settings):
        source_mode = self.current_source_mode()
        pattern = self.current_control_pattern()
        calibration_model = None
        calibration_method = ""
        calibration_path = ""
        fit_x_min = None
        fit_x_max = None
        if source_mode == SOURCE_INTENSITY:
            if not self.calibration_path:
                raise ValueError("Intensity mode requires a calibration CSV to be loaded first.")
            if self.calibration_loading:
                raise ValueError("Intensity mode requires the calibration fit to finish loading before START.")
            if self.calibration_model is None:
                raise ValueError("Intensity mode requires a completed calibration fit before START.")
            calibration_method = self.fit_method_choice.GetStringSelection()
            calibration_path = self.calibration_path
            calibration_model = self.calibration_model
            fit_x_min = self.parse_optional_float_from_ctrl(self.tc_calibration_xmin, "Calibration fit X min")
            fit_x_max = self.parse_optional_float_from_ctrl(self.tc_calibration_xmax, "Calibration fit X max")
        run_context = {
            "source_mode": source_mode,
            "pattern": pattern,
            "calibration_model": calibration_model,
            "calibration_method": calibration_method,
            "calibration_path": calibration_path,
            "fit_x_min_mA": fit_x_min,
            "fit_x_max_mA": fit_x_max,
        }
        sequence = self.build_active_sequence(settings, run_context=run_context)
        lock_message = self.format_run_lock_message(run_context)
        return {
            "settings": dict(settings),
            "sequence": sequence,
            "source_mode": source_mode,
            "pattern": pattern,
            "calibration_model": calibration_model,
            "calibration_method": calibration_method,
            "calibration_path": calibration_path,
            "fit_x_min_mA": fit_x_min,
            "fit_x_max_mA": fit_x_max,
            "lock_message": lock_message,
        }

    @staticmethod
    def format_run_lock_value(value):
        return "--" if value is None else f"{float(value):.6g}"

    def format_run_lock_message(self, run_context):
        if run_context["source_mode"] == SOURCE_INTENSITY:
            return (
                "Run locked: calibration method = "
                f"{run_context['calibration_method']}, fit range = "
                f"{self.format_run_lock_value(run_context['fit_x_min_mA'])} to "
                f"{self.format_run_lock_value(run_context['fit_x_max_mA'])} mA"
            )
        return "Run locked: source mode = Current, calibration conversion not used"

    def send_safety_output_off(self, ser):
        if ser is None:
            return
        try:
            self.write_cmd(ser, ":SOUR:CURR:LEV 0")
            self.write_cmd(ser, ":OUTP OFF")
            self.record_live_source_only(0.0)
            self.thread_log("Safety output OFF sent: source current set to 0 mA, output OFF.")
        except Exception as exc:
            self.thread_log(f"Could not send safety output OFF: {exc}")

    def run_sequence_worker(self, run_snapshot):
        settings = run_snapshot["settings"]
        sequence = run_snapshot["sequence"]
        start_time = time.time()
        finished_normally = False
        try:
            ser = serial.Serial(port=settings["com_port"], baudrate=settings["baudrate"], parity=serial.PARITY_NONE, bytesize=8, stopbits=1, timeout=SERIAL_TIMEOUT_S, xonxoff=False, rtscts=False, dsrdtr=False)
            with self.serial_lock:
                self.active_serial = ser
            self.configure_keithley(ser, settings["compliance_v"])
            self.thread_log(f"Keithley configured: current source, voltage compliance = {settings['compliance_v']} V.")
            self.thread_log(run_snapshot["lock_message"])

            for step in sequence:
                if self.stop_event.is_set():
                    break
                wx.CallAfter(self.set_step_status, step["label"])
                if step["state"] == "OFF":
                    self.write_cmd(ser, ":OUTP OFF")
                    self.thread_log(f"{step['label']}: output OFF for {step['duration_s']} s")
                    self.run_off_step_measurements(ser, step, start_time)
                elif step["state"] == "ON":
                    self.write_cmd(ser, f":SOUR:CURR:LEV {step['source_current_mA'] * 1e-3:.9g}")
                    self.write_cmd(ser, ":OUTP ON")
                    time.sleep(0.5)
                    self.thread_log(f"{step['label']}: source {step['source_current_mA']:.6g} mA for {step['duration_s']} s")
                    self.run_constant_on_step_measurements(ser, step, start_time)
                elif step["state"] == "ON_FUNCTION":
                    initial_x, initial_target, initial_current_ma = self.function_current_and_target_at_x(step, settings, 0.0)
                    self.write_cmd(ser, f":SOUR:CURR:LEV {initial_current_ma * 1e-3:.9g}")
                    self.write_cmd(ser, ":OUTP ON")
                    time.sleep(0.5)
                    self.thread_log(
                        f"{step['label']}: running f(x) for {step['duration_s']} s, "
                        f"initial source {initial_current_ma:.6g} mA."
                    )
                    self.run_function_on_step_measurements(ser, step, settings, start_time)

            if self.stop_event.is_set():
                self.thread_log("Sequence stopped by user. Safety output OFF will be sent during cleanup.")
            else:
                finished_normally = True
                self.thread_log("Sequence finished normally.")
        except Exception as exc:
            self.thread_log(f"ERROR: {exc}")
            self.thread_log("Safety output OFF will be sent during cleanup.")
        finally:
            try:
                with self.serial_lock:
                    ser_to_close = self.active_serial
                if ser_to_close is not None and ser_to_close.is_open:
                    self.send_safety_output_off(ser_to_close)
                    ser_to_close.close()
                with self.serial_lock:
                    if self.active_serial is ser_to_close:
                        self.active_serial = None
            except Exception as cleanup_exc:
                self.thread_log(f"Cleanup error while closing serial connection: {cleanup_exc}")
            wx.CallAfter(self.on_worker_finished, finished_normally)

    def run_off_step_measurements(self, ser, step, start_time):
        duration_s = step["duration_s"]
        self.add_data_row(start_time, step, 0.0, "", "", "Output OFF")
        self.run_off_live_updates(duration_s)

    def run_constant_on_step_measurements(self, ser, step, start_time):
        duration_s = step["duration_s"]
        step_start = time.time()
        read_count = 0
        while not self.stop_event.is_set():
            if time.time() - step_start >= duration_s:
                break
            try:
                voltage_v, current_a = self.read_voltage_current(ser)
                read_count += 1
                self.record_live_read(voltage_v, step["source_current_mA"])
                current_ma_measured = current_a * 1e3
                self.add_data_row(start_time, step, step["source_current_mA"], voltage_v, current_ma_measured, f"Live read {read_count} during ON")
                wx.CallAfter(self.tc_measured_voltage.SetValue, f"{voltage_v:.6g}")
                wx.CallAfter(self.set_step_status, f"{step['label']} | live read {read_count}")
            except Exception as exc:
                self.thread_log(f"Measurement warning in {step['label']}: {exc}")
                time.sleep(0.1)
            time.sleep(0.25)

    def function_current_and_target_at_x(self, step, settings, progress):
        x = step["x_min"] + progress * (step["x_max"] - step["x_min"])
        x_profile = np.asarray(step["x_profile"], dtype=float)
        target_profile = np.asarray(step["target_profile"], dtype=float)
        current_profile = np.asarray(step["current_profile_mA"], dtype=float)
        y = float(np.interp(x, x_profile, target_profile))
        current_ma = float(np.interp(x, x_profile, current_profile))
        self.validate_current_against_internal_max(current_ma, settings["internal_max_current_ma"], "Function control")
        return x, y, current_ma

    def run_function_on_step_measurements(self, ser, step, settings, start_time):
        duration_s = step["duration_s"]
        source_mode = step["source_mode"]
        step_start = time.time()
        read_count = 0
        last_set_time = 0.0
        while not self.stop_event.is_set():
            elapsed = time.time() - step_start
            if elapsed >= duration_s:
                break
            progress = min(max(elapsed / duration_s, 0.0), 1.0)
            try:
                x, y, current_ma = self.function_current_and_target_at_x(step, settings, progress)
                now = time.time()
                if now - last_set_time >= FUNCTION_EXEC_MIN_INTERVAL_S:
                    self.write_cmd(ser, f":SOUR:CURR:LEV {current_ma * 1e-3:.9g}")
                    last_set_time = now
                voltage_v, current_a = self.read_voltage_current(ser)
                read_count += 1
                self.record_live_read(voltage_v, current_ma)
                current_ma_measured = current_a * 1e3
                target_intensity = y if source_mode == SOURCE_INTENSITY else None
                self.add_data_row(
                    start_time,
                    step,
                    current_ma,
                    voltage_v,
                    current_ma_measured,
                    f"f(x) read {read_count}, x={x:.6g}, y={y:.6g}",
                    target_intensity_mw=target_intensity,
                )
                wx.CallAfter(self.tc_measured_voltage.SetValue, f"{voltage_v:.6g}")
                wx.CallAfter(self.set_step_status, f"Function | x={x:.3f} | live read {read_count}")
            except Exception as exc:
                self.thread_log(f"Function control measurement warning: {exc}")
                time.sleep(0.1)
            time.sleep(0.25)

    def interruptible_sleep(self, duration_s):
        end_time = time.time() + duration_s
        while time.time() < end_time:
            if self.stop_event.is_set():
                return
            time.sleep(0.05)

    def run_off_live_updates(self, duration_s):
        end_time = time.time() + duration_s
        self.record_live_read(0.0, 0.0)
        while not self.stop_event.is_set():
            remaining_s = end_time - time.time()
            if remaining_s <= 0:
                break
            time.sleep(min(0.25, remaining_s))
            if not self.stop_event.is_set():
                self.record_live_read(0.0, 0.0)

    def current_live_time(self):
        if self.live_start_time is None:
            self.live_start_time = time.time()
        return time.time() - self.live_start_time

    def trim_live_current_points(self):
        if len(self.live_source_current_times) > 2000:
            self.live_source_current_times = self.live_source_current_times[-2000:]
            self.live_source_current_values = self.live_source_current_values[-2000:]

    def record_live_initial_zero(self):
        self.live_voltage_times.append(0.0)
        self.live_voltage_values.append(0.0)
        self.live_source_current_times.append(0.0)
        self.live_source_current_values.append(0.0)
        self.update_live_voltage_plot()

    def record_live_read(self, voltage_v, source_current_ma):
        t = self.current_live_time()
        self.live_voltage_times.append(t)
        self.live_voltage_values.append(float(voltage_v))
        self.live_source_current_times.append(t)
        self.live_source_current_values.append(float(source_current_ma))
        if len(self.live_voltage_times) > 2000:
            self.live_voltage_times = self.live_voltage_times[-2000:]
            self.live_voltage_values = self.live_voltage_values[-2000:]
        self.trim_live_current_points()
        wx.CallAfter(self.update_live_voltage_plot)

    def record_live_source_only(self, source_current_ma):
        t = self.current_live_time()
        self.live_source_current_times.append(t)
        self.live_source_current_values.append(float(source_current_ma))
        self.trim_live_current_points()
        wx.CallAfter(self.update_live_voltage_plot)

    def clear_live_secondary_axis(self):
        if getattr(self, "ax_live_current", None) is not None:
            try:
                self.ax_live_current.remove()
            except ValueError:
                pass
            self.ax_live_current = None

    def update_live_voltage_plot(self):
        if not hasattr(self, "ax_live"):
            return
        self.clear_live_secondary_axis()
        self.ax_live.clear()
        lines = []
        all_times = []
        if self.live_voltage_times:
            voltage_line = self.ax_live.plot(
                self.live_voltage_times,
                self.live_voltage_values,
                color="tab:blue",
                label="Measured voltage",
            )[0]
            lines.append(voltage_line)
            all_times.extend(self.live_voltage_times)
            self.apply_axis_limits_from_values(self.ax_live, self.live_voltage_values)
        if self.live_source_current_times:
            self.ax_live_current = self.ax_live.twinx()
            current_line = self.ax_live_current.plot(
                self.live_source_current_times,
                self.live_source_current_values,
                color="tab:orange",
                label="Source current",
            )[0]
            self.ax_live_current.set_ylabel("Source current / mA")
            self.apply_axis_limits_from_values(self.ax_live_current, self.live_source_current_values)
            lines.append(current_line)
            all_times.extend(self.live_source_current_times)
        if not lines:
            self.ax_live.text(0.5, 0.5, "No live voltage data yet", ha="center", va="center")
        else:
            self.ax_live.legend(lines, [line.get_label() for line in lines], loc="best")
        self.ax_live.set_xlabel("Time / s")
        self.ax_live.set_ylabel("Measured voltage / V")
        self.ax_live.grid(True)
        if all_times:
            x_min = min(all_times)
            x_max = max(all_times)
            self.ax_live.set_xlim(x_min, x_max if x_max > x_min else x_min + 1.0)
        self.figure_live.tight_layout(pad=1.6)
        self.canvas_live.draw()

    def set_step_status(self, text):
        self.step_status_text = str(text)

    def add_data_row(self, start_time, step, source_current_ma, measured_voltage_v, measured_current_ma, note, target_intensity_mw=None):
        row = {
            "Time_s": f"{time.time() - start_time:.9g}",
            "Source_Current_mA": f"{source_current_ma:.9g}" if isinstance(source_current_ma, (int, float, np.floating)) else source_current_ma,
            "Measured_Voltage_V": f"{measured_voltage_v:.9g}" if isinstance(measured_voltage_v, (int, float, np.floating)) else measured_voltage_v,
            "Measured_Current_mA": f"{measured_current_ma:.9g}" if isinstance(measured_current_ma, (int, float, np.floating)) else measured_current_ma,
            "Step_Label": step["label"],
            "State": step["state"],
            "Step_Duration_s": f"{step['duration_s']:.9g}",
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
            "Note": note,
        }
        if step.get("source_mode") == SOURCE_INTENSITY:
            if target_intensity_mw is not None:
                row["Target_Intensity_mW"] = f"{target_intensity_mw:.9g}"
            else:
                row["Target_Intensity_mW"] = step.get("target_intensity_mW", "")
        self.data_rows.append(row)

    def update_save_keithley_controls(self):
        if hasattr(self, "btn_save_keithley"):
            can_save = bool(self.data_rows) and not self.running and not self.quick_running and not self.cb_quick_test.IsChecked()
            self.btn_save_keithley.Enable(can_save)

    def on_save_keithley_csv(self, event):
        if not self.data_rows:
            self.show_warning("No Keithley run data is available to save.")
            return
        filename = f"keithley_run_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with wx.FileDialog(
            self,
            "Save Keithley run data CSV",
            wildcard="CSV files (*.csv)|*.csv",
            defaultFile=filename,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        self.save_run_data_csv(path)

    def save_run_data_csv(self, path):
        try:
            # Include all keys that appear in the run data.
            fieldnames = []
            for row in self.data_rows:
                for key in row.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.data_rows)
            self.log(f"Saved Keithley run data CSV: {path}")
            log_usage_event(self, "afm_keithley_csv_saved", file_metadata(path))
        except OSError as exc:
            self.show_warning(f"Could not save Keithley run data CSV:\n{exc}")

    def on_worker_finished(self, finished_normally):
        self.running = False
        self.btn_start.Enable(not self.cb_quick_test.IsChecked())
        self.btn_save_source.Enable(not self.cb_quick_test.IsChecked())
        self.btn_stop.Enable(not self.cb_quick_test.IsChecked())
        self.update_quick_test_controls()
        self.update_source_mode_controls()
        self.update_control_pattern_controls()
        self.update_save_keithley_controls()
        if finished_normally:
            self.log("Worker finished.")
            log_usage_event(self, "afm_sequence_finished", {"finished_normally": True})
        else:
            self.log("Worker ended after stop or error.")
            log_usage_event(self, "afm_sequence_finished", {"finished_normally": False})

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def thread_log(self, message):
        wx.CallAfter(self.log, message)

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.AppendText(f"[{stamp}] {message}\n")
















