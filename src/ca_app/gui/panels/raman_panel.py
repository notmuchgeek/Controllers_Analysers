"""Raman analysis workspace panel."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

import wx
import wx.grid as wxgrid
import numpy as np
from matplotlib import colormaps
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg
from matplotlib.figure import Figure

from ca_app.core.aps_analysis import dwf_preview_percent_from_slider
from ca_app.core.raman_electrical import (
    DEFAULT_PREVIEW_SECONDS,
    DRAIN_CURRENT_COL,
    DRAIN_TIME_COL,
    DRAIN_VOLTAGE_COL,
    GATE_CURRENT_COL,
    GATE_TIME_COL,
    GATE_VOLTAGE_COL,
    RamanElectricalData,
    load_electrical_csv,
    summarize_electrical_data,
    summary_table_rows,
)
from ca_app.core.raman_insitu_echem import (
    DEFAULT_PEAK_WINDOWS,
    DEFAULT_RAMAN_RANGE_MAX_CM1,
    DEFAULT_RAMAN_RANGE_MIN_CM1,
    DEFAULT_RESULT_SPECTRA_EVERY_N,
    DEFAULT_TIME_OFFSET_S,
    DEFAULT_TIME_PER_SEQUENCE_S,
    DEFAULT_WINDOW_PREVIEW_EVERY_N,
    PeakWindow,
    RamanInsituError,
    analyze_insitu_sequence,
    format_peak_label,
    filter_raman_range,
    legend_title_for_mode,
    load_raman_sequence,
    raman_dataset_to_sequence,
    save_peak_summary_csv,
    save_ratio_csv,
    selected_sequence_values,
    x_label_for_mode,
    x_values_for_mode,
)
from ca_app.core.raman_mapping import (
    RamanDataset,
    RamanMappingError,
    build_unstacked_table,
    export_origin_txt,
    export_selected_sequence_txt,
    image_from_dataset,
    load_raman_data,
    parse_selected_spectra,
)
from ca_app.core.raman_baseline import (
    ASPLS_K_VALUES,
    ASPLS_LAMBDA_VALUES,
    BACKCOR_ORDER_VALUES,
    BACKCOR_THRESHOLD_VALUES,
    DEFAULT_BACKCOR_BELOW_BASELINE_FRACTION,
    DRPLS_ETA_VALUES,
    DRPLS_LAMBDA_VALUES,
    METHOD_ASPLS,
    METHOD_BACKCOR,
    METHOD_DRPLS,
    RamanBaselineError,
    RamanBaselineSettings,
    default_output_name,
    fit_raman_baseline,
    interpolate_to_reference_x,
    parse_numeric_list,
    read_raman_txt,
    save_corrected_txt,
)


class RamanAnalysisPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.build_ui()

    def build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)
        self.substrate_page = RamanSubstrateBaselinePanel(self.notebook)
        self.insitu_page = RamanInsituEchemPanel(self.notebook)
        self.mapping_page = RamanMappingPanel(self.notebook, self)
        self.electrical_page = RamanElectricalPanel(self.notebook)
        self.notebook.AddPage(self.substrate_page, "Baseline")
        self.notebook.AddPage(self.mapping_page, "Mapping")
        self.notebook.AddPage(self.insitu_page, "Insitu EChem")
        self.notebook.AddPage(self.electrical_page, "Electrical")
        sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def build_placeholder_tab(self, title):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(panel, label=f"{title} analysis")
        font = label.GetFont()
        font.SetPointSize(font.GetPointSize() + 4)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        label.SetFont(font)
        message = wx.StaticText(panel, label="This Raman analysis method is reserved for a future implementation.")
        sizer.AddStretchSpacer(1)
        sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 12)
        sizer.Add(message, 0, wx.ALIGN_CENTER | wx.BOTTOM, 12)
        sizer.AddStretchSpacer(1)
        panel.SetSizer(sizer)
        return panel

    def collect_app_parameters(self):
        return {
            "substrate_baseline": self.substrate_page.collect_app_parameters(),
            "mapping": self.mapping_page.collect_app_parameters(),
            "insitu_echem": self.insitu_page.collect_app_parameters(),
            "electrical": self.electrical_page.collect_app_parameters(),
        }

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        if isinstance(params.get("substrate_baseline"), dict):
            self.substrate_page.apply_app_parameters(params["substrate_baseline"])
        if isinstance(params.get("mapping"), dict):
            self.mapping_page.apply_app_parameters(params["mapping"])
        if isinstance(params.get("insitu_echem"), dict):
            self.insitu_page.apply_app_parameters(params["insitu_echem"])
        if isinstance(params.get("electrical"), dict):
            self.electrical_page.apply_app_parameters(params["electrical"])


def create_readonly_grid(parent):
    grid = wxgrid.Grid(parent)
    grid.CreateGrid(0, 0)
    grid.EnableEditing(False)
    grid.EnableDragGridSize(False)
    grid.SetRowLabelSize(44)
    grid.SetColLabelSize(24)
    return grid


def populate_grid(grid, headers, rows):
    current_rows = grid.GetNumberRows()
    current_cols = grid.GetNumberCols()
    target_rows = len(rows)
    target_cols = len(headers)
    if current_rows < target_rows:
        grid.AppendRows(target_rows - current_rows)
    elif current_rows > target_rows:
        grid.DeleteRows(0, current_rows - target_rows)
    if current_cols < target_cols:
        grid.AppendCols(target_cols - current_cols)
    elif current_cols > target_cols:
        grid.DeleteCols(0, current_cols - target_cols)
    for col, header in enumerate(headers):
        grid.SetColLabelValue(col, str(header))
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            grid.SetCellValue(row_index, col_index, str(value))
    grid.AutoSizeColumns(setAsMin=True)


def clear_grid(grid, message):
    populate_grid(grid, ["Preview"], [[message]])


class RamanMappingPanel(wx.Panel):
    def __init__(self, parent, raman_panel):
        super().__init__(parent)
        self.raman_panel = raman_panel
        self.raw_path = ""
        self.dataset: RamanDataset | None = None
        self.preview_call = None
        self.build_ui()

    def build_ui(self):
        root = wx.BoxSizer(wx.HORIZONTAL)
        root.Add(self.build_left_panel(), 0, wx.EXPAND | wx.ALL, 8)
        root.Add(self.build_right_panel(), 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(root)

    def build_left_panel(self):
        scrolled = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scrolled.SetScrollRate(0, 20)
        scrolled.SetMinSize((520, -1))
        sizer = wx.BoxSizer(wx.VERTICAL)

        params_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Parameters")
        params_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_save_params = wx.Button(scrolled, label="Save Parameters")
        self.btn_load_params = wx.Button(scrolled, label="Load Parameters")
        self.btn_save_params.Bind(wx.EVT_BUTTON, self.on_save_parameters)
        self.btn_load_params.Bind(wx.EVT_BUTTON, self.on_load_parameters)
        params_row.Add(self.btn_save_params, 1, wx.EXPAND | wx.RIGHT, 5)
        params_row.Add(self.btn_load_params, 1, wx.EXPAND)
        params_box.Add(params_row, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(params_box, 0, wx.EXPAND | wx.ALL, 5)

        load_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Load file")
        self.btn_load_mapping = wx.Button(scrolled, label="Load wdf/txt")
        self.lbl_mapping_file = wx.TextCtrl(scrolled, value="No Raman mapping file loaded", style=wx.TE_READONLY)
        self.btn_load_mapping.Bind(wx.EVT_BUTTON, self.on_load_file)
        load_box.Add(self.add_load_row(self.btn_load_mapping, self.lbl_mapping_file), 0, wx.EXPAND | wx.ALL, 5)
        preview_row = wx.BoxSizer(wx.HORIZONTAL)
        preview_row.Add(wx.StaticText(scrolled, label="Every N for preview"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.tc_preview_every_n = wx.TextCtrl(scrolled, value="1")
        self.cb_raw_legend = wx.CheckBox(scrolled, label="Legend")
        self.cb_raw_legend.SetValue(False)
        self.tc_preview_every_n.Bind(wx.EVT_TEXT, self.on_preview_controls_changed)
        self.cb_raw_legend.Bind(wx.EVT_CHECKBOX, self.on_preview_controls_changed)
        preview_row.Add(self.tc_preview_every_n, 1, wx.EXPAND | wx.RIGHT, 10)
        preview_row.Add(self.cb_raw_legend, 0, wx.ALIGN_CENTER_VERTICAL)
        load_box.Add(preview_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        sizer.Add(load_box, 0, wx.EXPAND | wx.ALL, 5)

        averaging_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Averaging")
        self.btn_save_origin = wx.Button(scrolled, label="Save")
        self.btn_save_origin.Disable()
        self.btn_save_origin.Bind(wx.EVT_BUTTON, self.on_save_origin)
        averaging_box.Add(self.btn_save_origin, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(averaging_box, 0, wx.EXPAND | wx.ALL, 5)

        select_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Mapping & Selecting")
        range_row = wx.BoxSizer(wx.HORIZONTAL)
        self.tc_range_min = wx.TextCtrl(scrolled, value=f"{DEFAULT_RAMAN_RANGE_MIN_CM1:g}")
        self.tc_range_max = wx.TextCtrl(scrolled, value=f"{DEFAULT_RAMAN_RANGE_MAX_CM1:g}")
        range_row.Add(wx.StaticText(scrolled, label="Min"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        range_row.Add(self.tc_range_min, 1, wx.EXPAND | wx.RIGHT, 10)
        range_row.Add(wx.StaticText(scrolled, label="Max"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        range_row.Add(self.tc_range_max, 1, wx.EXPAND)
        select_box.Add(range_row, 0, wx.EXPAND | wx.ALL, 5)
        selected_grid = wx.FlexGridSizer(rows=1, cols=2, vgap=6, hgap=6)
        selected_grid.AddGrowableCol(1, 1)
        self.tc_selected = wx.TextCtrl(scrolled, value="1,2,3")
        selected_grid.Add(wx.StaticText(scrolled, label="Selected columns"), 0, wx.ALIGN_CENTER_VERTICAL)
        selected_grid.Add(self.tc_selected, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        select_box.Add(selected_grid, 0, wx.EXPAND | wx.ALL, 5)
        self.btn_update = wx.Button(scrolled, label="Update")
        self.btn_update.Bind(wx.EVT_BUTTON, self.on_update)
        select_box.Add(self.btn_update, 0, wx.EXPAND | wx.ALL, 5)
        for ctrl in [self.tc_range_min, self.tc_range_max, self.tc_selected]:
            ctrl.Bind(wx.EVT_TEXT, self.on_selection_text_changed)
        sizer.Add(select_box, 0, wx.EXPAND | wx.ALL, 5)

        save_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Save")
        self.btn_save_selected = wx.Button(scrolled, label="Save selected")
        self.btn_load_to_insitu = wx.Button(scrolled, label="Load to Insitu Echem")
        self.btn_save_selected.Disable()
        self.btn_load_to_insitu.Disable()
        self.btn_save_selected.Bind(wx.EVT_BUTTON, self.on_save_selected)
        self.btn_load_to_insitu.Bind(wx.EVT_BUTTON, self.on_load_to_insitu)
        save_box.Add(self.btn_save_selected, 0, wx.EXPAND | wx.ALL, 5)
        save_box.Add(self.btn_load_to_insitu, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(save_box, 0, wx.EXPAND | wx.ALL, 5)

        scrolled.SetSizer(sizer)
        return scrolled

    def build_right_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.mapping_notebook = wx.Notebook(panel)
        self.avg_panel = wx.Panel(self.mapping_notebook)
        avg_sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid_raw_preview = create_readonly_grid(self.avg_panel)
        self.grid_avg_preview = create_readonly_grid(self.avg_panel)
        avg_sizer.Add(self.grid_raw_preview, 1, wx.EXPAND | wx.ALL, 6)
        avg_sizer.Add(self.grid_avg_preview, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.avg_panel.SetSizer(avg_sizer)
        self.mapping_notebook.AddPage(self.avg_panel, "Avg./Norm.")

        self.figure_raw, self.canvas_raw = self.add_figure_page("Raw data")
        self.figure_location, self.canvas_location = self.add_figure_page("Location")
        self.figure_selected, self.canvas_selected = self.add_figure_page("Selected")
        sizer.Add(self.mapping_notebook, 1, wx.EXPAND)

        log_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Mapping log")
        self.log_box = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.log_box.SetMinSize((-1, 105))
        log_box.Add(self.log_box, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(log_box, 0, wx.EXPAND | wx.TOP, 6)
        panel.SetSizer(sizer)
        self.clear_previews()
        return panel

    def add_figure_page(self, title):
        panel = wx.Panel(self.mapping_notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        figure = Figure(figsize=(8, 6))
        canvas = FigureCanvasWxAgg(panel, -1, figure)
        sizer.Add(canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self.mapping_notebook.AddPage(panel, title)
        return figure, canvas

    @staticmethod
    def add_load_row(button, label):
        button.SetMinSize((135, -1))
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(button, 0, wx.RIGHT, 6)
        row.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        return row

    def collect_parameters(self):
        return {
            "analysis": "mapping",
            "version": 1,
            "raman_range_min_cm1": self.tc_range_min.GetValue(),
            "raman_range_max_cm1": self.tc_range_max.GetValue(),
            "selected_columns": self.tc_selected.GetValue(),
            "preview_every_n": self.tc_preview_every_n.GetValue(),
            "raw_legend": self.cb_raw_legend.GetValue(),
        }

    def apply_parameters(self, params):
        if not isinstance(params, dict):
            raise RamanMappingError("Parameter file must contain a JSON object.")
        self.tc_range_min.SetValue(str(params.get("raman_range_min_cm1", self.tc_range_min.GetValue())))
        self.tc_range_max.SetValue(str(params.get("raman_range_max_cm1", self.tc_range_max.GetValue())))
        self.tc_selected.SetValue(str(params.get("selected_columns", self.tc_selected.GetValue())))
        self.tc_preview_every_n.SetValue(str(params.get("preview_every_n", self.tc_preview_every_n.GetValue())))
        self.cb_raw_legend.SetValue(bool(params.get("raw_legend", self.cb_raw_legend.GetValue())))
        self.update_legend_control()
        if self.dataset is not None:
            self.update_previews()

    def collect_app_parameters(self):
        params = self.collect_parameters()
        params["raw_path"] = self.raw_path
        return params

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        raw_path = str(params.get("raw_path", "") or "")
        if raw_path:
            try:
                self.load_dataset(raw_path)
            except Exception as exc:
                self.raw_path = raw_path
                self.set_loaded_file_display(raw_path)
                self.log(f"Could not restore Mapping file: {exc}")
        self.apply_parameters(params)

    def on_save_parameters(self, event):
        default_name = f"mapping_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with wx.FileDialog(
            self,
            "Save Mapping parameters",
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
        self.log(f"Saved Mapping parameters: {path}")

    def on_load_parameters(self, event):
        with wx.FileDialog(
            self,
            "Load Mapping parameters",
            wildcard="JSON files (*.json)|*.json|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                self.apply_parameters(json.load(handle))
        except Exception as exc:
            self.show_warning(f"Could not load parameters:\n{exc}")
            return
        self.log(f"Loaded Mapping parameters: {path}")

    def on_load_file(self, event):
        with wx.FileDialog(
            self,
            "Load Raman Mapping WDF/TXT file",
            wildcard="Raman files (*.wdf;*.txt)|*.wdf;*.txt|WDF files (*.wdf)|*.wdf|Text files (*.txt)|*.txt|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            self.load_dataset(path)
        except Exception as exc:
            self.show_warning(str(exc))

    def load_dataset(self, path):
        self.dataset = load_raman_data(path, input_mode="auto")
        self.raw_path = str(path)
        self.set_loaded_file_display(path)
        wave_min = float(np.nanmin(self.dataset.wavenumber))
        wave_max = float(np.nanmax(self.dataset.wavenumber))
        self.tc_range_min.SetValue(f"{min(wave_min, wave_max):.6g}")
        self.tc_range_max.SetValue(f"{max(wave_min, wave_max):.6g}")
        default_count = min(3, self.dataset.n_spectra)
        self.tc_selected.SetValue(",".join(str(index) for index in range(1, default_count + 1)))
        self.update_buttons()
        self.update_previews()
        self.mapping_notebook.SetSelection(1)
        self.log(
            f"Loaded {Path(path).name}: {self.dataset.n_points} Raman points, "
            f"{self.dataset.n_spectra} spectra, source={self.dataset.source_type}."
        )

    def set_loaded_file_display(self, path):
        self.lbl_mapping_file.SetValue(Path(path).name)
        self.lbl_mapping_file.SetToolTip(str(path))

    def on_selection_text_changed(self, event):
        event.Skip()

    def on_preview_controls_changed(self, event):
        event.Skip()
        self.update_legend_control()
        if self.preview_call is not None and self.preview_call.IsRunning():
            self.preview_call.Stop()
        self.preview_call = wx.CallLater(250, self.update_previews)

    def on_update(self, event):
        self.update_previews()

    def update_buttons(self):
        enabled = self.dataset is not None
        self.btn_save_origin.Enable(enabled)
        self.btn_save_selected.Enable(enabled)
        self.btn_load_to_insitu.Enable(enabled)
        self.update_legend_control()

    def update_legend_control(self):
        allow_legend = self.preview_every_n(default=1) > 1
        self.cb_raw_legend.Enable(allow_legend)
        if not allow_legend:
            self.cb_raw_legend.SetValue(False)

    def preview_every_n(self, default=1):
        text = self.tc_preview_every_n.GetValue().strip()
        if not text:
            return default
        try:
            value = int(text)
        except ValueError:
            return default
        return max(value, 1)

    def read_raman_range(self):
        try:
            min_cm1 = float(self.tc_range_min.GetValue().strip())
            max_cm1 = float(self.tc_range_max.GetValue().strip())
        except ValueError as exc:
            raise RamanMappingError("Raman range values must be numbers.") from exc
        if not np.isfinite(min_cm1) or not np.isfinite(max_cm1) or min_cm1 >= max_cm1:
            raise RamanMappingError("Raman range minimum must be less than maximum.")
        return min_cm1, max_cm1

    def selected_indices(self):
        if self.dataset is None:
            raise RamanMappingError("Load a Raman Mapping file first.")
        return parse_selected_spectra(self.tc_selected.GetValue(), self.dataset.n_spectra)

    def range_mask(self):
        if self.dataset is None:
            return np.array([], dtype=bool)
        min_cm1, max_cm1 = self.read_raman_range()
        mask = (self.dataset.wavenumber >= min_cm1) & (self.dataset.wavenumber <= max_cm1)
        if not np.any(mask):
            raise RamanMappingError(f"No Raman data points found in {min_cm1:g} to {max_cm1:g} cm^-1.")
        return mask

    def filtered_arrays(self):
        if self.dataset is None:
            raise RamanMappingError("Load a Raman Mapping file first.")
        mask = self.range_mask()
        return self.dataset.wavenumber[mask], self.dataset.intensity_matrix[mask, :]

    def update_previews(self):
        if self.dataset is None:
            self.clear_previews()
            return
        try:
            self.draw_avg_norm_preview()
            self.draw_raw_preview()
            self.draw_location_preview()
            self.draw_selected_preview()
        except Exception as exc:
            self.log(f"Preview update warning: {exc}")

    def draw_avg_norm_preview(self):
        headers, rows = build_unstacked_table(self.dataset)
        preview_rows = rows[:10]
        width = min(len(headers), 8)
        avg_headers = ["Wavenumber", "Averaged Intensity", "Normalised Intensity"]
        avg_indexes = [0, len(headers) - 2, len(headers) - 1]
        raw_rows = [[f"{value:.6g}" for value in row[:width]] for row in preview_rows]
        avg_rows = [[f"{row[index]:.6g}" for index in avg_indexes] for row in preview_rows]
        populate_grid(self.grid_raw_preview, headers[:width], raw_rows)
        populate_grid(self.grid_avg_preview, avg_headers, avg_rows)

    def draw_raw_preview(self):
        self.figure_raw.clear()
        ax = self.figure_raw.add_subplot(111)
        x, y_matrix = self.filtered_arrays()
        every_n = self.preview_every_n(default=1)
        indexes = list(range(0, y_matrix.shape[1], every_n))
        show_legend = every_n > 1 and self.cb_raw_legend.GetValue()
        for index in indexes:
            kwargs = {"linewidth": 0.8}
            if show_legend:
                kwargs["label"] = str(index + 1)
            ax.plot(x, y_matrix[:, index], **kwargs)
        ax.set_title("All mapping spectra" if every_n <= 1 else f"Every {every_n}-th mapping spectrum")
        ax.set_xlabel("Raman shift (cm$^{-1}$)")
        ax.set_ylabel("Intensity")
        ax.grid(True, alpha=0.3)
        if len(x) > 1 and x[0] > x[-1]:
            ax.invert_xaxis()
        if show_legend:
            ax.legend(title="Spectrum", fontsize=7, ncol=2)
        self.figure_raw.tight_layout(pad=1.2)
        self.canvas_raw.draw()

    def draw_location_preview(self):
        self.figure_location.clear()
        ax = self.figure_location.add_subplot(111)
        self.draw_location_map(ax, self.figure_location)
        self.figure_location.tight_layout(pad=1.2)
        self.canvas_location.draw()

    def draw_selected_preview(self):
        self.figure_selected.clear()
        selected_ax = self.figure_selected.add_subplot(111)
        x, y_matrix = self.filtered_arrays()
        selected = self.selected_indices()
        for index in selected:
            label = self.spectrum_label(index)
            selected_ax.plot(x, y_matrix[:, index], linewidth=1.1, label=label)
        selected_ax.set_title("Selected spectra")
        selected_ax.legend(fontsize=7)
        selected_ax.set_xlabel("Raman shift (cm$^{-1}$)")
        selected_ax.set_ylabel("Intensity")
        selected_ax.grid(True, alpha=0.3)
        if len(x) > 1 and x[0] > x[-1]:
            selected_ax.invert_xaxis()
        self.figure_selected.tight_layout(pad=1.2)
        self.canvas_selected.draw()

    def draw_location_map(self, ax, figure):
        dataset = self.dataset
        if dataset is None:
            return
        if dataset.image_bytes is not None:
            try:
                image = image_from_dataset(dataset)
                if dataset.image_origins is not None and dataset.image_dimensions is not None:
                    x0, y0 = dataset.image_origins
                    width, height = dataset.image_dimensions
                    ax.imshow(image, extent=(x0, x0 + width, y0 + height, y0))
                else:
                    ax.imshow(image)
            except Exception as exc:
                ax.text(0.5, 0.5, f"Could not draw image:\n{exc}", ha="center", va="center", transform=ax.transAxes)
        if "X" in dataset.metadata and "Y" in dataset.metadata:
            x = np.asarray(dataset.metadata["X"], dtype=float)
            y = np.asarray(dataset.metadata["Y"], dtype=float)
            seq = np.asarray(dataset.metadata["Sequence"], dtype=int)
            scatter = ax.scatter(x, y, c=seq, s=35, edgecolors="black")
            figure.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
            for xi, yi, label in zip(x, y, seq):
                ax.text(xi, yi, str(int(label)), fontsize=12, ha="left", va="bottom")
            ax.set_aspect("equal", adjustable="box")
            ax.set_title("Mapping locations")
            ax.set_xlabel("X / um")
            ax.set_ylabel("Y / um")
        elif dataset.image_bytes is None:
            ax.text(0.5, 0.5, "No image/location metadata available.", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()

    def spectrum_label(self, zero_based_index):
        if self.dataset is None:
            return ""
        sequence = int(np.asarray(self.dataset.metadata["Sequence"]).ravel()[zero_based_index])
        return str(sequence)

    def clear_previews(self):
        clear_grid(self.grid_raw_preview, "Load a Raman Mapping WDF/TXT file to preview the raw unstacked table.")
        clear_grid(self.grid_avg_preview, "Average and normalised intensity preview will appear here.")
        for figure, canvas, message in [
            (self.figure_raw, self.canvas_raw, "Load a Raman Mapping file to preview all raw spectra."),
            (self.figure_location, self.canvas_location, "Load a Raman Mapping file to preview mapping locations."),
            (self.figure_selected, self.canvas_selected, "Load a file and choose selected columns to preview selected spectra."),
        ]:
            figure.clear()
            ax = figure.add_subplot(111)
            ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            canvas.draw()

    def on_save_origin(self, event):
        if self.dataset is None:
            self.show_warning("Load a Raman Mapping file before saving.")
            return
        default_name = f"{Path(self.raw_path).stem}_processed_for_Origin.txt"
        with wx.FileDialog(
            self,
            "Save Origin-friendly Mapping TXT",
            wildcard="Text files (*.txt)|*.txt",
            defaultDir=str(Path(self.raw_path).parent),
            defaultFile=default_name,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            saved = export_origin_txt(self.dataset, path)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.log(f"Saved Origin-friendly Mapping TXT: {saved}")

    def on_save_selected(self, event):
        if self.dataset is None:
            self.show_warning("Load a Raman Mapping file before saving selected spectra.")
            return
        default_name = f"{Path(self.raw_path).stem}_selected_sequence.txt"
        with wx.FileDialog(
            self,
            "Save selected Mapping sequence TXT",
            wildcard="Text files (*.txt)|*.txt",
            defaultDir=str(Path(self.raw_path).parent),
            defaultFile=default_name,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            saved = export_selected_sequence_txt(self.dataset, self.tc_selected.GetValue(), path)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.log(f"Saved selected Mapping sequence TXT: {saved}")

    def on_load_to_insitu(self, event):
        if self.dataset is None:
            self.show_warning("Load a Raman Mapping file before loading selected spectra into Insitu EChem.")
            return
        try:
            data = raman_dataset_to_sequence(self.dataset, self.selected_indices(), name=f"{Path(self.raw_path).stem}_selected_sequence")
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.raman_panel.insitu_page.load_sequence_data(data, source_label=f"Mapping: {Path(self.raw_path).name}")
        self.raman_panel.notebook.SetSelection(2)
        self.log("Loaded selected Mapping spectra into Insitu EChem in memory.")

    def show_warning(self, message):
        wx.MessageBox(message, "Mapping warning", wx.OK | wx.ICON_WARNING, self)

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.AppendText(f"[{stamp}] {message}\n")


class RamanElectricalPanel(wx.Panel):
    RAW_TRACE_LINEWIDTH = 0.3
    RAW_TRACE_LINEWIDTH_MIN = 0.25
    RAW_TRACE_LINEWIDTH_MAX = 1.5

    def __init__(self, parent):
        super().__init__(parent)
        self.raw_path = ""
        self.data: RamanElectricalData | None = None
        self.summary = None
        self.preview_call = None
        self._updating_controls = False
        self.build_ui()

    def build_ui(self):
        root = wx.BoxSizer(wx.HORIZONTAL)
        root.Add(self.build_left_panel(), 0, wx.EXPAND | wx.ALL, 8)
        root.Add(self.build_right_panel(), 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(root)

    def build_left_panel(self):
        scrolled = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scrolled.SetScrollRate(0, 20)
        scrolled.SetMinSize((520, -1))
        sizer = wx.BoxSizer(wx.VERTICAL)

        load_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Electrical")
        self.btn_load_csv = wx.Button(scrolled, label="Load csv")
        self.lbl_electrical_file = wx.TextCtrl(
            scrolled,
            value="No Electrical CSV loaded",
            style=wx.TE_READONLY,
        )
        self.btn_load_csv.Bind(wx.EVT_BUTTON, self.on_load_file)
        load_box.Add(self.add_load_row(self.btn_load_csv, self.lbl_electrical_file), 0, wx.EXPAND | wx.ALL, 5)
        raw_preview_grid = wx.FlexGridSizer(rows=1, cols=4, vgap=6, hgap=6)
        raw_preview_grid.AddGrowableCol(1, 1)
        raw_preview_grid.AddGrowableCol(2, 2)
        self.tc_raw_preview_s = wx.TextCtrl(scrolled, value=f"{DEFAULT_PREVIEW_SECONDS:g}")
        self.slider_raw_preview = wx.Slider(scrolled, value=0, minValue=0, maxValue=100)
        self.lbl_raw_preview_range = wx.StaticText(scrolled, label="first 1.0 s")
        self.lbl_raw_preview_range.SetMinSize((90, -1))
        self.add_preview_row(
            raw_preview_grid,
            scrolled,
            "Raw data / s",
            self.tc_raw_preview_s,
            self.slider_raw_preview,
            self.lbl_raw_preview_range,
        )
        load_box.Add(raw_preview_grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        sizer.Add(load_box, 0, wx.EXPAND | wx.ALL, 5)

        preview_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Preview")
        preview_grid = wx.FlexGridSizer(rows=2, cols=4, vgap=6, hgap=6)
        preview_grid.AddGrowableCol(1, 1)
        preview_grid.AddGrowableCol(2, 2)
        self.tc_vg_preview_s = wx.TextCtrl(scrolled, value=f"{DEFAULT_PREVIEW_SECONDS:g}")
        self.tc_vd_preview_s = wx.TextCtrl(scrolled, value=f"{DEFAULT_PREVIEW_SECONDS:g}")
        self.slider_vg_preview = wx.Slider(scrolled, value=0, minValue=0, maxValue=100)
        self.slider_vd_preview = wx.Slider(scrolled, value=0, minValue=0, maxValue=100)
        self.lbl_vg_preview_range = wx.StaticText(scrolled, label="first 1.0 s")
        self.lbl_vd_preview_range = wx.StaticText(scrolled, label="first 1.0 s")
        self.lbl_vg_preview_range.SetMinSize((90, -1))
        self.lbl_vd_preview_range.SetMinSize((90, -1))
        self.add_preview_row(
            preview_grid,
            scrolled,
            "V_Gate / s",
            self.tc_vg_preview_s,
            self.slider_vg_preview,
            self.lbl_vg_preview_range,
        )
        self.add_preview_row(
            preview_grid,
            scrolled,
            "V_Drain / s",
            self.tc_vd_preview_s,
            self.slider_vd_preview,
            self.lbl_vd_preview_range,
        )
        preview_box.Add(preview_grid, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(preview_box, 0, wx.EXPAND | wx.ALL, 5)

        for ctrl in [self.tc_raw_preview_s, self.tc_vg_preview_s, self.tc_vd_preview_s]:
            ctrl.Bind(wx.EVT_TEXT, self.on_preview_text_changed)
        self.slider_raw_preview.Bind(wx.EVT_SLIDER, self.on_preview_slider)
        self.slider_vg_preview.Bind(wx.EVT_SLIDER, self.on_preview_slider)
        self.slider_vd_preview.Bind(wx.EVT_SLIDER, self.on_preview_slider)

        scrolled.SetSizer(sizer)
        return scrolled

    def build_right_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.electrical_notebook = wx.Notebook(panel)
        self.figure_electrical_raw, self.canvas_electrical_raw = self.add_figure_page("Raw data")
        self.figure_vgvd, self.canvas_vgvd, self.grid_summary = self.add_vgvd_page("V_Gate/V_Drain")
        sizer.Add(self.electrical_notebook, 1, wx.EXPAND)

        log_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Electrical log")
        self.log_box = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.log_box.SetMinSize((-1, 105))
        log_box.Add(self.log_box, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(log_box, 0, wx.EXPAND | wx.TOP, 6)

        panel.SetSizer(sizer)
        self.clear_previews()
        return panel

    def add_figure_page(self, title):
        panel = wx.Panel(self.electrical_notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        figure = Figure(figsize=(8, 6))
        canvas = FigureCanvasWxAgg(panel, -1, figure)
        sizer.Add(canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self.electrical_notebook.AddPage(panel, title)
        return figure, canvas

    def add_vgvd_page(self, title):
        panel = wx.Panel(self.electrical_notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        figure = Figure(figsize=(8, 4.8))
        canvas = FigureCanvasWxAgg(panel, -1, figure)
        grid = create_readonly_grid(panel)
        grid.SetMinSize((-1, 150))
        sizer.Add(canvas, 1, wx.EXPAND | wx.ALL, 8)
        sizer.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        panel.SetSizer(sizer)
        self.electrical_notebook.AddPage(panel, title)
        return figure, canvas, grid

    @staticmethod
    def add_load_row(button, label):
        button.SetMinSize((135, -1))
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(button, 0, wx.RIGHT, 6)
        row.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        return row

    @staticmethod
    def add_preview_row(grid, parent, label, ctrl, slider, range_label):
        grid.Add(wx.StaticText(parent, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(ctrl, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(slider, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        grid.Add(range_label, 0, wx.ALIGN_CENTER_VERTICAL)

    def collect_app_parameters(self):
        return {
            "raw_path": self.raw_path,
            "raw_preview_s": self.tc_raw_preview_s.GetValue(),
            "vg_preview_s": self.tc_vg_preview_s.GetValue(),
            "vd_preview_s": self.tc_vd_preview_s.GetValue(),
        }

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        raw_path = str(params.get("raw_path", "") or "")
        if raw_path:
            try:
                self.load_data(raw_path)
            except Exception as exc:
                self.raw_path = raw_path
                self.set_loaded_file_display(raw_path)
                self.log(f"Could not restore Electrical CSV: {exc}")
        self.tc_raw_preview_s.SetValue(str(params.get("raw_preview_s", self.tc_raw_preview_s.GetValue())))
        self.tc_vg_preview_s.SetValue(str(params.get("vg_preview_s", self.tc_vg_preview_s.GetValue())))
        self.tc_vd_preview_s.SetValue(str(params.get("vd_preview_s", self.tc_vd_preview_s.GetValue())))
        self.update_preview_labels()
        self.schedule_preview(delay_ms=50)

    def on_load_file(self, event):
        with wx.FileDialog(
            self,
            "Load Electrical CSV file",
            wildcard="CSV files (*.csv)|*.csv|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        try:
            self.load_data(path)
        except Exception as exc:
            self.show_warning(str(exc))

    def load_data(self, path):
        self.data = load_electrical_csv(path)
        self.summary = summarize_electrical_data(self.data)
        self.raw_path = str(path)
        self.set_loaded_file_display(path)
        self.update_previews()
        self.electrical_notebook.SetSelection(1)
        self.log(
            f"Loaded {Path(path).name}: {self.data.n_rows} rows, "
            f"total time {self.data.total_time_s:.6g} s."
        )
        if self.data.missing_columns:
            self.log("Missing exact column(s): " + ", ".join(self.data.missing_columns))

    def set_loaded_file_display(self, path):
        self.lbl_electrical_file.SetValue(Path(path).name)
        self.lbl_electrical_file.SetToolTip(str(path))

    def on_preview_text_changed(self, event):
        event.Skip()
        if self._updating_controls:
            return
        self.update_preview_labels()
        self.schedule_preview()

    def on_preview_slider(self, event):
        event.Skip()
        slider = event.GetEventObject()
        if slider is self.slider_raw_preview:
            ctrl = self.tc_raw_preview_s
            channel = "raw"
        elif slider is self.slider_vg_preview:
            ctrl = self.tc_vg_preview_s
            channel = "vg"
        else:
            ctrl = self.tc_vd_preview_s
            channel = "vd"
        seconds = self.seconds_from_slider(slider, channel)
        self._updating_controls = True
        try:
            ctrl.SetValue(self.format_preview_seconds(seconds))
        finally:
            self._updating_controls = False
        self.update_preview_labels()
        self.schedule_preview(delay_ms=50)

    def seconds_from_slider(self, slider, channel):
        total = self.channel_total_seconds(channel)
        if total <= 0:
            return DEFAULT_PREVIEW_SECONDS
        percent = dwf_preview_percent_from_slider(slider.GetValue())
        return max(total * percent / 100.0, 1.0 / 100.0)

    def channel_total_seconds(self, channel):
        if self.data is None:
            return DEFAULT_PREVIEW_SECONDS
        if channel == "raw":
            spans = []
            for time_name in [GATE_TIME_COL, DRAIN_TIME_COL]:
                values = self.data.column(time_name)
                if values is None:
                    continue
                clean = np.asarray(values, dtype=float)
                clean = clean[np.isfinite(clean)]
                if clean.size > 0:
                    spans.append(float(np.max(clean) - np.min(clean)))
            if spans:
                return max(max(spans), self.data.total_time_s)
            return self.data.total_time_s
        time_name = GATE_TIME_COL if channel == "vg" else DRAIN_TIME_COL
        values = self.data.column(time_name)
        if values is None:
            return self.data.total_time_s
        clean = np.asarray(values, dtype=float)
        clean = clean[np.isfinite(clean)]
        if clean.size == 0:
            return self.data.total_time_s
        span = float(np.max(clean) - np.min(clean))
        return span if span > 0 else self.data.total_time_s

    def update_preview_labels(self):
        self.lbl_raw_preview_range.SetLabel(f"first {self.format_preview_seconds(self.preview_seconds('raw'))} s")
        self.lbl_vg_preview_range.SetLabel(f"first {self.format_preview_seconds(self.preview_seconds('vg'))} s")
        self.lbl_vd_preview_range.SetLabel(f"first {self.format_preview_seconds(self.preview_seconds('vd'))} s")

    def schedule_preview(self, delay_ms=250):
        if self.preview_call is not None and self.preview_call.IsRunning():
            self.preview_call.Stop()
        self.preview_call = wx.CallLater(delay_ms, self.update_previews)

    def preview_seconds(self, channel):
        if channel == "raw":
            ctrl = self.tc_raw_preview_s
        elif channel == "vg":
            ctrl = self.tc_vg_preview_s
        else:
            ctrl = self.tc_vd_preview_s
        text = ctrl.GetValue().strip()
        if not text:
            return DEFAULT_PREVIEW_SECONDS
        try:
            value = float(text)
        except ValueError:
            return DEFAULT_PREVIEW_SECONDS
        if not np.isfinite(value) or value <= 0:
            return DEFAULT_PREVIEW_SECONDS
        return value

    @staticmethod
    def format_preview_seconds(value):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = DEFAULT_PREVIEW_SECONDS
        if not np.isfinite(numeric) or numeric <= 0:
            numeric = DEFAULT_PREVIEW_SECONDS
        return f"{numeric:.1f}"

    def update_previews(self):
        if self.data is None:
            self.clear_previews()
            return
        try:
            self.update_preview_labels()
            self.draw_raw_preview()
            self.draw_vgvd_preview()
            self.draw_summary_table()
        except Exception as exc:
            self.log(f"Preview update warning: {exc}")

    def draw_raw_preview(self):
        self.figure_electrical_raw.clear()
        axes = [
            self.figure_electrical_raw.add_subplot(221),
            self.figure_electrical_raw.add_subplot(222),
            self.figure_electrical_raw.add_subplot(223),
            self.figure_electrical_raw.add_subplot(224),
        ]
        plots = [
            (GATE_TIME_COL, GATE_VOLTAGE_COL, "Gate V", r"$V_{Gate}$ / V", "green"),
            (DRAIN_TIME_COL, DRAIN_VOLTAGE_COL, "Drain V", r"$V_{Drain}$ / V", "red"),
            (GATE_TIME_COL, GATE_CURRENT_COL, "Gate I", r"$I_{Gate}$ / A", "orange"),
            (DRAIN_TIME_COL, DRAIN_CURRENT_COL, "Drain I", r"$I_{Drain}$ / A", "blue"),
        ]
        raw_preview_s = self.preview_seconds("raw")
        raw_linewidth = self.raw_trace_linewidth(raw_preview_s)
        for ax, (time_col, signal_col, title, ylabel, color) in zip(axes, plots):
            self.plot_signal(ax, time_col, signal_col, title, ylabel, color, raw_preview_s, raw_linewidth)
        self.figure_electrical_raw.tight_layout(pad=1.2)
        self.canvas_electrical_raw.draw()

    @classmethod
    def raw_trace_linewidth(cls, preview_s):
        try:
            seconds = float(preview_s)
        except (TypeError, ValueError):
            return cls.RAW_TRACE_LINEWIDTH
        if not np.isfinite(seconds) or seconds <= 0:
            return cls.RAW_TRACE_LINEWIDTH
        linewidth = cls.RAW_TRACE_LINEWIDTH_MAX / np.sqrt(max(seconds, 0.1))
        return float(min(cls.RAW_TRACE_LINEWIDTH_MAX, max(cls.RAW_TRACE_LINEWIDTH_MIN, linewidth)))

    def plot_signal(self, ax, time_col, signal_col, title, ylabel, color, preview_s, linewidth):
        time_values = self.data.column(time_col) if self.data is not None else None
        signal_values = self.data.column(signal_col) if self.data is not None else None
        if time_values is None or signal_values is None:
            ax.text(0.5, 0.5, "Column missing", ha="center", va="center", transform=ax.transAxes)
        else:
            valid = np.isfinite(time_values) & np.isfinite(signal_values)
            if np.any(valid):
                start = float(np.min(time_values[valid]))
                valid = valid & (time_values <= start + float(preview_s))
            ax.plot(time_values[valid], signal_values[valid], color=color, linewidth=linewidth)
        ax.set_title(title)
        ax.set_xlabel("Time / s")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)

    def draw_vgvd_preview(self):
        self.figure_vgvd.clear()
        ax_left = self.figure_vgvd.add_subplot(111)
        ax_right = ax_left.twinx()
        has_vg = self.plot_voltage_preview(
            ax_left,
            GATE_TIME_COL,
            GATE_VOLTAGE_COL,
            self.preview_seconds("vg"),
            r"$V_{Gate}$",
            "green",
        )
        has_vd = self.plot_voltage_preview(
            ax_right,
            DRAIN_TIME_COL,
            DRAIN_VOLTAGE_COL,
            self.preview_seconds("vd"),
            r"$V_{Drain}$",
            "red",
        )
        if not has_vg:
            ax_left.text(0.5, 0.6, "Gate Voltage column missing", ha="center", va="center", transform=ax_left.transAxes)
        if not has_vd:
            ax_right.text(0.5, 0.4, "Drain Voltage column missing", ha="center", va="center", transform=ax_right.transAxes)
        ax_left.set_xlabel("Time / s")
        ax_left.set_ylabel(r"$V_{Gate}$ / V", color="green")
        ax_left.tick_params(axis="y", labelcolor="green")
        ax_left.grid(True, alpha=0.3)
        ax_right.set_ylabel(r"$V_{Drain}$ / V", color="red")
        ax_right.tick_params(axis="y", labelcolor="red")
        ax_left.set_title(
            "V_Gate first "
            f"{self.format_preview_seconds(self.preview_seconds('vg'))} s and "
            "V_Drain first "
            f"{self.format_preview_seconds(self.preview_seconds('vd'))} s"
        )
        lines_left, labels_left = ax_left.get_legend_handles_labels()
        lines_right, labels_right = ax_right.get_legend_handles_labels()
        if lines_left or lines_right:
            ax_left.legend(lines_left + lines_right, labels_left + labels_right, loc="best")
        self.figure_vgvd.tight_layout(pad=1.2)
        self.canvas_vgvd.draw()

    def plot_voltage_preview(self, ax, time_col, voltage_col, preview_s, label, color):
        time_values = self.data.column(time_col) if self.data is not None else None
        voltage_values = self.data.column(voltage_col) if self.data is not None else None
        if time_values is None or voltage_values is None:
            return False
        valid = np.isfinite(time_values) & np.isfinite(voltage_values)
        if not np.any(valid):
            return False
        t = time_values[valid]
        v = voltage_values[valid]
        start = float(np.min(t))
        mask = t <= start + float(preview_s)
        ax.plot(t[mask], v[mask], color=color, linewidth=1.5, label=label)
        return True

    def draw_summary_table(self):
        if self.summary is None:
            clear_grid(self.grid_summary, "Load an Electrical CSV file to preview V_Gate/V_Drain summary.")
            return
        headers = ["Item", "const/pulse", "const value / V", "n_pulse", "t_initial / s", "t_duration / s"]
        rows = []
        for row in summary_table_rows(self.summary):
            if len(row) == 2:
                rows.append([row[0], row[1], "-", "-", "-", "-"])
            else:
                rows.append(row)
        populate_grid(self.grid_summary, headers, rows)

    def clear_previews(self):
        for figure, canvas, message in [
            (
                self.figure_electrical_raw,
                self.canvas_electrical_raw,
                "Load an Electrical CSV file to preview V_Gate, I_Gate, V_Drain, and I_Drain.",
            ),
            (self.figure_vgvd, self.canvas_vgvd, "Load an Electrical CSV file to preview V_Gate/V_Drain."),
        ]:
            figure.clear()
            ax = figure.add_subplot(111)
            ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            canvas.draw()
        clear_grid(self.grid_summary, "Electrical summary will appear here.")

    def show_warning(self, message):
        wx.MessageBox(message, "Electrical warning", wx.OK | wx.ICON_WARNING, self)

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.AppendText(f"[{stamp}] {message}\n")


class RamanInsituEchemPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.raw_path = ""
        self.in_memory_data = None
        self.source_label = ""
        self.sequence_source = "time"
        self.data = None
        self.result = None
        self.window_rows = []
        self.preview_call = None
        self.build_ui()

    def build_ui(self):
        root = wx.BoxSizer(wx.HORIZONTAL)
        root.Add(self.build_left_panel(), 0, wx.EXPAND | wx.ALL, 8)
        root.Add(self.build_right_panel(), 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(root)

    def build_left_panel(self):
        scrolled = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scrolled.SetScrollRate(0, 20)
        scrolled.SetMinSize((520, -1))
        sizer = wx.BoxSizer(wx.VERTICAL)

        params_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Parameters")
        params_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_save_insitu_params = wx.Button(scrolled, label="Save Parameters")
        self.btn_load_insitu_params = wx.Button(scrolled, label="Load Parameters")
        self.btn_save_insitu_params.Bind(wx.EVT_BUTTON, self.on_save_parameters)
        self.btn_load_insitu_params.Bind(wx.EVT_BUTTON, self.on_load_parameters)
        params_row.Add(self.btn_save_insitu_params, 1, wx.EXPAND | wx.RIGHT, 5)
        params_row.Add(self.btn_load_insitu_params, 1, wx.EXPAND)
        params_box.Add(params_row, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(params_box, 0, wx.EXPAND | wx.ALL, 5)

        load_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Insitu EChem")
        self.btn_load_insitu = wx.Button(scrolled, label="Load wdf/txt")
        self.lbl_insitu_file = wx.TextCtrl(scrolled, value="No Raman sequence file loaded", style=wx.TE_READONLY)
        self.lbl_insitu_file.SetMinSize((260, -1))
        self.btn_load_insitu.Bind(wx.EVT_BUTTON, self.on_load_file)
        load_box.Add(self.add_load_row(self.btn_load_insitu, self.lbl_insitu_file), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(load_box, 0, wx.EXPAND | wx.ALL, 5)

        x_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "X-axis")
        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_sequence = wx.RadioButton(scrolled, label="Sequence", style=wx.RB_GROUP)
        self.rb_time = wx.RadioButton(scrolled, label="Time")
        self.rb_sequence.SetValue(True)
        self.rb_sequence.Bind(wx.EVT_RADIOBUTTON, self.on_x_mode_changed)
        self.rb_time.Bind(wx.EVT_RADIOBUTTON, self.on_x_mode_changed)
        mode_row.Add(self.rb_sequence, 0, wx.RIGHT, 16)
        mode_row.Add(self.rb_time, 0)
        x_box.Add(mode_row, 0, wx.ALL, 5)
        self.time_grid = wx.FlexGridSizer(rows=2, cols=2, vgap=6, hgap=6)
        self.time_grid.AddGrowableCol(1, 1)
        self.tc_time_offset = wx.TextCtrl(scrolled, value=f"{DEFAULT_TIME_OFFSET_S:g}")
        self.tc_time_per_sequence = wx.TextCtrl(scrolled, value=f"{DEFAULT_TIME_PER_SEQUENCE_S:g}")
        self.time_grid.Add(wx.StaticText(scrolled, label="Time Offset"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.time_grid.Add(self.tc_time_offset, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        self.time_grid.Add(wx.StaticText(scrolled, label="Time per sequence"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.time_grid.Add(self.tc_time_per_sequence, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        x_box.Add(self.time_grid, 0, wx.EXPAND | wx.ALL, 5)
        self.raman_range_grid = wx.FlexGridSizer(rows=2, cols=2, vgap=6, hgap=6)
        self.raman_range_grid.AddGrowableCol(1, 1)
        self.tc_raman_range_min = wx.TextCtrl(scrolled, value=f"{DEFAULT_RAMAN_RANGE_MIN_CM1:g}")
        self.tc_raman_range_max = wx.TextCtrl(scrolled, value=f"{DEFAULT_RAMAN_RANGE_MAX_CM1:g}")
        self.raman_range_grid.Add(wx.StaticText(scrolled, label="Raman range min / cm^-1"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.raman_range_grid.Add(self.tc_raman_range_min, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        self.raman_range_grid.Add(wx.StaticText(scrolled, label="Raman range max / cm^-1"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.raman_range_grid.Add(self.tc_raman_range_max, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        x_box.Add(self.raman_range_grid, 0, wx.EXPAND | wx.ALL, 5)
        for ctrl in [self.tc_time_offset, self.tc_time_per_sequence, self.tc_raman_range_min, self.tc_raman_range_max]:
            ctrl.Bind(wx.EVT_TEXT, self.on_parameter_changed)
        sizer.Add(x_box, 0, wx.EXPAND | wx.ALL, 5)

        window_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Window")
        self.window_rows_panel = wx.Panel(scrolled)
        self.window_rows_sizer = wx.BoxSizer(wx.VERTICAL)
        self.window_rows_panel.SetSizer(self.window_rows_sizer)
        header = wx.FlexGridSizer(rows=1, cols=2, vgap=0, hgap=6)
        header.AddGrowableCol(0, 1)
        header.AddGrowableCol(1, 1)
        header.Add(wx.StaticText(self.window_rows_panel, label="Peak"), 0, wx.EXPAND)
        header.Add(wx.StaticText(self.window_rows_panel, label="Window size"), 0, wx.EXPAND)
        self.window_rows_sizer.Add(header, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        for center, tolerance in DEFAULT_PEAK_WINDOWS:
            self.add_peak_window_row(center, tolerance)
        window_box.Add(self.window_rows_panel, 0, wx.EXPAND)
        window_button_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_window = wx.Button(scrolled, label="Add peak window")
        self.btn_delete_window = wx.Button(scrolled, label="Delete peak window")
        self.btn_add_window.Bind(wx.EVT_BUTTON, self.on_add_peak_window)
        self.btn_delete_window.Bind(wx.EVT_BUTTON, self.on_delete_peak_window)
        window_button_row.Add(self.btn_add_window, 1, wx.EXPAND | wx.RIGHT, 5)
        window_button_row.Add(self.btn_delete_window, 1, wx.EXPAND)
        window_box.Add(window_button_row, 0, wx.EXPAND | wx.ALL, 5)

        every_grid = wx.FlexGridSizer(rows=2, cols=2, vgap=6, hgap=6)
        every_grid.AddGrowableCol(1, 1)
        self.tc_window_every_n = wx.TextCtrl(scrolled, value=str(DEFAULT_WINDOW_PREVIEW_EVERY_N))
        self.tc_result_every_n = wx.TextCtrl(scrolled, value=str(DEFAULT_RESULT_SPECTRA_EVERY_N))
        every_grid.Add(wx.StaticText(scrolled, label="Every N for window preview"), 0, wx.ALIGN_CENTER_VERTICAL)
        every_grid.Add(self.tc_window_every_n, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        every_grid.Add(wx.StaticText(scrolled, label="Every N for result spectra"), 0, wx.ALIGN_CENTER_VERTICAL)
        every_grid.Add(self.tc_result_every_n, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        window_box.Add(every_grid, 0, wx.EXPAND | wx.ALL, 5)
        self.tc_window_every_n.Bind(wx.EVT_TEXT, self.on_parameter_changed)
        self.tc_result_every_n.Bind(wx.EVT_TEXT, self.on_parameter_changed)
        sizer.Add(window_box, 0, wx.EXPAND | wx.ALL, 5)

        norm_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Normalised peak")
        self.choice_normalized_peak = wx.Choice(scrolled)
        self.choice_normalized_peak.Bind(wx.EVT_CHOICE, self.on_parameter_changed)
        norm_box.Add(self.choice_normalized_peak, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(norm_box, 0, wx.EXPAND | wx.ALL, 5)

        update_row = wx.BoxSizer(wx.HORIZONTAL)
        self.cb_analysis_legend = wx.CheckBox(scrolled, label="Legend")
        self.cb_analysis_legend.SetValue(True)
        self.cb_analysis_legend.Bind(wx.EVT_CHECKBOX, self.on_parameter_changed)
        self.btn_update_preview = wx.Button(scrolled, label="Update")
        self.btn_update_preview.Bind(wx.EVT_BUTTON, self.on_update_preview)
        update_row.Add(self.cb_analysis_legend, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        update_row.Add(self.btn_update_preview, 1, wx.EXPAND)
        sizer.Add(update_row, 0, wx.EXPAND | wx.ALL, 5)

        save_box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Save")
        self.btn_save_spectra = wx.Button(scrolled, label="Save spectra plot/data")
        self.btn_save_positions = wx.Button(scrolled, label="Save peak positions plot/data")
        self.btn_save_intensities = wx.Button(scrolled, label="Save peak intensities plot/data")
        self.btn_save_ratios = wx.Button(scrolled, label="Save ratios plot/data")
        for button, handler in [
            (self.btn_save_spectra, self.on_save_spectra),
            (self.btn_save_positions, self.on_save_positions),
            (self.btn_save_intensities, self.on_save_intensities),
            (self.btn_save_ratios, self.on_save_ratios),
        ]:
            button.Disable()
            button.Bind(wx.EVT_BUTTON, handler)
            save_box.Add(button, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(save_box, 0, wx.EXPAND | wx.ALL, 5)

        scrolled.SetSizer(sizer)
        self.update_time_controls()
        self.update_normalized_peak_choices()
        return scrolled

    def build_right_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.insitu_notebook = wx.Notebook(panel)
        self.figure_windows, self.canvas_windows = self.add_figure_page("Peak windows")
        self.figure_analysis, self.canvas_analysis = self.add_figure_page("Analysis")
        sizer.Add(self.insitu_notebook, 1, wx.EXPAND)

        log_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Insitu EChem log")
        self.log_box = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.log_box.SetMinSize((-1, 105))
        log_box.Add(self.log_box, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(log_box, 0, wx.EXPAND | wx.TOP, 6)
        panel.SetSizer(sizer)
        self.clear_insitu_figures()
        return panel

    def add_figure_page(self, title):
        panel = wx.Panel(self.insitu_notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        figure = Figure(figsize=(8, 6))
        canvas = FigureCanvasWxAgg(panel, -1, figure)
        sizer.Add(canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self.insitu_notebook.AddPage(panel, title)
        return figure, canvas

    @staticmethod
    def add_load_row(button, label):
        button.SetMinSize((135, -1))
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(button, 0, wx.RIGHT, 6)
        row.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        return row

    def add_peak_window_row(self, center="", tolerance=""):
        row_panel = wx.Panel(self.window_rows_panel)
        row = wx.FlexGridSizer(rows=1, cols=2, vgap=0, hgap=6)
        row.AddGrowableCol(0, 1)
        row.AddGrowableCol(1, 1)
        center_ctrl = wx.TextCtrl(row_panel, value=f"{center:g}" if isinstance(center, (int, float)) else str(center))
        tolerance_ctrl = wx.TextCtrl(row_panel, value=f"{tolerance:g}" if isinstance(tolerance, (int, float)) else str(tolerance))
        center_ctrl.Bind(wx.EVT_TEXT, self.on_windows_changed)
        tolerance_ctrl.Bind(wx.EVT_TEXT, self.on_windows_changed)
        row.Add(center_ctrl, 0, wx.EXPAND)
        row.Add(tolerance_ctrl, 0, wx.EXPAND)
        row_panel.SetSizer(row)
        self.window_rows_sizer.Add(row_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        self.window_rows.append((row_panel, center_ctrl, tolerance_ctrl))

    def on_add_peak_window(self, event):
        self.add_peak_window_row("", "")
        self.window_rows_panel.Layout()
        self.Layout()
        self.update_normalized_peak_choices()
        self.force_preview_update()

    def on_delete_peak_window(self, event):
        self.remove_last_peak_window_row()

    def remove_last_peak_window_row(self):
        if len(self.window_rows) <= 1:
            self.show_warning("At least one peak window row is required.")
            self.log("Delete peak window refused: at least one row is required.")
            return
        row_panel, _, _ = self.window_rows.pop()
        self.window_rows_sizer.Detach(row_panel)
        row_panel.Destroy()
        self.window_rows_panel.Layout()
        self.Layout()
        self.update_normalized_peak_choices()
        self.force_preview_update()

    def collect_parameters(self):
        return {
            "analysis": "insitu_echem",
            "version": 1,
            "x_mode": self.current_x_mode(),
            "time_offset_s": self.tc_time_offset.GetValue(),
            "time_per_sequence_s": self.tc_time_per_sequence.GetValue(),
            "raman_range_min_cm1": self.tc_raman_range_min.GetValue(),
            "raman_range_max_cm1": self.tc_raman_range_max.GetValue(),
            "window_preview_every_n": self.tc_window_every_n.GetValue(),
            "result_spectra_every_n": self.tc_result_every_n.GetValue(),
            "normalized_peak_cm1": self.choice_normalized_peak.GetStringSelection(),
            "show_analysis_legend": self.cb_analysis_legend.GetValue(),
            "peak_windows": [
                {
                    "peak_cm1": center_ctrl.GetValue(),
                    "window_size_cm1": tolerance_ctrl.GetValue(),
                }
                for _, center_ctrl, tolerance_ctrl in self.window_rows
            ],
        }

    def apply_parameters(self, params):
        if not isinstance(params, dict):
            raise RamanInsituError("Parameter file must contain a JSON object.")
        required = [
            "x_mode",
            "time_offset_s",
            "time_per_sequence_s",
            "raman_range_min_cm1",
            "raman_range_max_cm1",
            "window_preview_every_n",
            "result_spectra_every_n",
            "peak_windows",
        ]
        for key in required:
            if key not in params:
                raise RamanInsituError(f"Missing parameter: {key}.")
        x_mode = str(params["x_mode"])
        if x_mode not in {"sequence", "time"}:
            raise RamanInsituError("x_mode must be sequence or time.")
        peak_windows = params["peak_windows"]
        if not isinstance(peak_windows, list) or not peak_windows:
            raise RamanInsituError("peak_windows must contain at least one row.")
        validated_windows = []
        for row in peak_windows:
            if not isinstance(row, dict):
                raise RamanInsituError("Each peak window must be a JSON object.")
            if "peak_cm1" not in row or "window_size_cm1" not in row:
                raise RamanInsituError("Each peak window must include peak_cm1 and window_size_cm1.")
            validated_windows.append((str(row["peak_cm1"]), str(row["window_size_cm1"])))

        self.rb_sequence.SetValue(x_mode == "sequence")
        self.rb_time.SetValue(x_mode == "time")
        self.tc_time_offset.SetValue(str(params["time_offset_s"]))
        self.tc_time_per_sequence.SetValue(str(params["time_per_sequence_s"]))
        self.tc_raman_range_min.SetValue(str(params["raman_range_min_cm1"]))
        self.tc_raman_range_max.SetValue(str(params["raman_range_max_cm1"]))
        self.tc_window_every_n.SetValue(str(params["window_preview_every_n"]))
        self.tc_result_every_n.SetValue(str(params["result_spectra_every_n"]))
        self.cb_analysis_legend.SetValue(bool(params.get("show_analysis_legend", True)))

        self.clear_peak_window_rows()
        for peak, window_size in validated_windows:
            self.add_peak_window_row(peak, window_size)

        self.update_time_controls()
        self.update_normalized_peak_choices()
        normalized_peak = str(params.get("normalized_peak_cm1", ""))
        if normalized_peak and normalized_peak in self.choice_normalized_peak.GetItems():
            self.choice_normalized_peak.SetStringSelection(normalized_peak)
        self.window_rows_panel.Layout()
        self.Layout()
        if self.raw_path:
            self.force_preview_update()

    def clear_peak_window_rows(self):
        for row_panel, _, _ in list(self.window_rows):
            self.window_rows_sizer.Detach(row_panel)
            row_panel.Destroy()
        self.window_rows.clear()

    def collect_app_parameters(self):
        params = self.collect_parameters()
        params["raw_path"] = self.raw_path
        return params

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        apply_params = dict(params)
        raw_path = str(apply_params.pop("raw_path", "") or "")
        self.in_memory_data = None
        self.apply_parameters(apply_params)
        if raw_path:
            self.raw_path = raw_path
            self.set_loaded_file_display(raw_path)
            self.force_preview_update()

    def on_save_parameters(self, event):
        default_name = f"insitu_echem_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with wx.FileDialog(
            self,
            "Save Insitu EChem parameters",
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
        self.log(f"Saved Insitu EChem parameters: {path}")

    def on_load_parameters(self, event):
        with wx.FileDialog(
            self,
            "Load Insitu EChem parameters",
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
        self.log(f"Loaded Insitu EChem parameters: {path}")

    def on_load_file(self, event):
        with wx.FileDialog(
            self,
            "Load Insitu EChem Raman file",
            wildcard="Raman files (*.wdf;*.txt)|*.wdf;*.txt|WDF files (*.wdf)|*.wdf|Text files (*.txt)|*.txt|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            path = dialog.GetPath()
        self.raw_path = path
        self.in_memory_data = None
        self.set_loaded_file_display(path)
        self.force_preview_update()

    def load_sequence_data(self, data, source_label="In-memory sequence"):
        self.raw_path = ""
        self.in_memory_data = data
        self.source_label = source_label
        self.set_loaded_file_display(source_label)
        self.force_preview_update()

    def on_x_mode_changed(self, event):
        self.update_time_controls()
        self.force_preview_update()

    def on_parameter_changed(self, event):
        self.schedule_preview_update()

    def on_update_preview(self, event):
        self.force_preview_update()

    def on_windows_changed(self, event):
        self.update_normalized_peak_choices()
        self.schedule_preview_update()

    def schedule_preview_update(self):
        if self.preview_call is not None and self.preview_call.IsRunning():
            self.preview_call.Stop()
        self.preview_call = wx.CallLater(300, self.reload_data_and_update)

    def force_preview_update(self):
        if self.preview_call is not None and self.preview_call.IsRunning():
            self.preview_call.Stop()
        if not self.raw_path and self.in_memory_data is None:
            self.log("Load a file first before updating the Insitu EChem preview.")
            return
        self.reload_data_and_update()

    def set_loaded_file_display(self, path):
        path_text = str(path)
        self.lbl_insitu_file.SetValue(Path(path_text).name if Path(path_text).suffix else path_text)
        self.lbl_insitu_file.SetToolTip(path_text)

    def update_time_controls(self):
        time_allowed = self.sequence_source == "time"
        if not time_allowed:
            self.rb_sequence.SetValue(True)
            self.rb_time.SetValue(False)
        self.rb_time.Enable(time_allowed)
        show = self.rb_time.GetValue() and time_allowed
        for item in self.time_grid.GetChildren():
            item.Show(show)
            window = item.GetWindow()
            if window is not None:
                window.Enable(time_allowed)
        self.Layout()

    def update_sequence_source(self, sequence_source):
        self.sequence_source = "time" if sequence_source == "time" else "sequence"
        self.update_time_controls()

    def reload_data_and_update(self):
        if not self.raw_path and self.in_memory_data is None:
            return
        try:
            time_offset, time_per_sequence = self.read_time_settings()
            range_min_cm1, range_max_cm1 = self.read_raman_range()
            raw_data = self.in_memory_data if self.in_memory_data is not None else load_raman_sequence(self.raw_path, time_offset, time_per_sequence)
            self.update_sequence_source(raw_data.sequence_source)
            self.data = filter_raman_range(raw_data, range_min_cm1, range_max_cm1)
            windows = self.read_peak_windows()
            normalized_peak = self.read_normalized_peak(windows)
            self.result = analyze_insitu_sequence(self.data, windows, normalized_peak)
        except Exception as exc:
            self.log(f"Preview update warning: {exc}")
            self.update_save_buttons()
            return
        self.draw_insitu_previews()
        self.update_save_buttons()
        self.log(
            f"Loaded {self.data.name}: {len(self.data.intensity):,} rows, "
            f"{len(self.data.sequence_values)} sequences, {len(self.result.windows)} peak window(s)."
        )

    def read_time_settings(self):
        return (
            self.parse_float(self.tc_time_offset, "Time Offset", allow_zero=True),
            self.parse_float(self.tc_time_per_sequence, "Time per sequence"),
        )

    def read_raman_range(self):
        min_cm1 = self.parse_float(self.tc_raman_range_min, "Raman range min", allow_zero=True)
        max_cm1 = self.parse_float(self.tc_raman_range_max, "Raman range max", allow_zero=True)
        if not np.isfinite(min_cm1) or not np.isfinite(max_cm1):
            raise RamanInsituError("Raman range values must be finite.")
        if min_cm1 >= max_cm1:
            raise RamanInsituError("Raman range minimum must be less than maximum.")
        return min_cm1, max_cm1

    def read_peak_windows(self):
        windows = []
        for _, center_ctrl, tolerance_ctrl in self.window_rows:
            center_text = center_ctrl.GetValue().strip()
            tolerance_text = tolerance_ctrl.GetValue().strip()
            if not center_text and not tolerance_text:
                continue
            if not center_text or not tolerance_text:
                raise RamanInsituError("Each peak-window row must contain both Peak and Window size.")
            windows.append(PeakWindow(float(center_text), float(tolerance_text)))
        if not windows:
            raise RamanInsituError("At least one peak window is required.")
        return tuple(windows)

    def read_normalized_peak(self, windows):
        text = self.choice_normalized_peak.GetStringSelection()
        if text:
            return float(text)
        centers = [window.center_cm1 for window in windows]
        if 1423.0 in centers:
            return 1423.0
        return centers[0]

    def read_every_n(self, ctrl, label):
        value = self.parse_int(ctrl, label)
        return max(value, 1)

    @staticmethod
    def parse_float(ctrl, label, allow_zero=False):
        text = ctrl.GetValue().strip()
        if not text:
            raise RamanInsituError(f"{label} is empty.")
        try:
            value = float(text)
        except ValueError as exc:
            raise RamanInsituError(f"{label} must be a number.") from exc
        if allow_zero:
            if value < 0:
                raise RamanInsituError(f"{label} must be >= 0.")
        elif value <= 0:
            raise RamanInsituError(f"{label} must be > 0.")
        return value

    @staticmethod
    def parse_int(ctrl, label):
        text = ctrl.GetValue().strip()
        if not text:
            raise RamanInsituError(f"{label} is empty.")
        try:
            value = int(text)
        except ValueError as exc:
            raise RamanInsituError(f"{label} must be an integer.") from exc
        if value <= 0:
            raise RamanInsituError(f"{label} must be > 0.")
        return value

    def update_normalized_peak_choices(self):
        old = self.choice_normalized_peak.GetStringSelection()
        labels = []
        for _, center_ctrl, _ in self.window_rows:
            try:
                labels.append(format_peak_label(float(center_ctrl.GetValue().strip())))
            except ValueError:
                continue
        self.choice_normalized_peak.Set(labels)
        preferred = "1423" if "1423" in labels else (old if old in labels else (labels[0] if labels else ""))
        if preferred:
            self.choice_normalized_peak.SetStringSelection(preferred)

    def update_save_buttons(self):
        enabled = self.result is not None
        for button in [self.btn_save_spectra, self.btn_save_positions, self.btn_save_intensities, self.btn_save_ratios]:
            button.Enable(enabled)

    def draw_insitu_previews(self):
        x_mode = self.current_x_mode()
        self.draw_peak_windows_preview(self.figure_windows, x_mode)
        self.canvas_windows.draw()
        self.draw_analysis_preview(self.figure_analysis, x_mode)
        self.canvas_analysis.draw()

    def draw_peak_windows_preview(self, figure, x_mode):
        figure.clear()
        ax = figure.add_subplot(111)
        every_n = self.read_every_n(self.tc_window_every_n, "Every N for window preview")
        self.plot_spectra_with_windows(ax, every_n, x_mode)
        figure.tight_layout(pad=1.2)

    def draw_analysis_preview(self, figure, x_mode):
        figure.clear()
        spectra_ax = figure.add_subplot(221)
        positions_ax = figure.add_subplot(222)
        intensities_ax = figure.add_subplot(223)
        ratios_ax = figure.add_subplot(224)
        every_n = self.read_every_n(self.tc_result_every_n, "Every N for result spectra")
        self.plot_gradient_spectra(spectra_ax, every_n, x_mode, show_legend=self.cb_analysis_legend.GetValue())
        self.plot_peak_positions(positions_ax, x_mode)
        self.plot_peak_intensities(intensities_ax, x_mode)
        self.plot_ratios(ratios_ax, x_mode)
        figure.tight_layout(pad=1.2)

    def plot_spectra_with_windows(self, ax, every_n, x_mode):
        self.plot_sequence_spectra(ax, every_n, x_mode, gradient=False)
        colors = colormaps["tab10"](np.linspace(0, 1, max(len(self.result.windows), 1)))
        for window, color in zip(self.result.windows, colors):
            ax.axvspan(
                window.low_cm1,
                window.high_cm1,
                alpha=0.32,
                color=color,
                label=f"{format_peak_label(window.center_cm1)} +/- {window.tolerance_cm1:g}",
            )
        ax.set_title(f"Every {every_n}-th spectrum with target peak windows")
        ax.legend(title=legend_title_for_mode(x_mode), fontsize=7, ncol=2)

    def plot_gradient_spectra(self, ax, every_n, x_mode, show_legend=True):
        self.plot_sequence_spectra(ax, every_n, x_mode, gradient=True)
        ax.set_title(f"Every {every_n}-th spectrum")
        if show_legend:
            ax.legend(title=legend_title_for_mode(x_mode), fontsize=7, ncol=2)

    def plot_sequence_spectra(self, ax, every_n, x_mode, gradient):
        sequence_values = selected_sequence_values(self.result.data, every_n)
        cmap = colormaps["RdYlGn"]
        color_values = cmap(np.linspace(0, 1, len(sequence_values))) if gradient and len(sequence_values) else [None] * len(sequence_values)
        for seq, color in zip(sequence_values, color_values):
            mask = self.result.data.sequence_index == seq
            order = np.argsort(self.result.data.raman_cm1[mask])
            x = self.result.data.raman_cm1[mask][order]
            y = self.result.data.intensity[mask][order]
            label_value = self.result.data.time_s[mask][0] if x_mode == "time" else seq
            label = f"{label_value:.2f} s" if x_mode == "time" else f"Seq {int(label_value)}"
            kwargs = {"linewidth": 1.0, "label": label}
            if color is not None:
                kwargs["color"] = color
            ax.plot(x, y, **kwargs)
        ax.set_xlabel("Raman shift (cm$^{-1}$)")
        ax.set_ylabel("Intensity")
        ax.grid(True, alpha=0.3)
        ax.invert_xaxis()

    def plot_peak_positions(self, ax, x_mode):
        for series in self.result.peak_series:
            x = x_values_for_mode(series, x_mode)
            ax.plot(x, series.peak_position_cm1, marker="o", markersize=3, linewidth=1, label=f"{format_peak_label(series.window.center_cm1)} +/- {series.window.tolerance_cm1:g}")
        ax.set_xlabel(x_label_for_mode(x_mode))
        ax.set_ylabel("Peak position (cm$^{-1}$)")
        ax.set_title(f"Peak position vs {x_label_for_mode(x_mode).lower()}")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)

    def plot_peak_intensities(self, ax, x_mode):
        for series in self.result.peak_series:
            x = x_values_for_mode(series, x_mode)
            ax.plot(x, series.peak_intensity, marker="o", markersize=3, linewidth=1, label=f"{format_peak_label(series.window.center_cm1)} +/- {series.window.tolerance_cm1:g}")
        ax.set_xlabel(x_label_for_mode(x_mode))
        ax.set_ylabel("Peak intensity")
        ax.set_title(f"Peak intensity vs {x_label_for_mode(x_mode).lower()}")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)

    def plot_ratios(self, ax, x_mode):
        norm_label = format_peak_label(self.result.normalized_peak_cm1)
        for ratio in self.result.ratios:
            if np.isclose(ratio.center_cm1, ratio.normalized_center_cm1):
                continue
            x = x_values_for_mode(ratio, x_mode)
            ax.plot(x, ratio.ratio, marker="o", markersize=3, linewidth=1, label=f"{format_peak_label(ratio.center_cm1)} / {norm_label}")
        ax.axhline(1.0, linestyle="--", linewidth=1.2, color="k", label=f"{norm_label} = 1")
        ax.set_xlabel(x_label_for_mode(x_mode))
        ax.set_ylabel("Peak intensity ratio")
        ax.set_title(f"Peak intensity ratios normalized to {norm_label}")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)

    def current_x_mode(self):
        return "time" if self.rb_time.GetValue() else "sequence"

    def clear_insitu_figures(self):
        for figure, canvas, message in [
            (self.figure_windows, self.canvas_windows, "Load an Insitu EChem Raman sequence file to preview peak windows."),
            (self.figure_analysis, self.canvas_analysis, "Load a file and define peak windows to show analysis results."),
        ]:
            figure.clear()
            ax = figure.add_subplot(111)
            ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            canvas.draw()

    def choose_output_folder(self):
        with wx.DirDialog(self, "Choose output folder", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return ""
            return dialog.GetPath()

    def base_output_stem(self):
        if self.raw_path:
            return Path(self.raw_path).stem
        if self.in_memory_data is not None:
            return self.in_memory_data.name
        return "insitu_echem"

    def save_individual_plot(self, plot_name, plotter, csv_writer):
        if self.result is None:
            self.show_warning("Load and analyze a Raman sequence file before saving.")
            return
        folder = self.choose_output_folder()
        if not folder:
            return
        folder = Path(folder)
        stem = self.base_output_stem()
        image_path = folder / f"{stem}_{plot_name}.png"
        data_path = folder / f"{stem}_{plot_name}.csv"
        figure = Figure(figsize=(8, 5))
        ax = figure.add_subplot(111)
        plotter(ax, self.current_x_mode())
        figure.tight_layout(pad=1.2)
        figure.savefig(image_path, dpi=200)
        csv_writer(data_path)
        self.log(f"Saved {plot_name}: {image_path}; {data_path}")

    def on_save_spectra(self, event):
        def write_csv(path):
            every_n = self.read_every_n(self.tc_result_every_n, "Every N for result spectra")
            sequence_values = selected_sequence_values(self.result.data, every_n)
            with Path(path).open("w", newline="", encoding="utf-8-sig") as handle:
                writer = __import__("csv").writer(handle)
                writer.writerow(["sequence_index", "time_s", "raman_cm1", "intensity"])
                for seq in sequence_values:
                    mask = self.result.data.sequence_index == seq
                    for time_s, raman, intensity in zip(
                        self.result.data.time_s[mask],
                        self.result.data.raman_cm1[mask],
                        self.result.data.intensity[mask],
                    ):
                        writer.writerow([int(seq), float(time_s), float(raman), float(intensity)])

        self.save_individual_plot(
            "spectra",
            lambda ax, x_mode: self.plot_gradient_spectra(ax, self.read_every_n(self.tc_result_every_n, "Every N for result spectra"), x_mode),
            write_csv,
        )

    def on_save_positions(self, event):
        self.save_individual_plot("peak_positions", self.plot_peak_positions, lambda path: save_peak_summary_csv(self.result, path))

    def on_save_intensities(self, event):
        self.save_individual_plot("peak_intensities", self.plot_peak_intensities, lambda path: save_peak_summary_csv(self.result, path))

    def on_save_ratios(self, event):
        self.save_individual_plot("ratios", self.plot_ratios, lambda path: save_ratio_csv(self.result, path))

    def show_warning(self, message):
        wx.MessageBox(message, "Insitu EChem warning", wx.OK | wx.ICON_WARNING, self)

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.AppendText(f"[{stamp}] {message}\n")


class RamanSubstrateBaselinePanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.raw_path = ""
        self.raw_spectrum = None
        self.wire_path = ""
        self.wire_spectrum = None
        self.result = None
        self.fit_running = False
        self.build_ui()

    def build_ui(self):
        root = wx.BoxSizer(wx.HORIZONTAL)
        root.Add(self.build_left_panel(), 0, wx.EXPAND | wx.ALL, 8)
        root.Add(self.build_right_panel(), 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(root)

    def build_left_panel(self):
        scrolled = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scrolled.SetScrollRate(0, 20)
        scrolled.SetMinSize((520, -1))
        box = wx.StaticBoxSizer(wx.VERTICAL, scrolled, "Substrate Baseline")

        self.btn_load_raw = wx.Button(scrolled, label="Load txt")
        self.lbl_raw = wx.StaticText(scrolled, label="No Raman file loaded")
        self.btn_load_raw.Bind(wx.EVT_BUTTON, self.on_load_raw)
        box.Add(self.add_load_row(self.btn_load_raw, self.lbl_raw), 0, wx.EXPAND | wx.ALL, 5)

        method_grid = wx.FlexGridSizer(rows=1, cols=2, vgap=6, hgap=6)
        method_grid.AddGrowableCol(1, 1)
        self.choice_method = wx.Choice(scrolled, choices=[METHOD_ASPLS, METHOD_DRPLS, METHOD_BACKCOR])
        self.choice_method.SetStringSelection(METHOD_ASPLS)
        self.choice_method.Bind(wx.EVT_CHOICE, self.on_method_changed)
        method_grid.Add(wx.StaticText(scrolled, label="Fitting method"), 0, wx.ALIGN_CENTER_VERTICAL)
        method_grid.Add(self.choice_method, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        box.Add(method_grid, 0, wx.EXPAND | wx.ALL, 5)

        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rb_auto = wx.RadioButton(scrolled, label="Auto", style=wx.RB_GROUP)
        self.rb_manual = wx.RadioButton(scrolled, label="Manual")
        self.rb_auto.SetValue(True)
        self.rb_auto.Bind(wx.EVT_RADIOBUTTON, self.on_mode_changed)
        self.rb_manual.Bind(wx.EVT_RADIOBUTTON, self.on_mode_changed)
        mode_row.Add(wx.StaticText(scrolled, label="Parameter mode"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        mode_row.Add(self.rb_auto, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)
        mode_row.Add(self.rb_manual, 0, wx.ALIGN_CENTER_VERTICAL)
        box.Add(mode_row, 0, wx.EXPAND | wx.ALL, 5)

        param_grid = wx.FlexGridSizer(rows=3, cols=2, vgap=6, hgap=6)
        param_grid.AddGrowableCol(1, 1)
        self.lbl_param1 = wx.StaticText(scrolled, label="")
        self.lbl_param2 = wx.StaticText(scrolled, label="")
        self.lbl_param3 = wx.StaticText(scrolled, label="")
        self.tc_param1 = wx.TextCtrl(scrolled)
        self.tc_param2 = wx.TextCtrl(scrolled)
        self.tc_param3 = wx.TextCtrl(scrolled)
        param_grid.Add(self.lbl_param1, 0, wx.ALIGN_CENTER_VERTICAL)
        param_grid.Add(self.tc_param1, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        param_grid.Add(self.lbl_param2, 0, wx.ALIGN_CENTER_VERTICAL)
        param_grid.Add(self.tc_param2, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        param_grid.Add(self.lbl_param3, 0, wx.ALIGN_CENTER_VERTICAL)
        param_grid.Add(self.tc_param3, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        box.Add(param_grid, 0, wx.EXPAND | wx.ALL, 5)

        self.btn_load_wire = wx.Button(scrolled, label="Load WiRE software analysed results")
        self.lbl_wire = wx.StaticText(scrolled, label="No WiRE result loaded")
        self.btn_load_wire.Bind(wx.EVT_BUTTON, self.on_load_wire)
        box.Add(self.add_load_row(self.btn_load_wire, self.lbl_wire), 0, wx.EXPAND | wx.ALL, 5)

        output_grid = wx.FlexGridSizer(rows=1, cols=2, vgap=6, hgap=6)
        output_grid.AddGrowableCol(1, 1)
        self.tc_output_name = wx.TextCtrl(scrolled, value="")
        output_grid.Add(wx.StaticText(scrolled, label="Output filename"), 0, wx.ALIGN_CENTER_VERTICAL)
        output_grid.Add(self.tc_output_name, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        box.Add(output_grid, 0, wx.EXPAND | wx.ALL, 5)

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_fit = wx.Button(scrolled, label="Fit")
        self.btn_save = wx.Button(scrolled, label="Save")
        self.btn_save.Disable()
        self.btn_fit.Bind(wx.EVT_BUTTON, self.on_fit)
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)
        button_row.Add(self.btn_fit, 1, wx.EXPAND | wx.RIGHT, 5)
        button_row.Add(self.btn_save, 1, wx.EXPAND)
        box.Add(button_row, 0, wx.EXPAND | wx.ALL, 5)

        scrolled.SetSizer(box)
        self.update_parameter_controls()
        return scrolled

    def build_right_panel(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.preview_notebook = wx.Notebook(panel)
        self.figure_preview, self.canvas_preview = self.add_preview_page("Preview")
        sizer.Add(self.preview_notebook, 1, wx.EXPAND)

        log_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Raman log")
        self.log_box = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        self.log_box.SetMinSize((-1, 105))
        log_box.Add(self.log_box, 0, wx.EXPAND | wx.ALL, 6)
        sizer.Add(log_box, 0, wx.EXPAND | wx.TOP, 6)

        panel.SetSizer(sizer)
        self.clear_preview()
        return panel

    def add_preview_page(self, title):
        panel = wx.Panel(self.preview_notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        figure = Figure(figsize=(8, 7))
        canvas = FigureCanvasWxAgg(panel, -1, figure)
        sizer.Add(canvas, 1, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(sizer)
        self.preview_notebook.AddPage(panel, title)
        return figure, canvas

    @staticmethod
    def add_load_row(button, label):
        button.SetMinSize((215, -1))
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(button, 0, wx.RIGHT, 6)
        row.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        return row

    def on_load_raw(self, event):
        paths = self.open_txt_file("Load Raman TXT file")
        if not paths:
            return
        path = paths[0]
        try:
            self.raw_spectrum = read_raman_txt(path)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.raw_path = path
        self.result = None
        self.lbl_raw.SetLabel(Path(path).name)
        self.tc_output_name.SetValue(default_output_name(path))
        self.btn_save.Disable()
        self.draw_loaded_raw()
        self.log(f"Loaded Raman file: {Path(path).name}.")
        if self.rb_auto.GetValue():
            self.start_fit("Auto fitting after Raman file load.")

    def on_load_wire(self, event):
        paths = self.open_txt_file("Load WiRE software analysed results")
        if not paths:
            return
        path = paths[0]
        try:
            self.wire_spectrum = read_raman_txt(path)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.wire_path = path
        self.lbl_wire.SetLabel(Path(path).name)
        self.log(f"Loaded WiRE software analysed results: {Path(path).name}.")
        if self.result is not None:
            self.draw_result()

    def open_txt_file(self, title):
        with wx.FileDialog(
            self,
            title,
            wildcard="Text files (*.txt)|*.txt|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return []
            return [dialog.GetPath()]

    def on_method_changed(self, event):
        self.update_parameter_controls()
        if self.raw_spectrum is not None and self.rb_auto.GetValue():
            self.start_fit("Auto fitting after method change.")

    def on_mode_changed(self, event):
        self.update_parameter_controls()
        if self.raw_spectrum is not None and self.rb_auto.GetValue():
            self.start_fit("Auto fitting after switching to Auto mode.")

    def on_fit(self, event):
        self.start_fit("Starting Raman baseline fit.")

    def start_fit(self, message):
        if self.fit_running:
            self.show_warning("A Raman baseline fit is already running.")
            return
        if self.raw_spectrum is None:
            self.show_warning("Load a Raman file before fitting.")
            return
        try:
            settings = self.read_settings()
        except Exception as exc:
            self.show_warning(str(exc))
            return

        self.fit_running = True
        self.update_buttons()
        self.log(message)
        threading.Thread(target=self.fit_worker, args=(self.raw_spectrum, settings), daemon=True).start()

    def fit_worker(self, spectrum, settings):
        try:
            result = fit_raman_baseline(spectrum, settings)
            wx.CallAfter(self.on_fit_result, result)
        except Exception as exc:
            wx.CallAfter(self.on_fit_error, f"Raman baseline fit failed: {exc}")

    def on_fit_result(self, result):
        self.result = result
        self.fit_running = False
        self.update_buttons()
        self.draw_result()
        self.log_selected_parameters(result)
        if result.auto:
            self.log(f"Evaluated {len(result.search_records)} automatic parameter candidate(s).")

    def on_fit_error(self, message):
        self.fit_running = False
        self.update_buttons()
        self.log(message)
        self.show_warning(message)

    def on_save(self, event):
        if self.result is None:
            self.show_warning("Run Raman baseline fitting before saving.")
            return
        output_name = self.tc_output_name.GetValue().strip()
        if not output_name:
            self.show_warning("Output filename is empty.")
            return
        output_path = Path(output_name)
        if not output_path.is_absolute():
            output_path = Path(self.raw_path).parent / output_path
        if output_path.suffix == "":
            output_path = output_path.with_suffix(".txt")
        try:
            saved_path = save_corrected_txt(self.result, output_path)
        except Exception as exc:
            self.show_warning(str(exc))
            return
        self.log(f"Saved corrected Raman spectrum: {saved_path}")

    def read_settings(self):
        method = self.choice_method.GetStringSelection()
        auto = self.rb_auto.GetValue()
        if method == METHOD_BACKCOR:
            fraction = self.parse_single_float(self.tc_param3.GetValue(), "Below-baseline fraction")
            if auto:
                return RamanBaselineSettings(
                    method=method,
                    auto=True,
                    order_values=self.parse_int_list(self.tc_param1.GetValue(), "Orders"),
                    threshold_values=parse_numeric_list(self.tc_param2.GetValue(), "Thresholds"),
                    below_baseline_fraction=fraction,
                )
            return RamanBaselineSettings(
                method=method,
                auto=False,
                order_value=self.parse_single_int(self.tc_param1.GetValue(), "Order"),
                threshold_value=self.parse_single_float(self.tc_param2.GetValue(), "Threshold"),
                below_baseline_fraction=fraction,
            )
        if auto:
            return RamanBaselineSettings(
                method=method,
                auto=True,
                lambda_values=parse_numeric_list(self.tc_param1.GetValue(), "lambda values"),
                secondary_values=parse_numeric_list(self.tc_param2.GetValue(), self.secondary_label(method) + " values"),
            )
        return RamanBaselineSettings(
            method=method,
            auto=False,
            lambda_value=self.parse_single_float(self.tc_param1.GetValue(), "lambda"),
            secondary_value=self.parse_single_float(self.tc_param2.GetValue(), self.secondary_label(method)),
        )

    @staticmethod
    def parse_int_list(text, name):
        values = parse_numeric_list(text, name)
        orders = []
        for value in values:
            order = int(value)
            if order < 1 or abs(value - order) > 1e-12:
                raise RamanBaselineError(f"{name} must contain positive integers.")
            orders.append(order)
        return tuple(orders)

    @classmethod
    def parse_single_int(cls, text, name):
        values = cls.parse_int_list(text, name)
        if len(values) != 1:
            raise RamanBaselineError(f"Manual {name} must contain exactly one integer.")
        return values[0]

    @staticmethod
    def parse_single_float(text, name):
        values = parse_numeric_list(text, name)
        if len(values) != 1:
            raise RamanBaselineError(f"Manual {name} must contain exactly one value.")
        return values[0]

    def update_parameter_controls(self):
        method = self.choice_method.GetStringSelection() or METHOD_ASPLS
        auto = self.rb_auto.GetValue()
        show_backcor_fraction = method == METHOD_BACKCOR
        if method == METHOD_BACKCOR:
            self.lbl_param1.SetLabel("Orders" if auto else "Order")
            self.lbl_param2.SetLabel("Thresholds" if auto else "Threshold")
            self.lbl_param3.SetLabel("Below-baseline fraction")
            if auto:
                self.tc_param1.SetValue(self.format_values(BACKCOR_ORDER_VALUES))
                self.tc_param2.SetValue(self.format_values(BACKCOR_THRESHOLD_VALUES))
            else:
                self.tc_param1.SetValue("4")
                self.tc_param2.SetValue("0.01")
            self.tc_param3.SetValue(f"{DEFAULT_BACKCOR_BELOW_BASELINE_FRACTION:g}")
        else:
            secondary = self.secondary_label(method)
            self.lbl_param1.SetLabel("lambda values" if auto else "lambda")
            self.lbl_param2.SetLabel(f"{secondary} values" if auto else secondary)
            if auto:
                lambda_values = ASPLS_LAMBDA_VALUES if method == METHOD_ASPLS else DRPLS_LAMBDA_VALUES
                secondary_values = ASPLS_K_VALUES if method == METHOD_ASPLS else DRPLS_ETA_VALUES
                self.tc_param1.SetValue(self.format_values(lambda_values))
                self.tc_param2.SetValue(self.format_values(secondary_values))
            elif method == METHOD_ASPLS:
                self.tc_param1.SetValue("1e6")
                self.tc_param2.SetValue("1.0")
            else:
                self.tc_param1.SetValue("1e5")
                self.tc_param2.SetValue("0.1")
        self.lbl_param3.Show(show_backcor_fraction)
        self.tc_param3.Show(show_backcor_fraction)
        self.Layout()

    @staticmethod
    def secondary_label(method):
        return "eta" if method == METHOD_DRPLS else "k"

    @staticmethod
    def format_values(values):
        return ", ".join(f"{value:g}" for value in values)

    def update_buttons(self):
        enabled = not self.fit_running
        self.btn_load_raw.Enable(enabled)
        self.btn_load_wire.Enable(enabled)
        self.btn_fit.Enable(enabled)
        self.btn_save.Enable(enabled and self.result is not None)

    def draw_loaded_raw(self):
        self.figure_preview.clear()
        raw_ax = self.figure_preview.add_subplot(211)
        corrected_ax = self.figure_preview.add_subplot(212)
        x = self.raw_spectrum.raman_shift
        y = self.raw_spectrum.intensity
        raw_ax.plot(x, y, label="Raw Raman spectrum", linewidth=1.2)
        raw_ax.set_title("Raw Raman spectrum")
        raw_ax.set_xlabel("Raman shift / cm$^{-1}$")
        raw_ax.set_ylabel("Intensity")
        self.apply_raman_axis_style(raw_ax, x)
        corrected_ax.text(
            0.5,
            0.5,
            "Run fitting to show the corrected Raman spectrum.",
            ha="center",
            va="center",
            transform=corrected_ax.transAxes,
        )
        corrected_ax.set_axis_off()
        self.figure_preview.tight_layout(pad=1.2)
        self.canvas_preview.draw()

    def draw_result(self):
        self.figure_preview.clear()
        raw_ax = self.figure_preview.add_subplot(211)
        corrected_ax = self.figure_preview.add_subplot(212)
        x = self.result.spectrum.raman_shift
        raw_ax.plot(x, self.result.spectrum.intensity, label="Raw Raman spectrum", linewidth=1.2)
        raw_ax.plot(x, self.result.baseline, label="Estimated baseline", linewidth=1.8)
        raw_ax.set_title("Raw Raman spectrum with estimated baseline")
        raw_ax.set_xlabel("Raman shift / cm$^{-1}$")
        raw_ax.set_ylabel("Intensity")
        self.apply_raman_axis_style(raw_ax, x)

        corrected_ax.plot(x, self.result.corrected, label="Baseline-corrected Raman spectrum", linewidth=1.2)
        if self.wire_spectrum is not None:
            wire_on_x = interpolate_to_reference_x(self.wire_spectrum.raman_shift, self.wire_spectrum.intensity, x)
            corrected_ax.plot(x, wire_on_x, label="WiRE software analysed results", linewidth=1.2)
        corrected_ax.axhline(0, linewidth=1.0, color="k")
        corrected_ax.set_title("Baseline-corrected Raman spectrum")
        corrected_ax.set_xlabel("Raman shift / cm$^{-1}$")
        corrected_ax.set_ylabel("Corrected intensity")
        self.apply_raman_axis_style(corrected_ax, x)
        self.figure_preview.tight_layout(pad=1.2)
        self.canvas_preview.draw()

    def clear_preview(self):
        self.figure_preview.clear()
        raw_ax = self.figure_preview.add_subplot(211)
        corrected_ax = self.figure_preview.add_subplot(212)
        raw_ax.text(
            0.5,
            0.5,
            "Load a Raman file to preview substrate baseline fitting.",
            ha="center",
            va="center",
            transform=raw_ax.transAxes,
        )
        corrected_ax.text(
            0.5,
            0.5,
            "Run fitting to show the corrected Raman spectrum.",
            ha="center",
            va="center",
            transform=corrected_ax.transAxes,
        )
        raw_ax.set_axis_off()
        corrected_ax.set_axis_off()
        self.canvas_preview.draw()

    def collect_app_parameters(self):
        return {
            "raw_path": self.raw_path,
            "wire_path": self.wire_path,
            "method": self.choice_method.GetStringSelection(),
            "auto": self.rb_auto.GetValue(),
            "param1": self.tc_param1.GetValue(),
            "param2": self.tc_param2.GetValue(),
            "param3": self.tc_param3.GetValue(),
            "output_name": self.tc_output_name.GetValue(),
        }

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        method = str(params.get("method", METHOD_ASPLS))
        if self.choice_method.FindString(method) == wx.NOT_FOUND:
            method = METHOD_ASPLS
        self.choice_method.SetStringSelection(method)
        auto = bool(params.get("auto", True))
        self.rb_auto.SetValue(auto)
        self.rb_manual.SetValue(not auto)
        self.update_parameter_controls()
        self.tc_param1.SetValue(str(params.get("param1", self.tc_param1.GetValue())))
        self.tc_param2.SetValue(str(params.get("param2", self.tc_param2.GetValue())))
        self.tc_param3.SetValue(str(params.get("param3", self.tc_param3.GetValue())))
        self.tc_output_name.SetValue(str(params.get("output_name", self.tc_output_name.GetValue())))
        self.result = None
        self.btn_save.Disable()

        raw_path = str(params.get("raw_path", "") or "")
        if raw_path:
            try:
                self.raw_spectrum = read_raman_txt(raw_path)
                self.raw_path = raw_path
                self.lbl_raw.SetLabel(Path(raw_path).name)
                if not self.tc_output_name.GetValue().strip():
                    self.tc_output_name.SetValue(default_output_name(raw_path))
                self.draw_loaded_raw()
                self.log(f"Restored Raman file: {Path(raw_path).name}.")
            except Exception as exc:
                self.raw_path = raw_path
                self.raw_spectrum = None
                self.lbl_raw.SetLabel(Path(raw_path).name)
                self.log(f"Could not restore Raman file: {exc}")
        else:
            self.raw_path = ""
            self.raw_spectrum = None
            self.lbl_raw.SetLabel("No Raman file loaded")

        wire_path = str(params.get("wire_path", "") or "")
        if wire_path:
            try:
                self.wire_spectrum = read_raman_txt(wire_path)
                self.wire_path = wire_path
                self.lbl_wire.SetLabel(Path(wire_path).name)
                self.log(f"Restored WiRE result: {Path(wire_path).name}.")
            except Exception as exc:
                self.wire_path = wire_path
                self.wire_spectrum = None
                self.lbl_wire.SetLabel(Path(wire_path).name)
                self.log(f"Could not restore WiRE result: {exc}")
        else:
            self.wire_path = ""
            self.wire_spectrum = None
            self.lbl_wire.SetLabel("No WiRE result loaded")
        if self.raw_spectrum is None:
            self.clear_preview()

    def log_selected_parameters(self, result):
        params = result.selected_parameters
        if result.method == METHOD_BACKCOR:
            self.log(
                f"{result.method} selected order={int(params['order'])}, "
                f"threshold={float(params['threshold']):.6g}, "
                f"below-baseline fraction={float(params['below_baseline_fraction']):.6g}, "
                f"cost_function={params['cost_function']}, "
                f"iterations={int(params['iterations'])}, score={float(params['score']):.4g}."
            )
            return
        secondary_name = "eta" if result.method == METHOD_DRPLS else "k"
        self.log(
            f"{result.method} selected lambda={float(params['lambda']):.6g}, "
            f"{secondary_name}={float(params[secondary_name]):.6g}, "
            f"iterations={int(params['iterations'])}, score={float(params['score']):.4g}."
        )

    @staticmethod
    def apply_raman_axis_style(ax, x):
        ax.grid(True, which="both", axis="both")
        ax.autoscale(enable=True, axis="both", tight=True)
        if len(x) > 1 and x[0] > x[-1]:
            ax.invert_xaxis()
        if ax.lines:
            ax.legend(fontsize=8)

    def show_warning(self, message):
        wx.MessageBox(message, "Raman warning", wx.OK | wx.ICON_WARNING, self)

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.AppendText(f"[{stamp}] {message}\n")

