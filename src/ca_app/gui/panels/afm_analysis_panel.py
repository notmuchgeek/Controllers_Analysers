"""AFM/KPFM CPD image analysis workspace."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import wx
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from ca_app.core.afm_kpfm_analysis import (
    DEFAULT_HOPG_WORK_FUNCTION_EV,
    AfmKpfmAnalysisError,
    Region,
    average_hopg_references,
    average_per_processed_row,
    average_per_processed_row_with_masks,
    build_one_mask_set,
    build_two_mask_set,
    cpd_to_energy,
    first_dark_and_illuminated_regions,
    fit_gaussian_peak_from_values,
    gaussian_height_distribution,
    height_distribution_density,
    histogram,
    image_row_span_for_processed_region,
    load_cpd_image,
    load_mask,
    processed_region_mask,
    x_values_for_rows,
)
from ca_app.runtime.usage_logger import file_metadata, log_usage_event

COLORMAP_CATEGORIES = {
    "Uniform": ["viridis", "plasma", "inferno", "magma", "cividis"],
    "Sequential": [
        "binary",
        "gist_yarg",
        "gist_gray",
        "gray",
        "bone",
        "pink",
        "spring",
        "summer",
        "autumn",
        "winter",
        "cool",
        "Wistia",
        "hot",
        "afmhot",
        "gist_heat",
        "copper",
    ],
    "Diverging": [
        "PiYG",
        "PRGn",
        "BrBG",
        "PuOr",
        "RdGy",
        "RdBu",
        "RdYlBu",
        "RdYlGn",
        "Spectral",
        "coolwarm",
        "bwr",
        "seismic",
        "berlin",
        "managua",
        "vanimo",
    ],
    "Misc": [
        "flag",
        "prism",
        "ocean",
        "gist_earth",
        "terrain",
        "gist_stern",
        "gnuplot",
        "gnuplot2",
        "CMRmap",
        "cubehelix",
        "brg",
        "gist_rainbow",
        "rainbow",
        "jet",
        "turbo",
        "nipy_spectral",
        "gist_ncar",
    ],
}
DEFAULT_COLORMAP_CATEGORY = "Uniform"
DEFAULT_COLORMAP_NAME = "viridis"


class AfmAnalysisPanel(wx.Panel):
    """KPFM CPD TIFF/PNG analysis panel."""

    def __init__(self, parent):
        super().__init__(parent)
        self.cpd_path = ""
        self.cpd_image = None
        self.hopg_paths = ["", ""]
        self.hopg_images = [None, None]
        self.hopg_fit_params = [None, None]
        self.mask_paths = ["", ""]
        self.loaded_masks = [None, None]
        self.preview_call = None
        self.region_rows = []
        self.setting_controls = False
        self.build_ui()

    def build_ui(self):
        root = wx.BoxSizer(wx.HORIZONTAL)
        root.Add(self.build_left_panel(), 0, wx.EXPAND | wx.ALL, 8)
        root.Add(self.build_right_panel(), 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(root)

    def build_left_panel(self):
        scrolled = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scrolled.SetScrollRate(0, 20)
        scrolled.SetMinSize((530, -1))
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(self.build_cpd_controls(scrolled), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.build_axis_controls(scrolled), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.build_hopg_controls(scrolled), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.build_region_controls(scrolled), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.build_mask_controls(scrolled), 0, wx.EXPAND | wx.ALL, 5)

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_save_parameters = wx.Button(scrolled, label="Save Parameters")
        self.btn_load_parameters = wx.Button(scrolled, label="Load Parameters")
        self.btn_update_preview = wx.Button(scrolled, label="Update")
        self.btn_save_parameters.Bind(wx.EVT_BUTTON, self.on_save_parameters)
        self.btn_load_parameters.Bind(wx.EVT_BUTTON, self.on_load_parameters)
        self.btn_update_preview.Bind(wx.EVT_BUTTON, self.on_update_preview)
        button_row.Add(self.btn_save_parameters, 1, wx.EXPAND | wx.RIGHT, 5)
        button_row.Add(self.btn_load_parameters, 1, wx.EXPAND | wx.RIGHT, 5)
        button_row.Add(self.btn_update_preview, 1, wx.EXPAND)
        sizer.Add(button_row, 0, wx.EXPAND | wx.ALL, 5)

        scrolled.SetSizer(sizer)
        self.update_energy_controls()
        self.update_time_controls()
        self.update_mask_controls()
        self.update_png_controls()
        for index in range(len(self.hopg_rows)):
            self.update_hopg_row_controls(index)
        return scrolled

    def build_cpd_controls(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "CPD image")
        self.btn_load_cpd = wx.Button(parent, label="Load TIFF/PNG")
        self.tc_cpd_file = wx.TextCtrl(parent, value="No CPD image loaded", style=wx.TE_READONLY)
        self.btn_load_cpd.Bind(wx.EVT_BUTTON, self.on_load_cpd)
        box.Add(self.add_load_row(self.btn_load_cpd, self.tc_cpd_file), 0, wx.EXPAND | wx.ALL, 5)

        png_grid = wx.FlexGridSizer(rows=2, cols=2, vgap=6, hgap=6)
        png_grid.AddGrowableCol(1, 1)
        self.tc_png_min = wx.TextCtrl(parent, value="-0.5")
        self.tc_png_max = wx.TextCtrl(parent, value="0.5")
        png_grid.Add(wx.StaticText(parent, label="PNG voltage min / V"), 0, wx.ALIGN_CENTER_VERTICAL)
        png_grid.Add(self.tc_png_min, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        png_grid.Add(wx.StaticText(parent, label="PNG voltage max / V"), 0, wx.ALIGN_CENTER_VERTICAL)
        png_grid.Add(self.tc_png_max, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        box.Add(png_grid, 0, wx.EXPAND | wx.ALL, 5)
        self.tc_png_min.Bind(wx.EVT_TEXT, self.on_png_rescale_changed)
        self.tc_png_max.Bind(wx.EVT_TEXT, self.on_png_rescale_changed)

        cmap_row = wx.BoxSizer(wx.HORIZONTAL)
        self.choice_cmap_category = wx.Choice(parent, choices=list(COLORMAP_CATEGORIES))
        self.choice_cmap = wx.Choice(parent, choices=COLORMAP_CATEGORIES[DEFAULT_COLORMAP_CATEGORY])
        self.choice_cmap_category.SetStringSelection(DEFAULT_COLORMAP_CATEGORY)
        self.choice_cmap.SetStringSelection(DEFAULT_COLORMAP_NAME)
        self.choice_cmap_category.Bind(wx.EVT_CHOICE, self.on_colormap_category_changed)
        self.choice_cmap.Bind(wx.EVT_CHOICE, self.on_parameter_changed)
        cmap_row.Add(wx.StaticText(parent, label="Colour map"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        cmap_row.Add(self.choice_cmap_category, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        cmap_row.Add(self.choice_cmap, 1, wx.EXPAND)
        box.Add(cmap_row, 0, wx.EXPAND | wx.ALL, 5)
        return box

    def build_axis_controls(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "Axes")

        direction_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_scan_up = wx.RadioButton(parent, label="Up", style=wx.RB_GROUP)
        self.rb_scan_down = wx.RadioButton(parent, label="Down")
        self.rb_scan_up.SetValue(True)
        for radio in [self.rb_scan_up, self.rb_scan_down]:
            radio.Bind(wx.EVT_RADIOBUTTON, self.on_parameter_changed)
        direction_row.Add(wx.StaticText(parent, label="Slow Scan Direction"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        direction_row.Add(self.rb_scan_up, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        direction_row.Add(self.rb_scan_down, 0, wx.ALIGN_CENTER_VERTICAL)
        box.Add(direction_row, 0, wx.EXPAND | wx.ALL, 5)

        x_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_x_row = wx.RadioButton(parent, label="Row", style=wx.RB_GROUP)
        self.rb_x_time = wx.RadioButton(parent, label="Time")
        self.rb_x_row.SetValue(True)
        self.rb_x_row.Bind(wx.EVT_RADIOBUTTON, self.on_x_axis_changed)
        self.rb_x_time.Bind(wx.EVT_RADIOBUTTON, self.on_x_axis_changed)
        x_row.Add(wx.StaticText(parent, label="X axis"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        x_row.Add(self.rb_x_row, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        x_row.Add(self.rb_x_time, 0, wx.ALIGN_CENTER_VERTICAL)
        box.Add(x_row, 0, wx.EXPAND | wx.ALL, 5)

        self.time_grid = wx.FlexGridSizer(rows=2, cols=2, vgap=6, hgap=6)
        self.time_grid.AddGrowableCol(1, 1)
        self.rb_time_scan_rate = wx.RadioButton(parent, label="Scan rate / Hz", style=wx.RB_GROUP)
        self.rb_time_total = wx.RadioButton(parent, label="Total scan time / s")
        self.rb_time_scan_rate.SetValue(True)
        self.tc_scan_rate = wx.TextCtrl(parent, value="0.3")
        self.tc_total_scan_time = wx.TextCtrl(parent, value="")
        self.rb_time_scan_rate.Bind(wx.EVT_RADIOBUTTON, self.on_time_source_changed)
        self.rb_time_total.Bind(wx.EVT_RADIOBUTTON, self.on_time_source_changed)
        self.time_grid.Add(self.rb_time_scan_rate, 0, wx.ALIGN_CENTER_VERTICAL)
        self.time_grid.Add(self.tc_scan_rate, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        self.time_grid.Add(self.rb_time_total, 0, wx.ALIGN_CENTER_VERTICAL)
        self.time_grid.Add(self.tc_total_scan_time, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        box.Add(self.time_grid, 0, wx.EXPAND | wx.ALL, 5)
        self.tc_scan_rate.Bind(wx.EVT_TEXT, self.on_parameter_changed)
        self.tc_total_scan_time.Bind(wx.EVT_TEXT, self.on_parameter_changed)

        y_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_y_cpd = wx.RadioButton(parent, label="CPD", style=wx.RB_GROUP)
        self.rb_y_energy = wx.RadioButton(parent, label="Energy")
        self.rb_y_cpd.SetValue(True)
        self.rb_y_cpd.Bind(wx.EVT_RADIOBUTTON, self.on_y_axis_changed)
        self.rb_y_energy.Bind(wx.EVT_RADIOBUTTON, self.on_y_axis_changed)
        y_row.Add(wx.StaticText(parent, label="Y axis"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        y_row.Add(self.rb_y_cpd, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        y_row.Add(self.rb_y_energy, 0, wx.ALIGN_CENTER_VERTICAL)
        box.Add(y_row, 0, wx.EXPAND | wx.ALL, 5)
        return box

    def build_hopg_controls(self, parent):
        self.hopg_box = wx.StaticBoxSizer(wx.VERTICAL, parent, "HOPG reference")
        grid = wx.FlexGridSizer(rows=1, cols=2, vgap=6, hgap=6)
        grid.AddGrowableCol(1, 1)
        self.tc_hopg_work_function = wx.TextCtrl(parent, value=f"{DEFAULT_HOPG_WORK_FUNCTION_EV:g}")
        grid.Add(wx.StaticText(parent, label="HOPG work function / eV"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.tc_hopg_work_function, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        self.hopg_box.Add(grid, 0, wx.EXPAND | wx.ALL, 5)
        self.tc_hopg_work_function.Bind(wx.EVT_TEXT, self.on_parameter_changed)

        header = wx.FlexGridSizer(rows=1, cols=5, vgap=0, hgap=6)
        header.Add(wx.StaticText(parent, label="Use"), 0, wx.ALIGN_CENTER)
        header.Add(wx.StaticText(parent, label="Reference"), 0, wx.EXPAND)
        header.Add(wx.StaticText(parent, label="File"), 0, wx.EXPAND)
        header.Add(wx.StaticText(parent, label="Manual"), 0, wx.ALIGN_CENTER)
        header.Add(wx.StaticText(parent, label="Peak / V"), 0, wx.EXPAND)
        self.hopg_box.Add(header, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)

        self.hopg_rows = []
        for index in range(2):
            row = wx.FlexGridSizer(rows=1, cols=5, vgap=0, hgap=6)
            row.AddGrowableCol(2, 1)
            enabled = wx.CheckBox(parent, label="")
            enabled.SetValue(True)
            enabled.Enable(index == 1)
            button = wx.Button(parent, label=f"Load HOPG {index + 1}")
            filename = wx.TextCtrl(parent, value="No HOPG file loaded", style=wx.TE_READONLY)
            manual = wx.CheckBox(parent, label="")
            manual.SetValue(True)
            peak = wx.TextCtrl(parent, value="")
            peak.SetMinSize((80, -1))
            enabled.Bind(wx.EVT_CHECKBOX, lambda event, i=index: self.on_hopg_enabled_changed(i))
            button.Bind(wx.EVT_BUTTON, lambda event, i=index: self.on_load_hopg(i))
            manual.Bind(wx.EVT_CHECKBOX, lambda event, i=index: self.on_hopg_manual_changed(i))
            peak.Bind(wx.EVT_TEXT, self.on_parameter_changed)
            row.Add(enabled, 0, wx.ALIGN_CENTER)
            row.Add(button, 0, wx.EXPAND)
            row.Add(filename, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
            row.Add(manual, 0, wx.ALIGN_CENTER)
            row.Add(peak, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
            self.hopg_box.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
            self.hopg_rows.append((enabled, button, filename, manual, peak))
        return self.hopg_box

    def build_region_controls(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "Illuminated region")
        self.region_rows_panel = wx.Panel(parent)
        self.region_rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self.region_rows_panel.SetSizer(self.region_rows_sizer)
        header = wx.FlexGridSizer(rows=1, cols=2, vgap=0, hgap=6)
        header.AddGrowableCol(0, 1)
        header.AddGrowableCol(1, 1)
        header.Add(wx.StaticText(self.region_rows_panel, label="Start row"), 0, wx.EXPAND)
        header.Add(wx.StaticText(self.region_rows_panel, label="End row"), 0, wx.EXPAND)
        self.region_rows_sizer.Add(header, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.add_region_row("", "")
        box.Add(self.region_rows_panel, 0, wx.EXPAND)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_region = wx.Button(parent, label="Add")
        self.btn_delete_region = wx.Button(parent, label="Delete")
        self.btn_add_region.Bind(wx.EVT_BUTTON, self.on_add_region)
        self.btn_delete_region.Bind(wx.EVT_BUTTON, self.on_delete_region)
        buttons.Add(self.btn_add_region, 1, wx.EXPAND | wx.RIGHT, 5)
        buttons.Add(self.btn_delete_region, 1, wx.EXPAND)
        box.Add(buttons, 0, wx.EXPAND | wx.ALL, 5)
        return box

    def build_mask_controls(self, parent):
        box = wx.StaticBoxSizer(wx.VERTICAL, parent, "Mask")
        self.cb_enable_masks = wx.CheckBox(parent, label="Use masks")
        self.cb_enable_masks.Bind(wx.EVT_CHECKBOX, self.on_mask_mode_changed)
        box.Add(self.cb_enable_masks, 0, wx.ALL, 5)

        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_one_mask = wx.RadioButton(parent, label="One mask", style=wx.RB_GROUP)
        self.rb_two_masks = wx.RadioButton(parent, label="Two masks")
        self.rb_one_mask.SetValue(True)
        self.rb_one_mask.Bind(wx.EVT_RADIOBUTTON, self.on_mask_mode_changed)
        self.rb_two_masks.Bind(wx.EVT_RADIOBUTTON, self.on_mask_mode_changed)
        mode_row.Add(self.rb_one_mask, 0, wx.RIGHT, 16)
        mode_row.Add(self.rb_two_masks, 0)
        box.Add(mode_row, 0, wx.EXPAND | wx.ALL, 5)

        self.btn_load_mask1 = wx.Button(parent, label="Load mask")
        self.tc_mask1_file = wx.TextCtrl(parent, value="No mask loaded", style=wx.TE_READONLY)
        self.btn_load_mask1.Bind(wx.EVT_BUTTON, lambda event: self.on_load_mask(0))
        box.Add(self.add_load_row(self.btn_load_mask1, self.tc_mask1_file), 0, wx.EXPAND | wx.ALL, 5)

        self.btn_load_mask2 = wx.Button(parent, label="Load lower mask")
        self.tc_mask2_file = wx.TextCtrl(parent, value="No lower mask loaded", style=wx.TE_READONLY)
        self.btn_load_mask2.Bind(wx.EVT_BUTTON, lambda event: self.on_load_mask(1))
        box.Add(self.add_load_row(self.btn_load_mask2, self.tc_mask2_file), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        return box

    def build_right_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.preview_notebook = wx.Notebook(panel)
        self.figure_image, self.canvas_image = self.add_preview_page("CPD Image", figsize=(8, 7))
        self.figure_profile, self.canvas_profile = self.add_preview_page("Profile", figsize=(8, 7))
        self.figure_masks, self.canvas_masks = self.add_preview_page("Masks", figsize=(8, 6))
        self.figure_hopg, self.canvas_hopg = self.add_preview_page("HOPG Fit", figsize=(8, 5))
        sizer.Add(self.preview_notebook, 1, wx.EXPAND)

        log_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "AFM/KPFM analysis log")
        self.log_box = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.log_box.SetMinSize((-1, 105))
        log_box.Add(self.log_box, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(log_box, 0, wx.EXPAND | wx.TOP, 6)
        panel.SetSizer(sizer)
        self.clear_all_previews()
        return panel

    def add_preview_page(self, title, figsize):
        panel = wx.Panel(self.preview_notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        figure = Figure(figsize=figsize)
        canvas = FigureCanvasWxAgg(panel, -1, figure)
        sizer.Add(canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self.preview_notebook.AddPage(panel, title)
        return figure, canvas

    @staticmethod
    def add_load_row(button, text_ctrl):
        button.SetMinSize((135, -1))
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(button, 0, wx.RIGHT, 6)
        row.Add(text_ctrl, 1, wx.ALIGN_CENTER_VERTICAL)
        return row

    def add_region_row(self, start="", end=""):
        row_panel = wx.Panel(self.region_rows_panel)
        row = wx.FlexGridSizer(rows=1, cols=2, vgap=0, hgap=6)
        row.AddGrowableCol(0, 1)
        row.AddGrowableCol(1, 1)
        start_ctrl = wx.TextCtrl(row_panel, value=str(start))
        end_ctrl = wx.TextCtrl(row_panel, value=str(end))
        start_ctrl.Bind(wx.EVT_TEXT, self.on_parameter_changed)
        end_ctrl.Bind(wx.EVT_TEXT, self.on_parameter_changed)
        row.Add(start_ctrl, 0, wx.EXPAND)
        row.Add(end_ctrl, 0, wx.EXPAND)
        row_panel.SetSizer(row)
        self.region_rows_sizer.Add(row_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.region_rows.append((row_panel, start_ctrl, end_ctrl))

    def on_add_region(self, event):
        self.add_region_row("", "")
        self.region_rows_panel.Layout()
        self.Layout()
        self.force_preview_update(show_errors=False)

    def on_delete_region(self, event):
        if len(self.region_rows) <= 1:
            self.show_warning("At least one illuminated-region row is required.")
            return
        row_panel, _, _ = self.region_rows.pop()
        self.region_rows_sizer.Detach(row_panel)
        row_panel.Destroy()
        self.region_rows_panel.Layout()
        self.Layout()
        self.force_preview_update(show_errors=False)

    def on_load_cpd(self, event):
        with wx.FileDialog(
            self,
            "Load CPD TIFF/PNG image",
            wildcard="Image files (*.tif;*.tiff;*.png)|*.tif;*.tiff;*.png|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            image = self.load_image_with_current_png_scale(path)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.cpd_path = path
        self.cpd_image = image
        self.set_file_text(self.tc_cpd_file, path)
        self.update_png_controls()
        self.log_loaded_image("Loaded CPD image", image)
        log_usage_event(self, "afm_analysis_cpd_loaded", file_metadata(path))
        self.reload_loaded_masks()
        self.preview_notebook.SetSelection(0)
        self.force_preview_update(show_errors=True)

    def on_png_rescale_changed(self, event):
        if self.setting_controls:
            return
        if self.cpd_path and Path(self.cpd_path).suffix.lower() == ".png":
            try:
                self.cpd_image = self.load_image_with_current_png_scale(self.cpd_path)
                self.log_loaded_image("Rescaled PNG CPD image", self.cpd_image)
            except Exception:
                self.schedule_preview_update()
                return
        self.schedule_preview_update()

    def on_load_hopg(self, index):
        with wx.FileDialog(
            self,
            f"Load HOPG reference {index + 1}",
            wildcard="Image files (*.tif;*.tiff;*.png)|*.tif;*.tiff;*.png|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            peak, params = self.load_hopg_reference_path(index, path)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.log(f"Loaded HOPG {index + 1}: {Path(path).name}; fitted peak={peak:.6g} V, b={params['b']:.4g}.")
        log_usage_event(self, "afm_analysis_hopg_loaded", {"index": index + 1, **file_metadata(path)})
        self.preview_notebook.SetSelection(3)
        self.force_preview_update(show_errors=True)

    def load_hopg_reference_path(self, index, path):
        image = self.load_image_with_current_png_scale(path)
        peak, params = fit_gaussian_peak_from_values(image.values)
        self.hopg_paths[index] = path
        self.hopg_images[index] = image
        self.hopg_fit_params[index] = params
        _, _, filename_ctrl, manual_ctrl, peak_ctrl = self.hopg_rows[index]
        self.set_file_text(filename_ctrl, path)
        manual_ctrl.SetValue(False)
        peak_ctrl.SetValue(f"{peak:.6g}")
        self.update_hopg_row_controls(index)
        return peak, params

    def on_hopg_manual_changed(self, index):
        self.update_hopg_row_controls(index)
        self.force_preview_update(show_errors=False)

    def on_hopg_enabled_changed(self, index):
        self.update_hopg_row_controls(index)
        self.force_preview_update(show_errors=False)

    def on_load_mask(self, index):
        if self.cpd_image is None:
            self.show_warning("Load a CPD image before loading masks.")
            return
        with wx.FileDialog(
            self,
            "Load mask image",
            wildcard="PNG files (*.png)|*.png|Image files (*.png;*.tif;*.tiff)|*.png;*.tif;*.tiff|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            mask = load_mask(path, target_shape=self.cpd_image.values.shape)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.mask_paths[index] = path
        self.loaded_masks[index] = mask
        self.set_file_text(self.tc_mask1_file if index == 0 else self.tc_mask2_file, path)
        self.log(f"Loaded mask {index + 1}: {Path(path).name}.")
        log_usage_event(self, "afm_analysis_mask_loaded", {"index": index + 1, **file_metadata(path)})
        self.force_preview_update(show_errors=True)

    def reload_loaded_masks(self):
        if self.cpd_image is None:
            return
        for index, path in enumerate(self.mask_paths):
            if not path:
                continue
            try:
                self.loaded_masks[index] = load_mask(path, target_shape=self.cpd_image.values.shape)
                self.log(f"Resized mask {index + 1} to CPD image shape {self.cpd_image.values.shape}.")
            except Exception as exc:
                self.loaded_masks[index] = None
                self.log(f"Could not reload mask {index + 1}: {exc}")

    def load_image_with_current_png_scale(self, path):
        suffix = Path(path).suffix.lower()
        if suffix == ".png":
            return load_cpd_image(path, self.parse_float(self.tc_png_min.GetValue(), "PNG voltage min"), self.parse_float(self.tc_png_max.GetValue(), "PNG voltage max"))
        return load_cpd_image(path)

    def on_x_axis_changed(self, event):
        self.update_time_controls()
        self.force_preview_update(show_errors=False)

    def on_time_source_changed(self, event):
        self.update_time_controls()
        self.force_preview_update(show_errors=False)

    def on_y_axis_changed(self, event):
        self.update_energy_controls()
        self.force_preview_update(show_errors=False)

    def on_colormap_category_changed(self, event):
        self.update_colormap_choices()
        self.on_parameter_changed(event)

    def on_mask_mode_changed(self, event):
        self.update_mask_controls()
        self.force_preview_update(show_errors=False)

    def on_parameter_changed(self, event):
        if not self.setting_controls:
            self.schedule_preview_update()

    def on_update_preview(self, event):
        self.force_preview_update(show_errors=True)

    def schedule_preview_update(self):
        if self.preview_call is not None:
            self.preview_call.Stop()
        self.preview_call = wx.CallLater(300, self.force_preview_update, False)

    def force_preview_update(self, show_errors=False):
        self.preview_call = None
        try:
            self.draw_all_previews()
        except Exception as exc:
            self.draw_error(str(exc))
            self.log(f"Preview update failed: {exc}")
            if show_errors:
                self.show_warning(str(exc))

    def draw_all_previews(self):
        if self.cpd_image is None:
            self.clear_all_previews()
            return
        values = self.current_display_values()
        masks = self.current_mask_set(show_missing=False)
        regions = self.current_regions(show_missing=False)
        self.draw_image_preview(values, regions)
        self.draw_profile_preview(values, masks, regions)
        self.draw_mask_preview(values, masks)
        self.draw_hopg_fit_preview()

    def draw_image_preview(self, values, regions):
        self.figure_image.clear()
        vmin, vmax = self.robust_image_limits(values)
        cmap = self.current_image_colormap()
        grid = self.figure_image.add_gridspec(
            2,
            2,
            width_ratios=[1.0, 1.2],
            height_ratios=[1.0, 1.0],
            wspace=0.38,
            hspace=0.34,
        )
        image_grid = grid[0, 0].subgridspec(1, 2, width_ratios=[1.0, 0.055], wspace=0.07)
        region_grid = grid[1, 0].subgridspec(1, 2, width_ratios=[1.0, 0.055], wspace=0.07)
        image_ax = self.figure_image.add_subplot(image_grid[0, 0])
        image_cax = self.figure_image.add_subplot(image_grid[0, 1])
        hist_ax = self.figure_image.add_subplot(grid[0, 1])
        region_ax = self.figure_image.add_subplot(region_grid[0, 0])
        region_cax = self.figure_image.add_subplot(region_grid[0, 1])
        region_hist_ax = self.figure_image.add_subplot(grid[1, 1])

        im = image_ax.imshow(values, cmap=cmap, origin="upper", aspect="equal", vmin=vmin, vmax=vmax)
        image_ax.set_box_aspect(1)
        image_ax.set_title("Loaded image")
        image_ax.set_xlabel("Column")
        self.apply_processed_y_axis(image_ax, values.shape[0])
        self.figure_image.colorbar(im, cax=image_cax)

        counts, edges = histogram(values)
        hist_ax.bar(edges[:-1], counts, width=np.diff(edges), color="0.55", alpha=0.7)
        hist_ax.set_title("Full image histogram")
        hist_ax.set_xlabel(self.value_axis_label())
        hist_ax.set_ylabel("Pixel count")

        region_im = region_ax.imshow(values, cmap=cmap, origin="upper", aspect="equal", vmin=vmin, vmax=vmax)
        region_ax.set_box_aspect(1)
        region_ax.set_title("Dark and illuminated regions")
        region_ax.set_xlabel("Column")
        self.apply_processed_y_axis(region_ax, values.shape[0])
        self.figure_image.colorbar(region_im, cax=region_cax)
        num_rows = values.shape[0]
        dark, light = first_dark_and_illuminated_regions(regions, num_rows)
        for region, label, linestyle in [(dark, "Dark", "-"), (light, "Illuminated", "--")]:
            if region is None:
                continue
            row_start, row_end = image_row_span_for_processed_region(region, num_rows, self.current_direction())
            rect = Rectangle(
                (0, row_start - 0.5),
                values.shape[1],
                row_end - row_start + 1,
                fill=False,
                edgecolor="red",
                linestyle=linestyle,
                linewidth=2,
                label=label,
            )
            region_ax.add_patch(rect)
        if region_ax.patches:
            region_ax.legend(fontsize=8)

        ordered = values[::-1, :] if self.current_direction() == "up" else values
        plotted = False
        for region, label, color in [(dark, "Dark", "0.25"), (light, "Illuminated", "gold")]:
            if region is None:
                continue
            row_mask = processed_region_mask(region, num_rows)
            selected = ordered[row_mask, :]
            if np.any(np.isfinite(selected)):
                counts, edges = histogram(selected)
                region_hist_ax.step(edges[:-1], counts, where="post", label=label, color=color)
                plotted = True
        region_hist_ax.set_title("Dark vs illuminated histogram")
        region_hist_ax.set_xlabel(self.value_axis_label())
        region_hist_ax.set_ylabel("Pixel count")
        if plotted:
            region_hist_ax.legend(fontsize=8)
        else:
            region_hist_ax.text(0.5, 0.5, "Enter an illuminated region to compare histograms.", ha="center", va="center", transform=region_hist_ax.transAxes)
            region_hist_ax.set_axis_off()
        self.canvas_image.draw()

    def draw_profile_preview(self, values, mask_set, regions):
        self.figure_profile.clear()
        hist_ax = self.figure_profile.add_subplot(211)
        profile_ax = self.figure_profile.add_subplot(212)

        counts, edges = histogram(values)
        hist_ax.bar(edges[:-1], counts, width=np.diff(edges), color="0.55", alpha=0.7)
        if mask_set is not None:
            colors = self.mask_colors(mask_set.labels)
            for label, mask, color in zip(mask_set.labels, mask_set.masks, colors):
                valid = mask & np.isfinite(values)
                if np.any(valid):
                    mask_counts, mask_edges = histogram(values[valid], value_range=(float(edges[0]), float(edges[-1])))
                    hist_ax.step(mask_edges[:-1], mask_counts, where="post", color=color, linewidth=1.4, label=label)
        hist_ax.set_title("Voltage distribution")
        hist_ax.set_xlabel(self.value_axis_label())
        hist_ax.set_ylabel("Pixel count")
        if mask_set is not None:
            hist_ax.legend(fontsize=8)

        direction = self.current_direction()
        x_values = self.current_x_values(values.shape[0])
        whole_profile = average_per_processed_row(values, direction)
        profile_ax.plot(x_values, whole_profile, label="Whole image", color="black", marker=".", linewidth=1.0)
        if mask_set is not None:
            colors = self.mask_colors(mask_set.labels)
            for label, profile, color in zip(
                mask_set.labels,
                average_per_processed_row_with_masks(values, mask_set.masks, direction),
                colors,
            ):
                profile_ax.plot(x_values, profile, label=label, color=color, marker=".", linestyle="--", linewidth=1.0)

        for region in regions:
            start = max(1, region.start_row)
            end = min(values.shape[0], region.end_row)
            if start > end:
                continue
            if self.current_x_mode() == "row":
                span_start, span_end = start, end
            else:
                span_start, span_end = x_values[start - 1], x_values[end - 1]
            profile_ax.axvspan(span_start, span_end, color="yellow", alpha=0.25)
        profile_ax.set_title(f"{self.value_name()} over {self.current_x_mode()}")
        profile_ax.set_xlabel("Row number" if self.current_x_mode() == "row" else "Time / s")
        profile_ax.set_ylabel(self.value_axis_label())
        profile_ax.grid(True)
        profile_ax.legend(fontsize=8)
        self.figure_profile.tight_layout(pad=1.2)
        self.canvas_profile.draw()

    def apply_processed_y_axis(self, ax, num_rows):
        if num_rows <= 1:
            ticks = np.array([0.0])
        else:
            ticks = np.linspace(0, num_rows - 1, min(6, num_rows))
        if self.current_direction() == "up":
            labels = [f"{int(round(num_rows - 1 - tick))}" for tick in ticks]
        else:
            labels = [f"{int(round(tick))}" for tick in ticks]
        ax.set_yticks(ticks)
        ax.set_yticklabels(labels)
        ax.set_ylabel("Processed row")

    @staticmethod
    def mask_colors(labels):
        palette = {
            "Upper": "tab:blue",
            "Middle": "tab:green",
            "Lower": "tab:red",
            "Mask": "tab:blue",
            "Inverse": "tab:orange",
        }
        return [palette.get(label, color) for label, color in zip(labels, ["tab:blue", "tab:green", "tab:red", "tab:orange"])]

    def current_colormap_category(self):
        category = self.choice_cmap_category.GetStringSelection()
        return category if category in COLORMAP_CATEGORIES else DEFAULT_COLORMAP_CATEGORY

    def current_colormap_name(self):
        category = self.current_colormap_category()
        name = self.choice_cmap.GetStringSelection()
        if name in COLORMAP_CATEGORIES[category]:
            return name
        if DEFAULT_COLORMAP_NAME in COLORMAP_CATEGORIES[category]:
            return DEFAULT_COLORMAP_NAME
        return COLORMAP_CATEGORIES[category][0]

    def current_image_colormap(self):
        name = self.current_colormap_name()
        return f"{name}_r" if self.rb_y_cpd.GetValue() else name

    def update_colormap_choices(self, category=None, selected=None):
        if category not in COLORMAP_CATEGORIES:
            category = self.current_colormap_category()
        maps = COLORMAP_CATEGORIES[category]
        if selected not in maps:
            current = self.choice_cmap.GetStringSelection()
            selected = current if current in maps else DEFAULT_COLORMAP_NAME
        if selected not in maps:
            selected = maps[0]
        self.choice_cmap_category.SetStringSelection(category)
        self.choice_cmap.Set(maps)
        self.choice_cmap.SetStringSelection(selected)

    @staticmethod
    def robust_image_limits(values, lower_percentile=1.0, upper_percentile=99.0):
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size == 0:
            return 0.0, 1.0
        vmin, vmax = np.nanpercentile(finite, [lower_percentile, upper_percentile])
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
            vmin = float(np.nanmin(finite))
            vmax = float(np.nanmax(finite))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
            center = float(finite[0])
            delta = max(abs(center) * 1e-6, 1e-6)
            return center - delta, center + delta
        return float(vmin), float(vmax)

    def draw_mask_preview(self, values, mask_set):
        self.figure_masks.clear()
        if mask_set is None:
            ax = self.figure_masks.add_subplot(111)
            ax.text(0.5, 0.5, "Enable and load masks to preview mask regions.", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            self.canvas_masks.draw()
            return
        count = len(mask_set.masks)
        vmin, vmax = self.robust_image_limits(values)
        cmap = self.current_image_colormap()
        for index, (label, mask) in enumerate(zip(mask_set.labels, mask_set.masks), start=1):
            ax = self.figure_masks.add_subplot(1, count, index)
            im = ax.imshow(values, cmap=cmap, origin="upper", aspect="equal", vmin=vmin, vmax=vmax)
            overlay = np.ma.masked_where(~mask, np.ones_like(mask, dtype=float))
            ax.imshow(overlay, cmap=ListedColormap(["red"]), alpha=0.42, origin="upper", aspect="equal", vmin=0, vmax=1)
            ax.set_box_aspect(1)
            ax.set_title(label)
            ax.set_xticks([])
            ax.set_yticks([])
            self.figure_masks.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        self.figure_masks.tight_layout(pad=1.2)
        self.canvas_masks.draw()

    def draw_hopg_fit_preview(self):
        self.figure_hopg.clear()
        active = [
            (index, image, params)
            for index, (image, params) in enumerate(zip(self.hopg_images, self.hopg_fit_params))
            if self.hopg_reference_enabled(index) and image is not None and params is not None
        ]
        tip_values = self.active_hopg_tip_work_functions()
        if not active:
            ax = self.figure_hopg.add_subplot(111)
            if tip_values:
                if len(tip_values) == 1:
                    message = f"Calculated tip work function: {tip_values[0][1]:.6g} eV\nLoad a HOPG image to preview Gaussian fitting."
                else:
                    average = np.mean([value for _, value in tip_values])
                    message = f"Calculated average tip work function: {average:.6g} eV\nLoad HOPG images to preview Gaussian fitting."
            else:
                message = "Load one or two HOPG reference images to preview Gaussian peak fitting."
            ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            self.canvas_hopg.draw()
            return
        if len(tip_values) == 1:
            self.figure_hopg.suptitle(f"Calculated tip work function: {tip_values[0][1]:.6g} eV", fontsize=11)
        elif len(tip_values) > 1:
            parts = [f"HOPG {index + 1}: {value:.6g} eV" for index, value in tip_values]
            parts.append(f"Average: {np.mean([value for _, value in tip_values]):.6g} eV")
            self.figure_hopg.suptitle("Calculated tip work function - " + "; ".join(parts), fontsize=10)
        for plot_index, (index, image, params) in enumerate(active, start=1):
            ax = self.figure_hopg.add_subplot(1, len(active), plot_index)
            centers, density, _ = height_distribution_density(image.values)
            fit_y = gaussian_height_distribution(centers, params["y0"], params["a"], params["x0"], params["b"])
            ax.plot(centers, density, color="0.35", label="Height distribution density")
            ax.plot(centers, fit_y, color="tab:red", label="Gaussian fit")
            ax.axvline(params["x0"], color="tab:blue", linestyle="--", linewidth=1.0, label=f"x0={params['x0']:.6g} V")
            ax.set_title(f"HOPG {index + 1}")
            ax.set_xlabel("CPD / V")
            ax.set_ylabel("Density")
            ax.grid(True)
            ax.legend(fontsize=8)
        self.figure_hopg.tight_layout(pad=1.2)
        self.canvas_hopg.draw()

    def clear_all_previews(self):
        for figure, canvas, message in [
            (self.figure_image, self.canvas_image, "Load a CPD TIFF or PNG image to start AFM/KPFM analysis."),
            (self.figure_profile, self.canvas_profile, "Load a CPD image to preview row/time profiles."),
            (self.figure_masks, self.canvas_masks, "Enable and load masks to preview mask regions."),
            (self.figure_hopg, self.canvas_hopg, "Load HOPG reference images to preview Gaussian peak fitting."),
        ]:
            figure.clear()
            ax = figure.add_subplot(111)
            ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            canvas.draw()

    def draw_error(self, message):
        for figure, canvas in [
            (self.figure_image, self.canvas_image),
            (self.figure_profile, self.canvas_profile),
            (self.figure_masks, self.canvas_masks),
            (self.figure_hopg, self.canvas_hopg),
        ]:
            figure.clear()
            ax = figure.add_subplot(111)
            ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True, transform=ax.transAxes)
            ax.set_axis_off()
            canvas.draw()

    def current_display_values(self):
        values = np.asarray(self.cpd_image.values, dtype=float)
        if self.rb_y_cpd.GetValue():
            return values
        refs = [peak for _, peak in self.active_hopg_peak_values()]
        hopg_peak = average_hopg_references(refs)
        work_function = self.parse_float(self.tc_hopg_work_function.GetValue(), "HOPG work function")
        return cpd_to_energy(values, work_function, hopg_peak)

    def active_hopg_peak_values(self):
        refs = []
        for index, (_, _, _, manual_ctrl, peak_ctrl) in enumerate(self.hopg_rows):
            if not self.hopg_reference_enabled(index):
                continue
            if manual_ctrl.GetValue():
                text = peak_ctrl.GetValue().strip()
                if text:
                    refs.append((index, self.parse_float(text, "HOPG peak")))
            elif self.hopg_fit_params[index] is not None:
                refs.append((index, float(self.hopg_fit_params[index]["x0"])))
        return refs

    def active_hopg_tip_work_functions(self):
        work_function = self.parse_float(self.tc_hopg_work_function.GetValue(), "HOPG work function")
        return [(index, work_function + peak) for index, peak in self.active_hopg_peak_values()]

    def current_mask_set(self, show_missing):
        if not self.cb_enable_masks.GetValue():
            return None
        if self.cpd_image is None:
            return None
        if self.rb_one_mask.GetValue():
            if self.loaded_masks[0] is None:
                if show_missing:
                    raise AfmKpfmAnalysisError("Load one mask before enabling one-mask mode.")
                return None
            return build_one_mask_set(self.loaded_masks[0], self.cpd_image.values.shape)
        if self.loaded_masks[0] is None or self.loaded_masks[1] is None:
            if show_missing:
                raise AfmKpfmAnalysisError("Load upper and lower masks before enabling two-mask mode.")
            return None
        return build_two_mask_set(self.loaded_masks[0], self.loaded_masks[1], self.cpd_image.values.shape)

    def current_regions(self, show_missing):
        if self.cpd_image is None:
            return []
        regions = []
        for _, start_ctrl, end_ctrl in self.region_rows:
            start_text = start_ctrl.GetValue().strip()
            end_text = end_ctrl.GetValue().strip()
            if not start_text and not end_text:
                continue
            if not start_text or not end_text:
                if show_missing:
                    raise AfmKpfmAnalysisError("Each illuminated region row needs both start and end rows.")
                continue
            regions.append(Region(int(float(start_text)), int(float(end_text))))
        num_rows = self.cpd_image.values.shape[0]
        validated = []
        for region in regions:
            start, end = sorted((region.start_row, region.end_row))
            if start < 1 or end > num_rows:
                if show_missing:
                    raise AfmKpfmAnalysisError(f"Illuminated region {start}-{end} is outside row range 1-{num_rows}.")
                continue
            validated.append(Region(start, end))
        return sorted(validated, key=lambda item: item.start_row)

    def current_x_values(self, num_rows):
        if self.current_x_mode() == "row":
            return x_values_for_rows(num_rows, "row")
        if self.rb_time_total.GetValue():
            total = self.parse_float(self.tc_total_scan_time.GetValue(), "Total scan time")
            return x_values_for_rows(num_rows, "time", total_scan_time_s=total)
        rate = self.parse_float(self.tc_scan_rate.GetValue(), "Scan rate")
        return x_values_for_rows(num_rows, "time", scan_rate_hz=rate)

    def current_direction(self):
        return "up" if self.rb_scan_up.GetValue() else "down"

    def current_x_mode(self):
        return "row" if self.rb_x_row.GetValue() else "time"

    def value_name(self):
        return "CPD" if self.rb_y_cpd.GetValue() else "Energy"

    def value_axis_label(self):
        return "CPD / V" if self.rb_y_cpd.GetValue() else "Energy / eV"

    def update_energy_controls(self):
        show = self.rb_y_energy.GetValue()
        self.hopg_box.ShowItems(show)
        self.Layout()

    def update_time_controls(self):
        show = self.rb_x_time.GetValue()
        self.time_grid.ShowItems(show)
        self.rb_time_scan_rate.Show(show)
        self.rb_time_total.Show(show)
        use_rate = show and self.rb_time_scan_rate.GetValue()
        use_total = show and self.rb_time_total.GetValue()
        self.tc_scan_rate.Enable(use_rate)
        self.tc_total_scan_time.Enable(use_total)
        self.Layout()

    def update_png_controls(self):
        is_tiff = bool(self.cpd_path) and Path(self.cpd_path).suffix.lower() in {".tif", ".tiff"}
        self.tc_png_min.Enable(not is_tiff)
        self.tc_png_max.Enable(not is_tiff)

    def update_hopg_row_controls(self, index):
        enabled_ctrl, button, filename_ctrl, manual_ctrl, peak_ctrl = self.hopg_rows[index]
        active = self.hopg_reference_enabled(index)
        button.Enable(active)
        filename_ctrl.Enable(active)
        manual_ctrl.Enable(active)
        peak_ctrl.Enable(active and manual_ctrl.GetValue())

    def hopg_reference_enabled(self, index):
        if index == 0:
            return True
        return self.hopg_rows[index][0].GetValue()

    def update_mask_controls(self):
        enabled = self.cb_enable_masks.GetValue()
        two_masks = self.rb_two_masks.GetValue()
        for ctrl in [self.rb_one_mask, self.rb_two_masks, self.btn_load_mask1, self.tc_mask1_file]:
            ctrl.Enable(enabled)
        self.btn_load_mask1.SetLabel("Load upper mask" if two_masks else "Load mask")
        self.tc_mask2_file.Show(enabled and two_masks)
        self.btn_load_mask2.Show(enabled and two_masks)
        self.Layout()

    def log_loaded_image(self, prefix, image):
        values = image.values
        self.log(
            f"{prefix}: {Path(image.path).name}; shape={values.shape}, "
            f"min={np.nanmin(values):.6g}, max={np.nanmax(values):.6g}, source={image.source}."
        )
        if image.source == "tiff":
            self.log(
                "Selected TIFF tag "
                f"{image.metadata.get('tag_id')} ({image.metadata.get('dtype')}), "
                f"candidate count={image.metadata.get('candidate_count')}."
            )
            if image.metadata.get("flipped_vertical"):
                self.log("TIFF raw CPD array was flipped vertically immediately after loading.")

    def collect_parameters(self):
        return {
            "analysis": "afm_kpfm_image",
            "version": 1,
            "cpd_path": self.cpd_path,
            "png_voltage_min": self.tc_png_min.GetValue(),
            "png_voltage_max": self.tc_png_max.GetValue(),
            "colormap_category": self.current_colormap_category(),
            "colormap_name": self.current_colormap_name(),
            "scan_direction": self.current_direction(),
            "x_axis": self.current_x_mode(),
            "time_source": "total" if self.rb_time_total.GetValue() else "scan_rate",
            "scan_rate_hz": self.tc_scan_rate.GetValue(),
            "total_scan_time_s": self.tc_total_scan_time.GetValue(),
            "y_axis": "energy" if self.rb_y_energy.GetValue() else "cpd",
            "hopg_work_function_ev": self.tc_hopg_work_function.GetValue(),
            "hopg_references": [
                {
                    "path": self.hopg_paths[index],
                    "enabled": enabled_ctrl.GetValue(),
                    "manual": manual_ctrl.GetValue(),
                    "peak_v": peak_ctrl.GetValue(),
                }
                for index, (enabled_ctrl, _, _, manual_ctrl, peak_ctrl) in enumerate(self.hopg_rows)
            ],
            "illuminated_regions": [
                {"start_row": start_ctrl.GetValue(), "end_row": end_ctrl.GetValue()}
                for _, start_ctrl, end_ctrl in self.region_rows
            ],
            "masks_enabled": self.cb_enable_masks.GetValue(),
            "mask_mode": "two" if self.rb_two_masks.GetValue() else "one",
            "mask_paths": list(self.mask_paths),
        }

    def apply_parameters(self, params):
        if not isinstance(params, dict):
            raise AfmKpfmAnalysisError("Parameter file must contain a JSON object.")
        self.setting_controls = True
        try:
            self.tc_png_min.SetValue(str(params.get("png_voltage_min", self.tc_png_min.GetValue())))
            self.tc_png_max.SetValue(str(params.get("png_voltage_max", self.tc_png_max.GetValue())))
            category = str(params.get("colormap_category", DEFAULT_COLORMAP_CATEGORY))
            cmap_name = str(params.get("colormap_name", DEFAULT_COLORMAP_NAME))
            if category not in COLORMAP_CATEGORIES:
                category = DEFAULT_COLORMAP_CATEGORY
            if cmap_name not in COLORMAP_CATEGORIES[category]:
                cmap_name = DEFAULT_COLORMAP_NAME if DEFAULT_COLORMAP_NAME in COLORMAP_CATEGORIES[category] else COLORMAP_CATEGORIES[category][0]
            self.update_colormap_choices(category, cmap_name)
            direction = str(params.get("scan_direction", "up"))
            self.rb_scan_up.SetValue(direction == "up")
            self.rb_scan_down.SetValue(direction != "up")
            x_axis = str(params.get("x_axis", "row"))
            self.rb_x_row.SetValue(x_axis != "time")
            self.rb_x_time.SetValue(x_axis == "time")
            time_source = str(params.get("time_source", "scan_rate"))
            self.rb_time_scan_rate.SetValue(time_source != "total")
            self.rb_time_total.SetValue(time_source == "total")
            self.tc_scan_rate.SetValue(str(params.get("scan_rate_hz", self.tc_scan_rate.GetValue())))
            self.tc_total_scan_time.SetValue(str(params.get("total_scan_time_s", self.tc_total_scan_time.GetValue())))
            y_axis = str(params.get("y_axis", "cpd"))
            self.rb_y_cpd.SetValue(y_axis != "energy")
            self.rb_y_energy.SetValue(y_axis == "energy")
            self.tc_hopg_work_function.SetValue(str(params.get("hopg_work_function_ev", self.tc_hopg_work_function.GetValue())))

            self.clear_region_rows()
            regions = params.get("illuminated_regions") or [{"start_row": "", "end_row": ""}]
            for region in regions:
                self.add_region_row(str(region.get("start_row", "")), str(region.get("end_row", "")))

            self.cb_enable_masks.SetValue(bool(params.get("masks_enabled", False)))
            mask_mode = str(params.get("mask_mode", "one"))
            self.rb_one_mask.SetValue(mask_mode != "two")
            self.rb_two_masks.SetValue(mask_mode == "two")

            for index, row in enumerate(params.get("hopg_references", [])[:2]):
                enabled_ctrl, _, filename_ctrl, manual_ctrl, peak_ctrl = self.hopg_rows[index]
                self.hopg_paths[index] = ""
                self.hopg_images[index] = None
                self.hopg_fit_params[index] = None
                filename_ctrl.SetValue("No HOPG file loaded")
                filename_ctrl.SetToolTip("")
                peak_ctrl.SetValue(str(row.get("peak_v", "")))
                enabled_ctrl.SetValue(bool(row.get("enabled", True)))
                if index == 0:
                    enabled_ctrl.SetValue(True)
                manual_ctrl.SetValue(bool(row.get("manual", True)))
        finally:
            self.setting_controls = False

        cpd_path = str(params.get("cpd_path", "") or "")
        if cpd_path:
            self.cpd_image = self.load_image_with_current_png_scale(cpd_path)
            self.cpd_path = cpd_path
            self.set_file_text(self.tc_cpd_file, cpd_path)
            self.log_loaded_image("Loaded CPD image from parameters", self.cpd_image)

        for index, row in enumerate(params.get("hopg_references", [])[:2]):
            path = str(row.get("path", "") or "")
            if path:
                try:
                    self.load_hopg_reference_path(index, path)
                except Exception as exc:
                    self.log(f"Could not load HOPG {index + 1} from parameters: {exc}")
            enabled_ctrl, _, _, manual_ctrl, peak_ctrl = self.hopg_rows[index]
            enabled_ctrl.SetValue(bool(row.get("enabled", True)))
            if index == 0:
                enabled_ctrl.SetValue(True)
            manual_ctrl.SetValue(bool(row.get("manual", True)))
            peak_ctrl.SetValue(str(row.get("peak_v", peak_ctrl.GetValue())))
            self.update_hopg_row_controls(index)

        self.mask_paths = ["", ""]
        self.loaded_masks = [None, None]
        for index, path in enumerate((params.get("mask_paths") or [])[:2]):
            if not path:
                continue
            self.mask_paths[index] = str(path)
            text_ctrl = self.tc_mask1_file if index == 0 else self.tc_mask2_file
            self.set_file_text(text_ctrl, path)
        self.reload_loaded_masks()

        self.update_energy_controls()
        self.update_time_controls()
        self.update_mask_controls()
        self.update_png_controls()
        self.region_rows_panel.Layout()
        self.Layout()
        self.force_preview_update(show_errors=True)

    def clear_region_rows(self):
        for row_panel, _, _ in list(self.region_rows):
            self.region_rows_sizer.Detach(row_panel)
            row_panel.Destroy()
        self.region_rows.clear()

    def on_save_parameters(self, event):
        default_name = f"afm_kpfm_analysis_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with wx.FileDialog(
            self,
            "Save AFM/KPFM analysis parameters",
            wildcard="JSON files (*.json)|*.json",
            defaultFile=default_name,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(self.collect_parameters(), handle, indent=2)
        except Exception as exc:
            self.show_warning(f"Could not save parameters:\n{exc}")
            return
        self.log(f"Saved AFM/KPFM analysis parameters: {path}")
        log_usage_event(self, "afm_analysis_parameters_saved", file_metadata(path))

    def on_load_parameters(self, event):
        with wx.FileDialog(
            self,
            "Load AFM/KPFM analysis parameters",
            wildcard="JSON files (*.json)|*.json|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                params = json.load(handle)
            self.apply_parameters(params)
        except Exception as exc:
            self.show_warning(f"Could not load parameters:\n{exc}")
            return
        self.log(f"Loaded AFM/KPFM analysis parameters: {path}")
        log_usage_event(self, "afm_analysis_parameters_loaded", file_metadata(path))

    @staticmethod
    def parse_float(text, name):
        try:
            value = float(text)
        except ValueError as exc:
            raise AfmKpfmAnalysisError(f"{name} must be a number.") from exc
        if not np.isfinite(value):
            raise AfmKpfmAnalysisError(f"{name} must be finite.")
        return value

    @staticmethod
    def set_file_text(text_ctrl, path):
        name = Path(path).name
        text_ctrl.SetValue(name)
        text_ctrl.SetToolTip(str(path))

    def show_warning(self, message):
        wx.MessageBox(message, "AFM/KPFM analysis warning", wx.OK | wx.ICON_WARNING, self)

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.AppendText(f"[{stamp}] {message}\n")
