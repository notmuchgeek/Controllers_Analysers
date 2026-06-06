"""TPC laser-diode control panel."""

from __future__ import annotations

import threading
from datetime import datetime

import wx

from ca_app.constants import DEFAULT_BAUDRATE, DEFAULT_COM_PORT
from ca_app.core.tpc_laser_diode import (
    DEFAULT_TPC_SETTING_CURRENT_MA,
    GREEN_LD,
    RED_LD,
    clamp_current_to_limit,
    optical_power_from_current_mA,
    parse_requested_current_mA,
    resolve_laser_diode_selection,
)
BAUDRATE_CHOICES = ("9600", "19200", "38400", "57600")

from ca_app.hardware.tpc_keithley import (
    configure_tpc_current_source,
    open_tpc_serial,
    output_off,
    output_on_and_read,
    set_tpc_source_current_mA,
)
from ca_app.runtime.usage_logger import log_usage_event


class TpcLaserDiodePanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.worker_thread = None
        self.command_running = False
        self.output_is_on = False
        self.build_ui()

    def build_ui(self):
        root = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(self, label="TPC Laser Diode Power Control")
        title_font = title.GetFont()
        title_font.SetPointSize(title_font.GetPointSize() + 6)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        root.Add(title, 0, wx.ALL, 12)

        content = wx.BoxSizer(wx.HORIZONTAL)
        content.Add(self.build_controls(), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        content.Add(self.build_status(), 1, wx.EXPAND | wx.RIGHT | wx.BOTTOM, 12)
        root.Add(content, 1, wx.EXPAND)

        self.SetSizer(root)

    def build_controls(self):
        box = wx.StaticBoxSizer(wx.VERTICAL, self, "Laser diode control")

        message = wx.StaticText(
            self,
            label="Select LD - Red or Green\nRED LD current limit: 33 mA\nGreen LD current limit: 48 mA",
        )
        message.SetForegroundColour(wx.Colour(180, 0, 180))
        box.Add(message, 0, wx.EXPAND | wx.ALL, 8)

        selection_row = wx.BoxSizer(wx.HORIZONTAL)
        self.green_ld = wx.CheckBox(self, label="GREEN_LD")
        self.red_ld = wx.CheckBox(self, label="RED_LD")
        self.green_ld.SetForegroundColour(wx.GREEN)
        self.red_ld.SetForegroundColour(wx.RED)
        self.green_ld.Bind(wx.EVT_CHECKBOX, self.on_green_checked)
        self.red_ld.Bind(wx.EVT_CHECKBOX, self.on_red_checked)
        selection_row.Add(self.green_ld, 0, wx.RIGHT, 16)
        selection_row.Add(self.red_ld, 0)
        box.Add(selection_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        grid = wx.FlexGridSizer(rows=6, cols=3, vgap=8, hgap=6)
        grid.AddGrowableCol(1, 1)
        self.tc_com_port = wx.TextCtrl(self, value=DEFAULT_COM_PORT, size=(120, -1))
        self.choice_baudrate = wx.Choice(self, choices=list(BAUDRATE_CHOICES), size=(120, -1))
        self.choice_baudrate.SetStringSelection(str(DEFAULT_BAUDRATE))
        self.tc_setting_current = wx.TextCtrl(self, value=DEFAULT_TPC_SETTING_CURRENT_MA, size=(120, -1))
        self.tc_applied_voltage = wx.TextCtrl(self, style=wx.TE_READONLY, size=(120, -1))
        self.tc_applied_current = wx.TextCtrl(self, style=wx.TE_READONLY, size=(120, -1))
        self.tc_output_power = wx.TextCtrl(self, style=wx.TE_READONLY, size=(120, -1))

        self.add_labeled_row(grid, "COM port", self.tc_com_port, "")
        self.add_labeled_row(grid, "Baudrate", self.choice_baudrate, "")
        self.add_labeled_row(grid, "Setting_Current", self.tc_setting_current, "mA")
        self.add_labeled_row(grid, "Applied_Voltage", self.tc_applied_voltage, "V")
        self.add_labeled_row(grid, "Applied_Current", self.tc_applied_current, "mA")
        self.add_labeled_row(grid, "LD_Output_Power", self.tc_output_power, "W")
        box.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_on = wx.Button(self, label="ON", size=(130, 58))
        self.btn_off = wx.Button(self, label="OFF", size=(130, 58))
        self.btn_on.SetBackgroundColour(wx.GREEN)
        self.btn_off.SetBackgroundColour(wx.RED)
        self.btn_on.Bind(wx.EVT_BUTTON, self.on_ld_on)
        self.btn_off.Bind(wx.EVT_BUTTON, self.on_ld_off)
        button_row.Add(self.btn_on, 0, wx.RIGHT, 12)
        button_row.Add(self.btn_off, 0)
        box.Add(button_row, 0, wx.ALL, 8)

        return box

    def build_status(self):
        box = wx.StaticBoxSizer(wx.VERTICAL, self, "TPC status / log")
        self.log_box = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        box.Add(self.log_box, 1, wx.EXPAND | wx.ALL, 8)
        return box

    def add_labeled_row(self, grid, label, ctrl, unit):
        grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(self, label=unit), 0, wx.ALIGN_CENTER_VERTICAL)

    def on_green_checked(self, event):
        if self.green_ld.IsChecked():
            self.red_ld.SetValue(False)
        event.Skip()

    def on_red_checked(self, event):
        if self.red_ld.IsChecked():
            self.green_ld.SetValue(False)
        event.Skip()

    def read_com_port(self):
        com_port = self.tc_com_port.GetValue().strip()
        if not com_port:
            raise ValueError("COM port must not be empty.")
        return com_port

    def read_baudrate(self):
        baudrate_text = self.choice_baudrate.GetStringSelection() or str(DEFAULT_BAUDRATE)
        try:
            return int(baudrate_text)
        except ValueError as exc:
            raise ValueError("Baudrate must be one of 9600, 19200, 38400, or 57600.") from exc

    def current_selection(self):
        selection = resolve_laser_diode_selection(self.green_ld.IsChecked(), self.red_ld.IsChecked())
        if selection.name == RED_LD:
            self.red_ld.SetValue(True)
            self.green_ld.SetValue(False)
        elif selection.name == GREEN_LD:
            self.green_ld.SetValue(True)
            self.red_ld.SetValue(False)
        return selection

    def on_ld_on(self, event):
        if self.command_running:
            self.show_warning("A TPC hardware command is already running.")
            return
        try:
            selection = self.current_selection()
            requested_mA = parse_requested_current_mA(self.tc_setting_current.GetValue())
            current_request = clamp_current_to_limit(requested_mA, selection.current_limit_mA)
            com_port = self.read_com_port()
            baudrate = self.read_baudrate()
        except ValueError as exc:
            self.show_warning(str(exc))
            return

        self.command_running = True
        self.update_buttons()
        self.clear_measurements()
        self.log_selection(selection, current_request)
        log_usage_event(self, "tpc_output_on_clicked", {"laser": selection.name, "clamped": current_request.clamped})
        self.worker_thread = threading.Thread(
            target=self.ld_on_worker,
            args=(selection.name, current_request.command_mA, current_request.clamped, com_port, baudrate),
            daemon=True,
        )
        self.worker_thread.start()

    def ld_on_worker(self, ld_name, command_mA, clamped, com_port, baudrate):
        try:
            with open_tpc_serial(com_port, baudrate) as ser:
                configure_tpc_current_source(ser)
                set_tpc_source_current_mA(ser, command_mA)
                voltage_v, current_a = output_on_and_read(ser)
            measured_current_mA = current_a * 1e3
            optical_power = optical_power_from_current_mA(ld_name, measured_current_mA)
            wx.CallAfter(self.on_ld_on_result, voltage_v, measured_current_mA, optical_power, clamped)
        except Exception as exc:
            wx.CallAfter(self.on_worker_error, f"TPC LD ON failed: {exc}")

    def on_ld_on_result(self, voltage_v, current_mA, optical_power, clamped):
        self.output_is_on = True
        self.command_running = False
        self.tc_applied_voltage.SetValue(f"{voltage_v:.2f}")
        self.tc_applied_current.SetForegroundColour(wx.RED if clamped else wx.BLACK)
        self.tc_applied_current.SetValue(f"{current_mA:.2f}")
        self.tc_output_power.SetValue(f"{optical_power:.2f}")
        self.log("TPC LD output ON. Readback completed.")
        log_usage_event(self, "tpc_output_on_finished", {"clamped": clamped})
        self.update_buttons()

    def on_ld_off(self, event):
        if self.command_running:
            self.show_warning("Wait for the current TPC hardware command to finish before sending OFF.")
            return
        self.command_running = True
        self.update_buttons()
        try:
            com_port = self.read_com_port()
            baudrate = self.read_baudrate()
        except ValueError as exc:
            self.command_running = False
            self.update_buttons()
            self.show_warning(str(exc))
            return
        log_usage_event(self, "tpc_output_off_clicked")
        self.worker_thread = threading.Thread(target=self.ld_off_worker, args=(com_port, baudrate), daemon=True)
        self.worker_thread.start()

    def ld_off_worker(self, com_port, baudrate):
        try:
            output_off(com_port, baudrate)
            wx.CallAfter(self.on_ld_off_result)
        except Exception as exc:
            wx.CallAfter(self.on_worker_error, f"TPC LD OFF failed: {exc}")

    def on_ld_off_result(self):
        self.output_is_on = False
        self.command_running = False
        self.log("TPC LD output OFF sent.")
        log_usage_event(self, "tpc_output_off_finished")
        self.update_buttons()

    def on_worker_error(self, message):
        self.command_running = False
        self.log(message)
        log_usage_event(self, "tpc_hardware_command_failed")
        self.show_warning(message)
        self.update_buttons()

    def update_buttons(self):
        self.btn_on.Enable(not self.command_running)
        self.btn_off.Enable(not self.command_running)

    def clear_measurements(self):
        self.tc_applied_voltage.SetValue("")
        self.tc_applied_current.SetForegroundColour(wx.BLACK)
        self.tc_applied_current.SetValue("")
        self.tc_output_power.SetValue("")

    def collect_app_parameters(self):
        return {
            "green_ld": self.green_ld.IsChecked(),
            "red_ld": self.red_ld.IsChecked(),
            "com_port": self.tc_com_port.GetValue(),
            "baudrate": self.choice_baudrate.GetStringSelection(),
            "setting_current_mA": self.tc_setting_current.GetValue(),
        }

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        self.green_ld.SetValue(bool(params.get("green_ld", False)))
        self.red_ld.SetValue(bool(params.get("red_ld", False)))
        if self.green_ld.IsChecked() and self.red_ld.IsChecked():
            self.red_ld.SetValue(False)
        self.tc_com_port.SetValue(str(params.get("com_port", DEFAULT_COM_PORT)).strip() or DEFAULT_COM_PORT)
        baudrate = str(params.get("baudrate", DEFAULT_BAUDRATE))
        if self.choice_baudrate.FindString(baudrate) == wx.NOT_FOUND:
            baudrate = str(DEFAULT_BAUDRATE)
        self.choice_baudrate.SetStringSelection(baudrate)
        self.tc_setting_current.SetValue(str(params.get("setting_current_mA", DEFAULT_TPC_SETTING_CURRENT_MA)))
        self.output_is_on = False
        self.command_running = False
        self.clear_measurements()
        self.update_buttons()

    def log_selection(self, selection, current_request):
        if selection.used_default_red:
            self.log("No single LD was selected. RED Laser is used by default.")
        else:
            self.log(f"{selection.name.upper()} Laser selected.")
        if current_request.clamped:
            self.log(
                f"Requested {current_request.requested_mA:.6g} mA exceeds {selection.name} LD limit "
                f"of {selection.current_limit_mA:.6g} mA. Command is clamped to {current_request.command_mA:.6g} mA."
            )
        else:
            self.log(f"Commanding {current_request.command_mA:.6g} mA.")

    def show_warning(self, message):
        wx.MessageBox(message, "TPC warning", wx.OK | wx.ICON_WARNING, self)

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.AppendText(f"[{stamp}] {message}\n")







