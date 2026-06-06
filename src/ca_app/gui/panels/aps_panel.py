"""APS analysis workspace panel."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

from ca_app.core.aps_analysis import (
    ApsAnalysisError,
    ApsFitSettings,
    DosSmoothSettings,
    DwfSettings,
    SpvSettings,
    analyze_aps_files,
    analyze_spv_files,
    analyze_with_settings,
    analyze_workfunction,
    analyze_workfunction_ref_aps,
    build_spv_timemap,
    dwf_preview_percent_from_slider,
    import_aps_files,
    import_dwf_files,
    import_spv_files,
    save_aps_csv,
    save_aps_fit_csv,
    save_dos_csv,
    save_dwf_csv,
    save_dwf_stat_csv,
    save_homo_error_csv,
    save_normalized_spv_csv,
    save_spv_csv,
)
from ca_app.runtime.usage_logger import file_metadata, log_usage_event


class ApsAnalysisPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.dwf_paths: list[str] = []
        self.ref_aps_path = ""
        self.ref_dwf_path = ""
        self.aps_paths: list[str] = []
        self.spv_paths: list[str] = []
        self.workfunction_result = None
        self.aps_result = None
        self.spv_result = None
        self.preview_timer = None
        self.analysis_running = False
        self.ref_aps_fit_domain = "energy"
        self.aps_fit_domain = "energy"
        self.setting_fit_fields = False
        self.build_ui()
        self.Bind(wx.EVT_SIZE, self.on_size)

    def build_ui(self):
        root = wx.BoxSizer(wx.HORIZONTAL)
        left = self.build_left_panel()
        right = self.build_right_panel()
        root.Add(left, 0, wx.EXPAND | wx.ALL, 8)
        root.Add(right, 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(root)

    def build_left_panel(self):
        scrolled = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scrolled.SetScrollRate(0, 20)
        scrolled.SetMinSize((520, -1))
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.build_workfunction_controls(scrolled), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.build_aps_controls(scrolled), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.build_spv_controls(scrolled), 0, wx.EXPAND | wx.ALL, 5)
        scrolled.SetSizer(sizer)
        return scrolled

    def build_workfunction_controls(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "Workfunction Analysis")

        self.btn_load_dwf = wx.Button(parent, label="Load DWF files")
        self.btn_load_ref_aps = wx.Button(parent, label="Load reference APS")
        self.btn_load_ref_dwf = wx.Button(parent, label="Load reference DWF")
        self.lbl_dwf = wx.StaticText(parent, label="No DWF files loaded")
        self.lbl_ref_aps = wx.StaticText(parent, label="No reference APS loaded")
        self.lbl_ref_dwf = wx.StaticText(parent, label="No reference DWF loaded")

        for button, handler in [
            (self.btn_load_dwf, self.on_load_dwf),
            (self.btn_load_ref_aps, self.on_load_ref_aps),
            (self.btn_load_ref_dwf, self.on_load_ref_dwf),
        ]:
            button.Bind(wx.EVT_BUTTON, handler)

        box.Add(self.add_load_row(self.btn_load_dwf, self.lbl_dwf), 0, wx.EXPAND | wx.ALL, 5)
        box.Add(self.add_load_row(self.btn_load_ref_aps, self.lbl_ref_aps), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        box.Add(self.add_load_row(self.btn_load_ref_dwf, self.lbl_ref_dwf), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        stat_box = wx.StaticBoxSizer(wx.VERTICAL, parent, "DWF statistic settings")
        stat_grid = wx.FlexGridSizer(rows=2, cols=5, vgap=6, hgap=6)
        stat_grid.AddGrowableCol(1, 1)
        stat_grid.AddGrowableCol(3, 1)
        self.tc_ref_dwf_stat = wx.TextCtrl(parent, value="50")
        self.tc_sample_dwf_stat = wx.TextCtrl(parent, value="200")
        self.slider_ref_dwf_range = wx.Slider(parent, value=70, minValue=0, maxValue=100)
        self.slider_sample_dwf_range = wx.Slider(parent, value=70, minValue=0, maxValue=100)
        self.lbl_ref_dwf_range = wx.StaticText(parent, label=self.slider_range_label(self.slider_ref_dwf_range))
        self.lbl_sample_dwf_range = wx.StaticText(parent, label=self.slider_range_label(self.slider_sample_dwf_range))
        self.add_stat_slider_row(
            stat_grid,
            parent,
            "Sample DWF stat length",
            self.tc_sample_dwf_stat,
            "s",
            self.slider_sample_dwf_range,
            self.lbl_sample_dwf_range,
        )
        self.add_stat_slider_row(
            stat_grid,
            parent,
            "Ref DWF stat length",
            self.tc_ref_dwf_stat,
            "s",
            self.slider_ref_dwf_range,
            self.lbl_ref_dwf_range,
        )
        stat_box.Add(stat_grid, 0, wx.EXPAND | wx.ALL, 5)
        box.Add(stat_box, 0, wx.EXPAND | wx.ALL, 5)

        aps_fit_box = wx.StaticBoxSizer(wx.VERTICAL, parent, "Reference APS fitting parameters")
        aps_fit_grid = wx.FlexGridSizer(rows=2, cols=3, vgap=6, hgap=6)
        aps_fit_grid.AddGrowableCol(1, 1)
        self.tc_ref_aps_fit_lower = wx.TextCtrl(parent, value="4.75")
        self.tc_ref_aps_fit_upper = wx.TextCtrl(parent, value="5.35")
        self.add_row(aps_fit_grid, parent, "Ref APS fit lower", self.tc_ref_aps_fit_lower, "")
        self.add_row(aps_fit_grid, parent, "Ref APS fit upper", self.tc_ref_aps_fit_upper, "")
        aps_fit_box.Add(aps_fit_grid, 0, wx.EXPAND | wx.ALL, 5)
        self.lbl_ref_aps_fit_source = wx.StaticText(parent, label="Fit source: default energy window")
        aps_fit_box.Add(self.lbl_ref_aps_fit_source, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        box.Add(aps_fit_box, 0, wx.EXPAND | wx.ALL, 5)

        prefix_grid = wx.FlexGridSizer(rows=1, cols=3, vgap=6, hgap=6)
        prefix_grid.AddGrowableCol(1, 1)
        self.tc_dwf_prefix = wx.TextCtrl(parent, value="DWF")
        self.add_row(prefix_grid, parent, "Output prefix", self.tc_dwf_prefix, "")
        box.Add(prefix_grid, 0, wx.EXPAND | wx.ALL, 5)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_workfunction_analysis = wx.Button(parent, label="Analysis")
        self.btn_save_workfunction = wx.Button(parent, label="Save workfunction CSVs")
        self.btn_save_workfunction.Disable()
        self.btn_workfunction_analysis.Bind(wx.EVT_BUTTON, self.on_run_workfunction)
        self.btn_save_workfunction.Bind(wx.EVT_BUTTON, self.on_save_workfunction)
        row.Add(self.btn_workfunction_analysis, 1, wx.EXPAND | wx.RIGHT, 5)
        row.Add(self.btn_save_workfunction, 1, wx.EXPAND)
        box.Add(row, 0, wx.EXPAND | wx.ALL, 5)

        for ctrl in [self.tc_ref_dwf_stat, self.tc_sample_dwf_stat]:
            ctrl.Bind(wx.EVT_TEXT, self.on_preview_input)
        self.tc_ref_aps_fit_lower.Bind(wx.EVT_TEXT, self.on_ref_aps_fit_input)
        self.tc_ref_aps_fit_upper.Bind(wx.EVT_TEXT, self.on_ref_aps_fit_input)
        self.slider_ref_dwf_range.Bind(wx.EVT_SLIDER, self.on_preview_slider)
        self.slider_sample_dwf_range.Bind(wx.EVT_SLIDER, self.on_preview_slider)
        return box

    def build_aps_controls(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "APS Analysis")

        self.btn_load_aps = wx.Button(parent, label="Load APS files")
        self.lbl_aps = wx.StaticText(parent, label="No APS files loaded")
        self.btn_load_aps.Bind(wx.EVT_BUTTON, self.on_load_aps)
        box.Add(self.add_load_row(self.btn_load_aps, self.lbl_aps), 0, wx.EXPAND | wx.ALL, 5)

        fit_box = wx.StaticBoxSizer(wx.VERTICAL, parent, "APS fitting parameters")
        fit_grid = wx.FlexGridSizer(rows=2, cols=3, vgap=6, hgap=6)
        fit_grid.AddGrowableCol(1, 1)
        self.tc_aps_fit_lower = wx.TextCtrl(parent, value="5.45")
        self.tc_aps_fit_upper = wx.TextCtrl(parent, value="6.0")
        self.add_row(fit_grid, parent, "APS fit lower", self.tc_aps_fit_lower, "")
        self.add_row(fit_grid, parent, "APS fit upper", self.tc_aps_fit_upper, "")
        fit_box.Add(fit_grid, 0, wx.EXPAND | wx.ALL, 5)
        self.lbl_aps_fit_source = wx.StaticText(parent, label="Fit source: default energy window")
        fit_box.Add(self.lbl_aps_fit_source, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        box.Add(fit_box, 0, wx.EXPAND | wx.ALL, 5)

        dos_box = wx.StaticBoxSizer(wx.VERTICAL, parent, "DOS parameters")
        dos_grid = wx.FlexGridSizer(rows=4, cols=3, vgap=6, hgap=6)
        dos_grid.AddGrowableCol(1, 1)
        self.tc_dos_window = wx.TextCtrl(parent, value="7")
        self.tc_dos_poly = wx.TextCtrl(parent, value="3")
        self.tc_dos_scale = wx.TextCtrl(parent, value="4.122623")
        self.tc_dos_y0 = wx.TextCtrl(parent, value="0.1")
        self.add_row(dos_grid, parent, "DOS window", self.tc_dos_window, "")
        self.add_row(dos_grid, parent, "DOS polynomial", self.tc_dos_poly, "")
        self.add_row(dos_grid, parent, "DOS scale", self.tc_dos_scale, "")
        self.add_row(dos_grid, parent, "DOS y0", self.tc_dos_y0, "")
        dos_box.Add(dos_grid, 0, wx.EXPAND | wx.ALL, 5)
        box.Add(dos_box, 0, wx.EXPAND | wx.ALL, 5)

        prefix_grid = wx.FlexGridSizer(rows=1, cols=3, vgap=6, hgap=6)
        prefix_grid.AddGrowableCol(1, 1)
        self.tc_aps_prefix = wx.TextCtrl(parent, value="")
        self.add_row(prefix_grid, parent, "Output prefix", self.tc_aps_prefix, "")
        box.Add(prefix_grid, 0, wx.EXPAND | wx.ALL, 5)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_aps_analysis = wx.Button(parent, label="Analysis")
        self.btn_save_aps = wx.Button(parent, label="Save APS CSVs")
        self.btn_save_aps.Disable()
        self.btn_aps_analysis.Bind(wx.EVT_BUTTON, self.on_run_aps)
        self.btn_save_aps.Bind(wx.EVT_BUTTON, self.on_save_aps)
        row.Add(self.btn_aps_analysis, 1, wx.EXPAND | wx.RIGHT, 5)
        row.Add(self.btn_save_aps, 1, wx.EXPAND)
        box.Add(row, 0, wx.EXPAND | wx.ALL, 5)

        for ctrl in [self.tc_dos_window, self.tc_dos_poly, self.tc_dos_scale, self.tc_dos_y0]:
            ctrl.Bind(wx.EVT_TEXT, self.on_preview_input)
        self.tc_aps_fit_lower.Bind(wx.EVT_TEXT, self.on_aps_fit_input)
        self.tc_aps_fit_upper.Bind(wx.EVT_TEXT, self.on_aps_fit_input)
        return box

    def build_spv_controls(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "SPV Processing")

        self.btn_load_spv = wx.Button(parent, label="Load SPV files")
        self.lbl_spv = wx.StaticText(parent, label="No SPV files loaded")
        self.btn_load_spv.Bind(wx.EVT_BUTTON, self.on_load_spv)
        box.Add(self.add_load_row(self.btn_load_spv, self.lbl_spv), 0, wx.EXPAND | wx.ALL, 5)

        grid = wx.FlexGridSizer(rows=3, cols=5, vgap=6, hgap=6)
        grid.AddGrowableCol(1, 1)
        grid.AddGrowableCol(4, 1)
        self.tc_spv_initial_dark = wx.TextCtrl(parent, value="20")
        self.tc_spv_light1 = wx.TextCtrl(parent, value="100")
        self.tc_spv_dark1 = wx.TextCtrl(parent, value="150")
        self.tc_spv_repeats = wx.TextCtrl(parent, value="2")
        self.add_spv_timing_row(grid, parent, "Initial Dark", self.tc_spv_initial_dark, "s")
        self.add_spv_timing_row(grid, parent, "Light 1", self.tc_spv_light1, "s", "Repeats", self.tc_spv_repeats)
        self.add_spv_timing_row(grid, parent, "Dark 1", self.tc_spv_dark1, "s")
        box.Add(grid, 0, wx.EXPAND | wx.ALL, 5)

        prefix_grid = wx.FlexGridSizer(rows=1, cols=3, vgap=6, hgap=6)
        prefix_grid.AddGrowableCol(1, 1)
        self.tc_spv_prefix = wx.TextCtrl(parent, value="SPV")
        self.add_row(prefix_grid, parent, "Output prefix", self.tc_spv_prefix, "")
        box.Add(prefix_grid, 0, wx.EXPAND | wx.ALL, 5)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_spv_analysis = wx.Button(parent, label="Analysis")
        self.btn_save_spv = wx.Button(parent, label="Save SPV CSVs")
        self.btn_save_spv.Disable()
        self.btn_spv_analysis.Bind(wx.EVT_BUTTON, self.on_run_spv)
        self.btn_save_spv.Bind(wx.EVT_BUTTON, self.on_save_spv)
        row.Add(self.btn_spv_analysis, 1, wx.EXPAND | wx.RIGHT, 5)
        row.Add(self.btn_save_spv, 1, wx.EXPAND)
        box.Add(row, 0, wx.EXPAND | wx.ALL, 5)

        for ctrl in [
            self.tc_spv_initial_dark,
            self.tc_spv_dark1,
            self.tc_spv_light1,
            self.tc_spv_repeats,
        ]:
            ctrl.Bind(wx.EVT_TEXT, self.on_preview_input)
        return box

    def build_right_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(panel)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_notebook_page_changed)
        self.figure_work_preview, self.canvas_work_preview = self.add_figure_page("WF Preview / Results")
        self.figure_aps_preview, self.canvas_aps_preview = self.add_figure_page("APS Preview / Results")
        self.figure_dos_results, self.canvas_dos_results = self.add_figure_page("DOS")
        self.figure_spv_preview, self.canvas_spv_preview = self.add_figure_page("SPV Preview / Results")
        sizer.Add(self.notebook, 1, wx.EXPAND)
        log_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "APS log")
        self.log_box = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.log_box.SetMinSize((-1, 105))
        log_box.Add(self.log_box, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(log_box, 0, wx.EXPAND | wx.TOP, 6)
        panel.SetSizer(sizer)
        self.clear_all_figures()
        return panel

    def add_figure_page(self, title):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        figure = Figure(figsize=(8, 5))
        canvas = FigureCanvasWxAgg(panel, -1, figure)
        sizer.Add(canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self.notebook.AddPage(panel, title)
        return figure, canvas

    @staticmethod
    def add_row(grid, parent, label, ctrl, unit):
        grid.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=unit), 0, wx.ALIGN_CENTER_VERTICAL)

    @staticmethod
    def add_spv_timing_row(grid, parent, label, ctrl, unit, extra_label="", extra_ctrl=None):
        grid.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=unit), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=extra_label), 0, wx.ALIGN_CENTER_VERTICAL)
        if extra_ctrl is None:
            grid.AddSpacer(1)
        else:
            grid.Add(extra_ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

    @staticmethod
    def add_load_row(button, label):
        button.SetMinSize((135, -1))
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(button, 0, wx.RIGHT, 6)
        row.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        return row

    @staticmethod
    def add_stat_slider_row(grid, parent, label, ctrl, unit, slider, range_label):
        grid.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(wx.StaticText(parent, label=unit), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(slider, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(range_label, 0, wx.ALIGN_CENTER_VERTICAL)

    def on_load_dwf(self, event):
        paths = self.open_files("Load DWF files", multiple=True)
        if paths:
            self.dwf_paths = paths
            self.lbl_dwf.SetLabel(self.describe_paths(paths))
            self.btn_save_workfunction.Disable()
            log_usage_event(self, "aps_dwf_loaded", {"count": len(paths), **file_metadata(paths[0])})
            self.schedule_preview()

    def on_load_ref_aps(self, event):
        paths = self.open_files("Load reference APS", multiple=False)
        if paths:
            self.ref_aps_path = paths[0]
            self.lbl_ref_aps.SetLabel(Path(paths[0]).name)
            self.apply_ref_aps_metadata(paths[0])
            self.btn_save_workfunction.Disable()
            log_usage_event(self, "aps_ref_aps_loaded", file_metadata(paths[0]))
            self.schedule_preview()

    def on_load_ref_dwf(self, event):
        paths = self.open_files("Load reference DWF", multiple=False)
        if paths:
            self.ref_dwf_path = paths[0]
            self.lbl_ref_dwf.SetLabel(Path(paths[0]).name)
            self.btn_save_workfunction.Disable()
            log_usage_event(self, "aps_ref_dwf_loaded", file_metadata(paths[0]))
            self.schedule_preview()

    def on_load_aps(self, event):
        paths = self.open_files("Load APS files", multiple=True)
        if paths:
            self.aps_paths = paths
            self.lbl_aps.SetLabel(self.describe_paths(paths))
            self.apply_aps_metadata(paths)
            self.btn_save_aps.Disable()
            self.notebook.SetSelection(1)
            log_usage_event(self, "aps_files_loaded", {"count": len(paths), **file_metadata(paths[0])})
            self.schedule_preview()

    def on_load_spv(self, event):
        paths = self.open_files("Load SPV files", multiple=True)
        if paths:
            self.spv_paths = paths
            self.lbl_spv.SetLabel(self.describe_paths(paths))
            self.btn_save_spv.Disable()
            self.notebook.SetSelection(3)
            log_usage_event(self, "spv_files_loaded", {"count": len(paths), **file_metadata(paths[0])})
            try:
                settings = self.read_spv_settings()
                data = import_spv_files(paths, settings)
                end_time = max(float(item.time[-1]) for item in data)
                self.log(f"Loaded {len(data)} SPV file(s); timemap={settings.timemap}, max time={end_time:.3g} s.")
            except Exception as exc:
                self.log(f"SPV load preview warning: {exc}")
            self.schedule_preview()

    def open_files(self, title, multiple):
        style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        if multiple:
            style |= wx.FD_MULTIPLE
        with wx.FileDialog(self, title, wildcard="DAT files (*.DAT)|*.DAT|All files (*.*)|*.*", style=style) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return []
            return list(dialog.GetPaths() if multiple else [dialog.GetPath()])

    @staticmethod
    def describe_paths(paths):
        if len(paths) == 1:
            return Path(paths[0]).name
        return f"{len(paths)} files loaded"

    def apply_ref_aps_metadata(self, path):
        try:
            [item] = import_aps_files([path], sqrt=True)
        except Exception as exc:
            self.log(f"Could not inspect reference APS metadata: {exc}")
            return
        metadata = item.metadata
        self.setting_fit_fields = True
        try:
            if metadata is not None and metadata.has_fit_window:
                self.ref_aps_fit_domain = "energy"
                self.tc_ref_aps_fit_lower.SetValue(f"{metadata.e_low_ev:.6g}")
                self.tc_ref_aps_fit_upper.SetValue(f"{metadata.e_high_ev:.6g}")
                self.lbl_ref_aps_fit_source.SetLabel(
                    f"Fit source: DAT ELo/EHi loaded as energy window ({metadata.e_low_ev:.3f}-{metadata.e_high_ev:.3f} eV)"
                )
                self.log_metadata("Reference APS", item)
            else:
                self.ref_aps_fit_domain = "energy"
                lower, upper = self.energy_bounds_for_item(item)
                self.tc_ref_aps_fit_lower.SetValue(f"{lower:.6g}")
                self.tc_ref_aps_fit_upper.SetValue(f"{upper:.6g}")
                self.lbl_ref_aps_fit_source.SetLabel("Fit source: no DAT ELo/EHi; using full energy range")
                self.log("No DAT fit metadata found in reference APS; using full energy range.")
        finally:
            self.setting_fit_fields = False

    def apply_aps_metadata(self, paths):
        try:
            data = import_aps_files(paths, sqrt=None)
        except Exception as exc:
            self.log(f"Could not inspect APS metadata: {exc}")
            return
        metadata_items = [item for item in data if item.metadata is not None and item.metadata.has_fit_window]
        self.setting_fit_fields = True
        try:
            if metadata_items:
                first = metadata_items[0].metadata
                self.aps_fit_domain = "energy"
                self.tc_aps_fit_lower.SetValue(f"{first.e_low_ev:.6g}")
                self.tc_aps_fit_upper.SetValue(f"{first.e_high_ev:.6g}")
                self.lbl_aps_fit_source.SetLabel(f"Fit source: DAT ELo/EHi loaded as energy window ({len(metadata_items)}/{len(data)} files)")
                for item in data:
                    self.log_metadata("APS", item)
                if len(metadata_items) != len(data):
                    self.log("Some APS files have no DAT fit metadata; shared energy fit window remains visible above.")
            else:
                self.aps_fit_domain = "energy"
                lower, upper = self.energy_bounds_for_item(data[0])
                self.tc_aps_fit_lower.SetValue(f"{lower:.6g}")
                self.tc_aps_fit_upper.SetValue(f"{upper:.6g}")
                self.lbl_aps_fit_source.SetLabel("Fit source: no DAT ELo/EHi; using full energy range")
                self.log("No DAT fit metadata found in APS files; using full energy range.")
        finally:
            self.setting_fit_fields = False

    @staticmethod
    def energy_bounds_for_item(item):
        return float(item.energy.min()), float(item.energy.max())

    def log_metadata(self, prefix, item):
        metadata = item.metadata
        if metadata is None:
            self.log(f"{prefix} {item.name}: no DAT metadata.")
            return
        pieces = []
        if metadata.has_fit_window:
            pieces.append(f"ELo={metadata.e_low_ev:.3f} eV")
            pieces.append(f"EHi={metadata.e_high_ev:.3f} eV")
        if metadata.wf_ev is not None:
            pieces.append(f"WF={metadata.wf_ev:.3f} eV")
        if metadata.r2 is not None:
            pieces.append(f"R2={metadata.r2:.3f}")
        if metadata.power is not None:
            pieces.append(f"Power={metadata.power}")
        self.log(f"{prefix} {item.name}: using DAT metadata ({', '.join(pieces)}).")

    def collect_app_parameters(self):
        return {
            "dwf_paths": list(self.dwf_paths),
            "ref_aps_path": self.ref_aps_path,
            "ref_dwf_path": self.ref_dwf_path,
            "aps_paths": list(self.aps_paths),
            "spv_paths": list(self.spv_paths),
            "ref_dwf_stat_s": self.tc_ref_dwf_stat.GetValue(),
            "sample_dwf_stat_s": self.tc_sample_dwf_stat.GetValue(),
            "ref_dwf_range": self.slider_ref_dwf_range.GetValue(),
            "sample_dwf_range": self.slider_sample_dwf_range.GetValue(),
            "ref_aps_fit_lower": self.tc_ref_aps_fit_lower.GetValue(),
            "ref_aps_fit_upper": self.tc_ref_aps_fit_upper.GetValue(),
            "dwf_prefix": self.tc_dwf_prefix.GetValue(),
            "aps_fit_lower": self.tc_aps_fit_lower.GetValue(),
            "aps_fit_upper": self.tc_aps_fit_upper.GetValue(),
            "dos_window": self.tc_dos_window.GetValue(),
            "dos_poly": self.tc_dos_poly.GetValue(),
            "dos_scale": self.tc_dos_scale.GetValue(),
            "dos_y0": self.tc_dos_y0.GetValue(),
            "aps_prefix": self.tc_aps_prefix.GetValue(),
            "spv_initial_dark": self.tc_spv_initial_dark.GetValue(),
            "spv_light1": self.tc_spv_light1.GetValue(),
            "spv_dark1": self.tc_spv_dark1.GetValue(),
            "spv_repeats": self.tc_spv_repeats.GetValue(),
            "spv_prefix": self.tc_spv_prefix.GetValue(),
        }

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        self.analysis_running = False
        self.workfunction_result = None
        self.aps_result = None
        self.spv_result = None
        self.dwf_paths = [str(path) for path in params.get("dwf_paths", []) if path]
        self.ref_aps_path = str(params.get("ref_aps_path", "") or "")
        self.ref_dwf_path = str(params.get("ref_dwf_path", "") or "")
        self.aps_paths = [str(path) for path in params.get("aps_paths", []) if path]
        self.spv_paths = [str(path) for path in params.get("spv_paths", []) if path]
        self.lbl_dwf.SetLabel(self.describe_paths(self.dwf_paths) if self.dwf_paths else "No DWF files loaded")
        self.lbl_ref_aps.SetLabel(Path(self.ref_aps_path).name if self.ref_aps_path else "No reference APS loaded")
        self.lbl_ref_dwf.SetLabel(Path(self.ref_dwf_path).name if self.ref_dwf_path else "No reference DWF loaded")
        self.lbl_aps.SetLabel(self.describe_paths(self.aps_paths) if self.aps_paths else "No APS files loaded")
        self.lbl_spv.SetLabel(self.describe_paths(self.spv_paths) if self.spv_paths else "No SPV files loaded")

        self.tc_ref_dwf_stat.SetValue(str(params.get("ref_dwf_stat_s", self.tc_ref_dwf_stat.GetValue())))
        self.tc_sample_dwf_stat.SetValue(str(params.get("sample_dwf_stat_s", self.tc_sample_dwf_stat.GetValue())))
        self.slider_ref_dwf_range.SetValue(int(params.get("ref_dwf_range", self.slider_ref_dwf_range.GetValue())))
        self.slider_sample_dwf_range.SetValue(int(params.get("sample_dwf_range", self.slider_sample_dwf_range.GetValue())))
        self.lbl_ref_dwf_range.SetLabel(self.slider_range_label(self.slider_ref_dwf_range))
        self.lbl_sample_dwf_range.SetLabel(self.slider_range_label(self.slider_sample_dwf_range))
        self.tc_ref_aps_fit_lower.SetValue(str(params.get("ref_aps_fit_lower", self.tc_ref_aps_fit_lower.GetValue())))
        self.tc_ref_aps_fit_upper.SetValue(str(params.get("ref_aps_fit_upper", self.tc_ref_aps_fit_upper.GetValue())))
        self.tc_dwf_prefix.SetValue(str(params.get("dwf_prefix", self.tc_dwf_prefix.GetValue())))
        self.tc_aps_fit_lower.SetValue(str(params.get("aps_fit_lower", self.tc_aps_fit_lower.GetValue())))
        self.tc_aps_fit_upper.SetValue(str(params.get("aps_fit_upper", self.tc_aps_fit_upper.GetValue())))
        self.tc_dos_window.SetValue(str(params.get("dos_window", self.tc_dos_window.GetValue())))
        self.tc_dos_poly.SetValue(str(params.get("dos_poly", self.tc_dos_poly.GetValue())))
        self.tc_dos_scale.SetValue(str(params.get("dos_scale", self.tc_dos_scale.GetValue())))
        self.tc_dos_y0.SetValue(str(params.get("dos_y0", self.tc_dos_y0.GetValue())))
        self.tc_aps_prefix.SetValue(str(params.get("aps_prefix", self.tc_aps_prefix.GetValue())))
        self.tc_spv_initial_dark.SetValue(str(params.get("spv_initial_dark", self.tc_spv_initial_dark.GetValue())))
        self.tc_spv_light1.SetValue(str(params.get("spv_light1", self.tc_spv_light1.GetValue())))
        self.tc_spv_dark1.SetValue(str(params.get("spv_dark1", self.tc_spv_dark1.GetValue())))
        self.tc_spv_repeats.SetValue(str(params.get("spv_repeats", self.tc_spv_repeats.GetValue())))
        self.tc_spv_prefix.SetValue(str(params.get("spv_prefix", self.tc_spv_prefix.GetValue())))
        if self.ref_aps_path and Path(self.ref_aps_path).exists():
            self.apply_ref_aps_metadata(self.ref_aps_path)
        if self.aps_paths and all(Path(path).exists() for path in self.aps_paths):
            self.apply_aps_metadata(self.aps_paths)
        self.update_analysis_buttons()
        self.schedule_preview(delay_ms=50)

    def on_preview_input(self, event):
        self.schedule_preview()
        event.Skip()

    def on_ref_aps_fit_input(self, event):
        if not self.setting_fit_fields:
            self.ref_aps_fit_domain = "energy"
            self.update_ref_aps_fit_source_label("manual")
        self.schedule_preview()
        event.Skip()

    def on_aps_fit_input(self, event):
        if not self.setting_fit_fields:
            self.aps_fit_domain = "energy"
            self.update_aps_fit_source_label("manual")
        self.schedule_preview()
        event.Skip()

    def update_ref_aps_fit_source_label(self, source):
        self.lbl_ref_aps_fit_source.SetLabel(f"Fit source: {source} energy window")

    def update_aps_fit_source_label(self, source):
        self.lbl_aps_fit_source.SetLabel(f"Fit source: {source} energy window")

    def on_preview_slider(self, event):
        self.lbl_ref_dwf_range.SetLabel(self.slider_range_label(self.slider_ref_dwf_range))
        self.lbl_sample_dwf_range.SetLabel(self.slider_range_label(self.slider_sample_dwf_range))
        wx.CallAfter(self.update_workfunction_preview)
        event.Skip()

    def on_size(self, event):
        event.Skip()
        self.schedule_preview(delay_ms=150)

    def on_notebook_page_changed(self, event):
        event.Skip()
        wx.CallAfter(self.update_current_preview)

    @staticmethod
    def slider_range_label(slider):
        return f"last {dwf_preview_percent_from_slider(slider.GetValue()):.1f}%"

    def schedule_preview(self, delay_ms=350):
        if self.preview_timer is not None and self.preview_timer.IsRunning():
            self.preview_timer.Stop()
        self.preview_timer = wx.CallLater(delay_ms, self.update_previews)

    def update_previews(self):
        self.update_workfunction_preview()
        self.update_aps_preview()
        self.update_spv_preview()

    def update_current_preview(self):
        selection = self.notebook.GetSelection()
        if selection == 0:
            self.update_workfunction_preview()
        elif selection == 1:
            self.update_aps_preview()
        elif selection == 2 and self.aps_result is not None:
            self.draw_dos_results(self.aps_result)
        elif selection == 3:
            self.update_spv_preview()

    def update_workfunction_preview(self):
        self.figure_work_preview.clear()
        ax_sample_dwf = self.figure_work_preview.add_subplot(311)
        ax_ref_dwf = self.figure_work_preview.add_subplot(312)
        ax_aps = self.figure_work_preview.add_subplot(313)
        try:
            settings = self.read_dwf_settings()
            if self.dwf_paths:
                for item in import_dwf_files(self.dwf_paths):
                    ax_sample_dwf.plot(item.time, item.cpd_data, label=item.name)
                    self.shade_stat_region(ax_sample_dwf, item.time, settings.sample_dwf_stat_length_s, "tab:orange")
            if self.ref_dwf_path:
                [ref_dwf] = import_dwf_files([self.ref_dwf_path])
                ax_ref_dwf.plot(ref_dwf.time, ref_dwf.cpd_data, label=f"ref {ref_dwf.name}")
                self.shade_stat_region(ax_ref_dwf, ref_dwf.time, settings.ref_dwf_stat_length_s, "tab:orange")
            if self.ref_aps_path:
                [ref_aps] = import_aps_files([self.ref_aps_path], sqrt=True)
                try:
                    analyze_workfunction_ref_aps(ref_aps, settings)
                    ax_aps.plot(ref_aps.energy, ref_aps.pes, label=ref_aps.name)
                    self.shade_aps_fit_region(ax_aps, ref_aps, settings.ref_aps_fit_lower_bound, settings.ref_aps_fit_upper_bound, settings.ref_aps_fit_domain)
                    self.plot_dat_reference_markers(ax_aps, ref_aps)
                    self.plot_aps_fit(ax_aps, ref_aps)
                except Exception as exc:
                    ax_aps.text(0.02, 0.92, f"Preview fit warning: {exc}", transform=ax_aps.transAxes, fontsize=8)
            ax_sample_dwf.set_title("Sample DWF/CPD preview")
            ax_sample_dwf.set_xlabel("Time(s)")
            ax_sample_dwf.set_ylabel("CPD (meV)")
            ax_ref_dwf.set_title("Reference DWF/CPD preview")
            ax_ref_dwf.set_xlabel("Time(s)")
            ax_ref_dwf.set_ylabel("CPD (meV)")
            ax_aps.set_title("Reference APS preview")
            ax_aps.set_xlabel("Energy (eV)")
            ax_aps.set_ylabel("Photoemission$^{1/2}$  (arb.unit)")
            self.apply_aps_axis_style(ax_aps)
            for ax in [ax_sample_dwf, ax_ref_dwf]:
                self.apply_dwf_axis_style(ax)
            self.apply_last_percent_xlim_from_lines(ax_sample_dwf, self.slider_sample_dwf_range.GetValue())
            self.apply_last_percent_xlim_from_lines(ax_ref_dwf, self.slider_ref_dwf_range.GetValue())
            for ax in [ax_sample_dwf, ax_ref_dwf]:
                if ax.lines:
                    ax.legend(fontsize=8)
            if ax_aps.lines:
                ax_aps.legend(fontsize=8)
            if self.workfunction_result is not None:
                self.annotate_workfunction_result(ax_sample_dwf, self.workfunction_result)
            self.figure_work_preview.tight_layout(pad=1.2)
        except Exception as exc:
            ax_sample_dwf.text(0.02, 0.9, str(exc), transform=ax_sample_dwf.transAxes)
        self.canvas_work_preview.draw()

    def update_aps_preview(self):
        self.figure_aps_preview.clear()
        ax = self.figure_aps_preview.add_subplot(211)
        result_ax = self.figure_aps_preview.add_subplot(212)
        try:
            settings = self.read_aps_settings()
            if self.aps_paths:
                data = import_aps_files(self.aps_paths, sqrt=None if settings.fit_domain == "energy" else settings.sqrt)
                for item in data:
                    try:
                        analyze_with_settings(item, settings)
                        ax.plot(item.energy, item.pes, label=item.name)
                        self.shade_aps_fit_region(ax, item, settings.fit_lower_bound, settings.fit_upper_bound, settings.fit_domain)
                        self.plot_dat_reference_markers(ax, item)
                        self.plot_aps_fit(ax, item)
                    except Exception as exc:
                        ax.text(0.02, 0.92, f"Preview fit warning: {exc}", transform=ax.transAxes, fontsize=8)
                        break
            ax.set_title("APS preview with fitting region")
            ax.set_xlabel("Energy (eV)")
            ax.set_ylabel(self.aps_y_label(data[0].sqrt if self.aps_paths else False))
            self.apply_aps_axis_style(ax)
            if ax.lines:
                ax.legend(fontsize=8)
            if self.aps_result is not None:
                self.draw_aps_result_axis(result_ax, self.aps_result)
            else:
                result_ax.text(0.5, 0.5, "Run APS analysis to show results.", ha="center", va="center", transform=result_ax.transAxes)
                result_ax.set_axis_off()
            self.figure_aps_preview.tight_layout(pad=1.2)
        except Exception as exc:
            ax.text(0.02, 0.9, str(exc), transform=ax.transAxes)
        self.canvas_aps_preview.draw()

    def update_spv_preview(self):
        self.figure_spv_preview.clear()
        preview_ax = self.figure_spv_preview.add_subplot(311)
        result_ax = self.figure_spv_preview.add_subplot(312)
        norm_ax = self.figure_spv_preview.add_subplot(313)
        try:
            if self.spv_paths:
                settings = self.read_spv_settings()
                for item in import_spv_files(self.spv_paths, settings):
                    preview_ax.plot(item.time, item.cpd_data, label=item.name)
                    self.shade_spv_light_regions(preview_ax, item)
            preview_ax.set_title("SPV preview - raw WF data")
            preview_ax.set_xlabel("Time(s)")
            preview_ax.set_ylabel("WF (mV)")
            self.apply_spv_axis_style(preview_ax)
            if self.spv_result is not None:
                self.draw_spv_result_axis(result_ax, self.spv_result)
                self.draw_spv_norm_axis(norm_ax, self.spv_result)
            else:
                self.show_empty_spv_axis(result_ax, "Run SPV analysis to show background-corrected results.")
                self.show_empty_spv_axis(norm_ax, "Run SPV analysis to show normalized SPV.")
            self.figure_spv_preview.tight_layout(pad=1.2)
        except Exception as exc:
            preview_ax.text(0.02, 0.9, str(exc), transform=preview_ax.transAxes)
        self.canvas_spv_preview.draw()

    def draw_spv_result_axis(self, ax, result):
        for item in result.data:
            ax.plot(item.time, item.cpd_data, label=f"{item.name}, bg={item.bg_cpd:.3g} meV")
            self.shade_spv_light_regions(ax, item)
        ax.set_title("SPV results - background corrected")
        ax.set_xlabel("Time(s)")
        ax.set_ylabel("SPV (meV)")
        self.apply_spv_axis_style(ax)

    def draw_spv_norm_axis(self, ax, result):
        for item in result.data:
            ax.plot(item.time, item.norm_spv, label=f"{item.name}")
            self.shade_spv_light_regions(ax, item)
        ax.set_title("Normalized SPV")
        ax.set_xlabel("Time(s)")
        ax.set_ylabel("Normalized SPV")
        self.apply_spv_axis_style(ax)

    @staticmethod
    def show_empty_spv_axis(ax, message):
        ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()

    @staticmethod
    def apply_spv_axis_style(ax):
        ax.grid(True, which="both", axis="both")
        ax.autoscale(enable=True, axis="both", tight=True)
        if ax.lines:
            ax.legend(fontsize=8)

    def shade_stat_region(self, ax, time_values, length_s, color):
        if len(time_values) == 0:
            return
        start = max(float(time_values[-1]) - float(length_s), float(time_values[0]))
        ax.axvspan(start, float(time_values[-1]), color=color, alpha=0.12)

    @staticmethod
    def shade_spv_light_regions(ax, item):
        for start, stop in item.light_spans():
            ax.axvspan(start, stop, color="yellow", alpha=0.35)

    @staticmethod
    def apply_last_percent_xlim(ax, time_values, slider_value):
        if len(time_values) == 0:
            return
        start_time = float(time_values[0])
        end_time = float(time_values[-1])
        span = end_time - start_time
        if span <= 0:
            return
        percent = dwf_preview_percent_from_slider(slider_value)
        visible_start = end_time - span * percent / 100.0
        ax.set_xlim(max(start_time, visible_start), end_time)

    @staticmethod
    def apply_last_percent_xlim_from_lines(ax, slider_value):
        x_values = []
        for line in ax.lines:
            data = line.get_xdata()
            if len(data):
                x_values.extend(float(value) for value in data)
        if not x_values:
            return
        start_time = min(x_values)
        end_time = max(x_values)
        span = end_time - start_time
        if span <= 0:
            return
        percent = dwf_preview_percent_from_slider(slider_value)
        visible_start = end_time - span * percent / 100.0
        ax.set_xlim(max(start_time, visible_start), end_time)

    @staticmethod
    def shade_aps_fit_region(ax, item, lower, upper, fit_domain):
        if fit_domain == "energy":
            ax.axvspan(lower, upper, color="tab:orange", alpha=0.18)
        elif item.is_analyzed:
            ax.axvspan(
                float(item.energy[item.fit_candidate_start_index]),
                float(item.energy[item.fit_candidate_stop_index - 1]),
                color="tab:orange",
                alpha=0.18,
                label="selected candidate range",
            )

    @staticmethod
    def plot_dat_reference_markers(ax, item):
        metadata = item.metadata
        if metadata is None:
            return
        if metadata.wf_ev is not None and metadata.wf_ev > 0:
            ax.axvline(metadata.wf_ev, color="tab:green", linestyle=":", linewidth=1.0, label=f"{item.name} DAT WF")

    @staticmethod
    def plot_aps_fit(ax, item):
        if not item.is_analyzed:
            return
        x = item.energy[item.lin_start_index : item.lin_stop_index]
        y = item.lin_par[0] * x + item.lin_par[1]
        ax.plot(x, y, "--", linewidth=1.6, label=f"{item.name} fit")
        ax.axvspan(
            float(item.energy[item.lin_start_index]),
            float(item.energy[item.lin_stop_index - 1]),
            color="tab:blue",
            alpha=0.08,
            label="actual fitted segment",
        )
        ax.text(
            0.02,
            0.86,
            f"{item.name} used: {item.energy[item.lin_start_index]:.3f}-{item.energy[item.lin_stop_index - 1]:.3f} eV",
            transform=ax.transAxes,
            fontsize=8,
            bbox={"facecolor": "white", "alpha": 0.65, "edgecolor": "0.8"},
        )

    @staticmethod
    def apply_dwf_axis_style(ax):
        ax.grid(True, which="both", axis="both")
        ax.autoscale(enable=True, axis="both", tight=True)

    @staticmethod
    def apply_aps_axis_style(ax):
        ax.grid(True, which="both", axis="x")
        ax.axhline(y=0, color="k", linestyle="--", linewidth=0.8)
        ax.autoscale(enable=True, axis="both", tight=True)
        ax.set_ylim(bottom=-0.5)

    @staticmethod
    def aps_y_label(sqrt):
        if sqrt:
            return "Photoemission$^{1/2}$  (arb.unit)"
        return "Photoemission$^{1/3}$  (arb. unit)"

    def on_run_workfunction(self, event):
        if self.analysis_running:
            self.show_warning("An APS analysis is already running.")
            return
        try:
            settings = self.read_dwf_settings()
            if not self.dwf_paths or not self.ref_aps_path or not self.ref_dwf_path:
                raise ApsAnalysisError("Load DWF files, one reference APS file, and one reference DWF file first.")
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.analysis_running = True
        self.update_analysis_buttons()
        self.notebook.SetSelection(0)
        self.log("Starting workfunction analysis...")
        log_usage_event(self, "aps_workfunction_analysis_started", {"dwf_files": len(self.dwf_paths)})
        threading.Thread(target=self.workfunction_worker, args=(settings,), daemon=True).start()

    def workfunction_worker(self, settings):
        try:
            result = analyze_workfunction(self.dwf_paths, self.ref_aps_path, self.ref_dwf_path, settings)
            wx.CallAfter(self.on_workfunction_result, result)
        except Exception as exc:
            wx.CallAfter(self.on_analysis_error, f"Workfunction analysis failed: {exc}")

    def on_workfunction_result(self, result):
        self.workfunction_result = result
        self.analysis_running = False
        self.btn_save_workfunction.Enable()
        self.update_analysis_buttons()
        self.update_workfunction_preview()
        self.notebook.SetSelection(0)
        self.log("Workfunction analysis completed.")
        log_usage_event(self, "aps_workfunction_analysis_finished", {"dwf_files": len(result.dwf_data)})

    @staticmethod
    def annotate_workfunction_result(ax, result):
        lines = [f"Tip DWF = {result.tip_dwf:.4g} eV"]
        for item in result.dwf_data[:4]:
            lines.append(f"{item.name}: {item.average_cpd:.4g} +/- {item.std_cpd:.2g} {item.data_unit}")
        if len(result.dwf_data) > 4:
            lines.append(f"... {len(result.dwf_data) - 4} more")
        ax.text(
            0.02,
            0.98,
            "\n".join(lines),
            transform=ax.transAxes,
            va="top",
            fontsize=8,
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "0.8"},
        )

    def on_run_aps(self, event):
        if self.analysis_running:
            self.show_warning("An APS analysis is already running.")
            return
        try:
            aps_settings = self.read_aps_settings()
            dos_settings = self.read_dos_settings()
            if not self.aps_paths:
                raise ApsAnalysisError("Load at least one APS file first.")
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.analysis_running = True
        self.update_analysis_buttons()
        self.notebook.SetSelection(1)
        self.log("Starting APS analysis...")
        log_usage_event(self, "aps_analysis_started", {"aps_files": len(self.aps_paths)})
        threading.Thread(target=self.aps_worker, args=(aps_settings, dos_settings), daemon=True).start()

    def aps_worker(self, aps_settings, dos_settings):
        try:
            result = analyze_aps_files(self.aps_paths, aps_settings, dos_settings)
            wx.CallAfter(self.on_aps_result, result)
        except Exception as exc:
            wx.CallAfter(self.on_analysis_error, f"APS analysis failed: {exc}")

    def on_aps_result(self, result):
        self.aps_result = result
        self.analysis_running = False
        self.btn_save_aps.Enable()
        self.update_analysis_buttons()
        self.update_aps_preview()
        self.draw_dos_results(result)
        self.notebook.SetSelection(1)
        self.log("APS analysis completed.")
        log_usage_event(self, "aps_analysis_finished", {"aps_files": len(result.data)})

    def on_run_spv(self, event):
        if self.analysis_running:
            self.show_warning("An APS analysis is already running.")
            return
        try:
            settings = self.read_spv_settings()
            if not self.spv_paths:
                raise ApsAnalysisError("Load at least one SPV file first.")
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.analysis_running = True
        self.update_analysis_buttons()
        self.notebook.SetSelection(3)
        self.log("Starting SPV analysis...")
        log_usage_event(self, "spv_analysis_started", {"spv_files": len(self.spv_paths)})
        threading.Thread(target=self.spv_worker, args=(settings,), daemon=True).start()

    def spv_worker(self, settings):
        try:
            result = analyze_spv_files(self.spv_paths, settings)
            wx.CallAfter(self.on_spv_result, result)
        except Exception as exc:
            wx.CallAfter(self.on_analysis_error, f"SPV analysis failed: {exc}")

    def on_spv_result(self, result):
        self.spv_result = result
        self.analysis_running = False
        self.btn_save_spv.Enable()
        self.update_analysis_buttons()
        self.update_spv_preview()
        self.notebook.SetSelection(3)
        for item in result.data:
            self.log(f"SPV {item.name}: background={item.bg_cpd:.4g} meV.")
        self.log("SPV analysis completed.")
        log_usage_event(self, "spv_analysis_finished", {"spv_files": len(result.data)})

    def draw_aps_results(self, result):
        self.update_aps_preview()

    def draw_aps_result_axis(self, ax, result):
        for item in result.data:
            ax.plot(item.energy, item.pes, label=f"{item.name}, HOMO={item.homo:.3g} +/- {item.std_homo:.2g} eV")
            self.plot_aps_fit(ax, item)
        ax.set_title("APS analysis results")
        ax.set_xlabel("Energy (eV)")
        ax.set_ylabel(self.aps_y_label(result.data[0].sqrt))
        self.apply_aps_axis_style(ax)
        if ax.lines:
            ax.legend(fontsize=8)

    def draw_dos_results(self, result):
        self.figure_dos_results.clear()
        ax = self.figure_dos_results.add_subplot(111)
        for item in result.data:
            ax.plot(item.energy, item.dos_raw, "o-", markerfacecolor="none", markersize=3, linewidth=0.8, label=f"{item.name} no smooth")
            ax.plot(item.energy, item.dos, "*-", markerfacecolor="none", markersize=3, label=f"{item.name} smooth")
        ax.set_title("DOS results - no smooth and smoothed")
        ax.set_xlabel("Energy (eV)")
        ax.set_ylabel("DOS (arb. unit)")
        self.apply_aps_axis_style(ax)
        ax.legend(fontsize=8)
        self.figure_dos_results.tight_layout(pad=1.2)
        self.canvas_dos_results.draw()

    def on_analysis_error(self, message):
        self.analysis_running = False
        self.update_analysis_buttons()
        self.log(message)
        log_usage_event(self, "aps_analysis_failed")
        self.show_warning(message)

    def update_analysis_buttons(self):
        enabled = not self.analysis_running
        for button in [self.btn_workfunction_analysis, self.btn_aps_analysis, self.btn_spv_analysis]:
            button.Enable(enabled)
        self.btn_save_workfunction.Enable(enabled and self.workfunction_result is not None)
        self.btn_save_aps.Enable(enabled and self.aps_result is not None)
        self.btn_save_spv.Enable(enabled and self.spv_result is not None)

    def on_save_workfunction(self, event):
        if self.workfunction_result is None:
            self.show_warning("Run workfunction analysis before saving.")
            return
        folder = self.choose_output_folder()
        if not folder:
            return
        prefix = self.tc_dwf_prefix.GetValue().strip() or "DWF"
        try:
            path1 = save_dwf_csv(self.workfunction_result.dwf_data, folder, prefix)
            path2 = save_dwf_stat_csv(self.workfunction_result.dwf_data, folder, f"{prefix}_stat")
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.log(f"Saved workfunction CSVs: {path1}; {path2}")
        log_usage_event(self, "aps_workfunction_saved", file_metadata(path1))

    def on_save_aps(self, event):
        if self.aps_result is None:
            self.show_warning("Run APS analysis before saving.")
            return
        folder = self.choose_output_folder()
        if not folder:
            return
        prefix = self.tc_aps_prefix.GetValue().strip()
        try:
            path1 = save_aps_csv(self.aps_result.data, folder, f"{prefix}_APS" if prefix else "APS")
            path2 = save_aps_fit_csv(self.aps_result.data, folder, f"{prefix}_APS_linear_regression" if prefix else "APS_linear_regression")
            path3 = save_homo_error_csv(self.aps_result.data, folder, f"{prefix}_APS_HOMO" if prefix else "APS_HOMO")
            path4 = save_dos_csv(self.aps_result.data, folder, f"{prefix}_DOS" if prefix else "DOS")
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.log(f"Saved APS CSVs: {path1}; {path2}; {path3}; {path4}")
        log_usage_event(self, "aps_results_saved", file_metadata(path1))

    def on_save_spv(self, event):
        if self.spv_result is None:
            self.show_warning("Run SPV analysis before saving.")
            return
        folder = self.choose_output_folder()
        if not folder:
            return
        prefix = self.tc_spv_prefix.GetValue().strip() or "SPV"
        try:
            path1 = save_spv_csv(self.spv_result.data, folder, prefix)
            path2 = save_normalized_spv_csv(self.spv_result.data, folder, f"{prefix}_normalized")
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.log(f"Saved SPV CSVs: {path1}; {path2}")
        log_usage_event(self, "spv_results_saved", file_metadata(path1))

    def choose_output_folder(self):
        with wx.DirDialog(self, "Choose output folder", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return ""
            return dialog.GetPath()

    def read_dwf_settings(self):
        self.ref_aps_fit_domain = "energy"
        return DwfSettings(
            ref_aps_fit_lower_bound=self.parse_float(self.tc_ref_aps_fit_lower, "Reference APS fit lower", allow_zero=True),
            ref_aps_fit_upper_bound=self.parse_float(self.tc_ref_aps_fit_upper, "Reference APS fit upper"),
            ref_aps_fit_points=10,
            ref_dwf_stat_length_s=self.parse_float(self.tc_ref_dwf_stat, "Reference DWF statistic length"),
            sample_dwf_stat_length_s=self.parse_float(self.tc_sample_dwf_stat, "Sample DWF statistic length"),
            ref_aps_fit_domain=self.ref_aps_fit_domain,
        )

    def read_aps_settings(self):
        self.aps_fit_domain = "energy"
        return ApsFitSettings(
            fit_lower_bound=self.parse_float(self.tc_aps_fit_lower, "APS fit lower", allow_zero=True),
            fit_upper_bound=self.parse_float(self.tc_aps_fit_upper, "APS fit upper"),
            points=7,
            sqrt=False,
            fit_domain=self.aps_fit_domain,
        )

    def read_dos_settings(self):
        return DosSmoothSettings(
            window_length=self.parse_int(self.tc_dos_window, "DOS smoothing window"),
            polyorder=self.parse_int(self.tc_dos_poly, "DOS smoothing polynomial"),
            scale=self.parse_float(self.tc_dos_scale, "DOS smoothing scale"),
            y0=self.parse_float(self.tc_dos_y0, "DOS smoothing y0", allow_zero=True),
        )

    def read_spv_settings(self):
        repeats = self.parse_int(self.tc_spv_repeats, "SPV repeats")
        return SpvSettings(
            timemap=build_spv_timemap(
                self.parse_float(self.tc_spv_initial_dark, "SPV Initial Dark"),
                self.parse_float(self.tc_spv_light1, "SPV Light 1"),
                self.parse_float(self.tc_spv_dark1, "SPV Dark 1"),
                repeats,
            ),
            normalize_zone=1,
        )

    @staticmethod
    def parse_float(ctrl, name, allow_zero=False):
        text = ctrl.GetValue().strip()
        if not text:
            raise ApsAnalysisError(f"{name} is empty.")
        try:
            value = float(text)
        except ValueError as exc:
            raise ApsAnalysisError(f"{name} must be a number.") from exc
        if allow_zero:
            if value < 0:
                raise ApsAnalysisError(f"{name} must be >= 0.")
        elif value <= 0:
            raise ApsAnalysisError(f"{name} must be > 0.")
        return value

    @staticmethod
    def parse_int(ctrl, name):
        text = ctrl.GetValue().strip()
        if not text:
            raise ApsAnalysisError(f"{name} is empty.")
        try:
            return int(text)
        except ValueError as exc:
            raise ApsAnalysisError(f"{name} must be an integer.") from exc

    def clear_all_figures(self):
        for figure, canvas, title in [
            (self.figure_work_preview, self.canvas_work_preview, "Load files to preview workfunction analysis."),
            (self.figure_aps_preview, self.canvas_aps_preview, "Load APS files to preview APS analysis."),
            (self.figure_dos_results, self.canvas_dos_results, "Run APS analysis to show DOS results."),
            (self.figure_spv_preview, self.canvas_spv_preview, "Load SPV files to preview SPV analysis."),
        ]:
            figure.clear()
            ax = figure.add_subplot(111)
            ax.text(0.5, 0.5, title, ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            canvas.draw()

    def show_warning(self, message):
        wx.MessageBox(message, "APS warning", wx.OK | wx.ICON_WARNING, self)

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.AppendText(f"[{stamp}] {message}\n")
