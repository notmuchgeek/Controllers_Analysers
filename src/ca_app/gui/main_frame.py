"""Main application frame for Controllers & Analysers."""

from __future__ import annotations

import json
from pathlib import Path

import wx

from ca_app.gui.panels.afm_kpfm_panel import AfmKpfmPanel
from ca_app.gui.panels.aps_panel import ApsAnalysisPanel
from ca_app.gui.panels.raman_panel import RamanAnalysisPanel
from ca_app.gui.panels.tpc_panel import TpcLaserDiodePanel


WORKSPACE_NAMES = ("AFM/KPFM", "APS", "TPC", "Raman")
DEFAULT_WORKSPACE = "AFM/KPFM"
STATE_FILENAME = "app_state.json"
RESTORE_VIEW = "view"
RESTORE_TAB = "tab"
RESTORE_PARAMETERS = "parameters"
RESTORE_LEVELS = (RESTORE_VIEW, RESTORE_TAB, RESTORE_PARAMETERS)
DEFAULT_RESTORE_LEVEL = RESTORE_VIEW


def normalize_workspace_name(workspace):
    return workspace if workspace in WORKSPACE_NAMES else DEFAULT_WORKSPACE


def normalize_restore_level(level):
    return level if level in RESTORE_LEVELS else DEFAULT_RESTORE_LEVEL


def normalize_app_state(data):
    if not isinstance(data, dict):
        data = {}
    return {
        "version": 2,
        "restore_level": normalize_restore_level(data.get("restore_level")),
        "last_workspace": normalize_workspace_name(data.get("last_workspace")),
        "tabs": data.get("tabs") if isinstance(data.get("tabs"), dict) else {},
        "parameters": data.get("parameters") if isinstance(data.get("parameters"), dict) else {},
    }


def load_app_state(path):
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return normalize_app_state({})
    return normalize_app_state(data)


def save_app_state(path, state):
    normalized = normalize_app_state(state)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2)


def load_workspace_state(path):
    return load_app_state(path)["last_workspace"]


def save_workspace_state(path, workspace):
    save_app_state(path, {"last_workspace": workspace})


class CaAppFrame(wx.Frame):
    """Top-level workspace shell."""

    def __init__(self):
        super().__init__(None, title="Controllers & Analysers", size=(1680, 940))
        self.workspace_panels = {}
        self.view_menu_items = {}
        self.restore_menu_items = {}
        self.app_state = self.load_app_state()
        self.restore_level = self.app_state["restore_level"]
        self.active_workspace = self.app_state["last_workspace"]
        self.restoring_state = False
        self.build_ui()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Centre()

    def build_ui(self):
        self.build_menu_bar()

        root = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)
        self.workspace_container = wx.Panel(root)
        self.workspace_sizer = wx.BoxSizer(wx.VERTICAL)

        self.workspace_panels = {
            "AFM/KPFM": AfmKpfmPanel(self.workspace_container),
            "APS": ApsAnalysisPanel(self.workspace_container),
            "TPC": TpcLaserDiodePanel(self.workspace_container),
            "Raman": RamanAnalysisPanel(self.workspace_container),
        }

        for name, panel in self.workspace_panels.items():
            self.workspace_sizer.Add(panel, 1, wx.EXPAND)
            panel.Show(name == self.active_workspace)

        self.workspace_container.SetSizer(self.workspace_sizer)
        root_sizer.Add(self.workspace_container, 1, wx.EXPAND)
        root.SetSizer(root_sizer)
        self.SetMinSize((1260, 760))
        self.bind_notebook_save_events()
        self.restore_saved_state()

    def build_menu_bar(self):
        menu_bar = wx.MenuBar()

        view_menu = wx.Menu()
        for name in WORKSPACE_NAMES:
            item = view_menu.AppendRadioItem(wx.ID_ANY, name)
            self.view_menu_items[name] = item
            self.Bind(
                wx.EVT_MENU,
                lambda event, workspace=name: self.on_view_workspace(event, workspace),
                id=item.GetId(),
            )
        self.view_menu_items[self.active_workspace].Check(True)
        menu_bar.Append(view_menu, "&View")

        restore_menu = wx.Menu()
        for level, label in [
            (RESTORE_VIEW, "View"),
            (RESTORE_TAB, "Tab"),
            (RESTORE_PARAMETERS, "Parameters"),
        ]:
            item = restore_menu.AppendRadioItem(wx.ID_ANY, label)
            self.restore_menu_items[level] = item
            self.Bind(
                wx.EVT_MENU,
                lambda event, restore_level=level: self.on_restore_level(event, restore_level),
                id=item.GetId(),
            )
        self.restore_menu_items[self.restore_level].Check(True)
        menu_bar.Append(restore_menu, "Restore")

        about_menu = wx.Menu()
        versions_item = about_menu.Append(wx.ID_ANY, "&Versions")
        developer_item = about_menu.Append(wx.ID_ANY, "&Developer")
        about_item = about_menu.Append(wx.ID_ABOUT, "&About")
        self.Bind(wx.EVT_MENU, self.on_versions, id=versions_item.GetId())
        self.Bind(wx.EVT_MENU, self.on_developer, id=developer_item.GetId())
        self.Bind(wx.EVT_MENU, self.on_about, id=about_item.GetId())
        menu_bar.Append(about_menu, "&About")

        self.SetMenuBar(menu_bar)

    def build_placeholder_workspace(self, parent, name):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(panel, label=f"{name} workspace")
        font = label.GetFont()
        font.SetPointSize(font.GetPointSize() + 4)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        label.SetFont(font)
        sizer.AddStretchSpacer(1)
        sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 12)
        sizer.Add(
            wx.StaticText(panel, label="No tools have been added to this view yet."),
            0,
            wx.ALIGN_CENTER | wx.BOTTOM,
            12,
        )
        sizer.AddStretchSpacer(1)
        panel.SetSizer(sizer)
        return panel

    def on_view_workspace(self, event, workspace):
        self.show_workspace(workspace)

    def on_restore_level(self, event, restore_level):
        self.restore_level = normalize_restore_level(restore_level)
        if self.restore_level in self.restore_menu_items:
            self.restore_menu_items[self.restore_level].Check(True)
        self.save_current_app_state()

    def show_workspace(self, workspace):
        if workspace not in self.workspace_panels:
            return
        self.active_workspace = workspace
        for name, panel in self.workspace_panels.items():
            panel.Show(name == workspace)
        if workspace in self.view_menu_items:
            self.view_menu_items[workspace].Check(True)
        self.workspace_container.Layout()
        self.save_current_app_state()

    def state_file_path(self):
        folder = wx.StandardPaths.Get().GetUserLocalDataDir()
        return Path(folder) / STATE_FILENAME

    def load_app_state(self):
        return load_app_state(self.state_file_path())

    def load_last_workspace(self):
        return load_workspace_state(self.state_file_path())

    def save_last_workspace(self):
        try:
            self.save_current_app_state()
        except OSError:
            pass

    def save_current_app_state(self):
        if self.restoring_state:
            return
        state = {
            "version": 2,
            "restore_level": self.restore_level,
            "last_workspace": self.active_workspace,
            "tabs": {},
            "parameters": {},
        }
        if self.restore_level in {RESTORE_TAB, RESTORE_PARAMETERS}:
            state["tabs"] = self.collect_all_tab_state()
        if self.restore_level == RESTORE_PARAMETERS:
            state["parameters"] = self.collect_all_parameter_state()
        self.app_state = normalize_app_state(state)
        save_app_state(self.state_file_path(), self.app_state)

    def restore_saved_state(self):
        self.restoring_state = True
        try:
            if self.restore_level == RESTORE_PARAMETERS:
                self.apply_all_parameter_state(self.app_state.get("parameters", {}))
            self.show_workspace(self.active_workspace)
            if self.restore_level in {RESTORE_TAB, RESTORE_PARAMETERS}:
                self.apply_all_tab_state(self.app_state.get("tabs", {}))
        finally:
            self.restoring_state = False

    def collect_all_tab_state(self):
        return {
            name: self.collect_panel_tab_state(panel)
            for name, panel in self.workspace_panels.items()
        }

    def apply_all_tab_state(self, tabs):
        if not isinstance(tabs, dict):
            return
        for name, panel_state in tabs.items():
            panel = self.workspace_panels.get(name)
            if panel is not None:
                self.apply_panel_tab_state(panel, panel_state)
        self.workspace_container.Layout()

    def collect_all_parameter_state(self):
        result = {}
        for name, panel in self.workspace_panels.items():
            if hasattr(panel, "collect_app_parameters"):
                try:
                    result[name] = panel.collect_app_parameters()
                except Exception:
                    continue
        return result

    def apply_all_parameter_state(self, parameters):
        if not isinstance(parameters, dict):
            return
        for name, payload in parameters.items():
            panel = self.workspace_panels.get(name)
            if panel is not None and hasattr(panel, "apply_app_parameters"):
                try:
                    panel.apply_app_parameters(payload)
                except Exception:
                    continue

    def bind_notebook_save_events(self):
        for notebook in self.find_notebooks(self):
            notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_any_notebook_changed)

    def on_any_notebook_changed(self, event):
        event.Skip()
        if self.restore_level in {RESTORE_TAB, RESTORE_PARAMETERS}:
            wx.CallAfter(self.save_current_app_state)

    @classmethod
    def collect_panel_tab_state(cls, panel):
        return [
            {
                "selection": notebook.GetSelection(),
                "pages": [notebook.GetPageText(index) for index in range(notebook.GetPageCount())],
            }
            for notebook in cls.find_notebooks(panel)
        ]

    @classmethod
    def apply_panel_tab_state(cls, panel, state):
        if not isinstance(state, list):
            return
        pending_states = [item for item in state if isinstance(item, dict)]
        for notebook in cls.find_notebooks(panel):
            page_names = [notebook.GetPageText(index) for index in range(notebook.GetPageCount())]
            notebook_state = cls.match_notebook_state(page_names, pending_states)
            if not isinstance(notebook_state, dict) or notebook.GetPageCount() <= 0:
                continue
            selection = notebook_state.get("selection", 0)
            try:
                selection = int(selection)
            except (TypeError, ValueError):
                selection = 0
            selection = max(0, min(selection, notebook.GetPageCount() - 1))
            notebook.SetSelection(selection)

    @staticmethod
    def match_notebook_state(page_names, states):
        page_names = list(page_names)
        normalized_page_names = [CaAppFrame.normalize_tab_page_name(page) for page in page_names]
        for state in states:
            saved_pages = state.get("pages")
            if not isinstance(saved_pages, list):
                continue
            normalized_saved_pages = [CaAppFrame.normalize_tab_page_name(page) for page in saved_pages]
            if normalized_saved_pages == normalized_page_names:
                return state
        for state in states:
            saved_pages = state.get("pages")
            if not isinstance(saved_pages, list):
                continue
            normalized_saved_pages = [CaAppFrame.normalize_tab_page_name(page) for page in saved_pages]
            if normalized_saved_pages and all(page in normalized_page_names for page in normalized_saved_pages):
                return state
        return None

    @staticmethod
    def normalize_tab_page_name(page_name):
        if page_name == "Substrate Baseline":
            return "Baseline"
        return str(page_name)

    @classmethod
    def find_notebooks(cls, window):
        found = []
        if isinstance(window, wx.Notebook):
            found.append(window)
        for child in window.GetChildren():
            found.extend(cls.find_notebooks(child))
        return found

    def on_close(self, event):
        self.save_current_app_state()
        event.Skip()

    def on_versions(self, event):
        message = (
            "Controllers & Analysers\n"
            "Version: 0.14.0\n\n"
            "Restore\n"
            "  - View: remember the last opened workspace\n"
            "  - Tab: remember workspace and selected notebook tabs\n"
            "  - Parameters: remember workspace, tabs, loaded files, typed values, and selections\n\n"
            "AFM/KPFM\n"
            "  Controller\n"
            "    - Keithley current-source control over serial communication\n"
            "    - Current mode and intensity mode\n"
            "    - Quick Test ON/OFF source control\n"
            "    - Recurrent and Step sequence control\n"
            "    - Function control overlay for ON-stage profiles\n"
            "    - Current-intensity calibration CSV loading and fitting\n"
            "    - Source, function, calibration, and live-voltage previews\n"
            "    - Save/load parameters and source CSV export\n\n"
            "  Analysis\n"
            "    - CPD TIFF/PNG loading with TIFF metadata/raw-tag extraction\n"
            "    - CPD/Energy image previews, robust color scaling, selectable colormaps, and row/time profiles\n"
            "    - Illuminated-region comparison, mask previews, masked histograms, and HOPG Gaussian peak fitting\n"
            "    - Save/load parameters and app-state restore support\n\n"
            "Other Workspaces\n"
            "  APS\n"
            "    - Workfunction / DWF calibration analysis\n"
            "    - Reference APS and reference DWF loading\n"
            "    - APS spectrum HOMO and DOS analysis\n"
            "    - Raw-data previews with fitting/statistic regions\n"
            "    - Origin-style CSV export\n\n"
            "  TPC\n"
            "    - Laser diode red/green selection\n"
            "    - LD current limit enforcement\n"
            "    - Keithley current-source ON/OFF control\n"
            "    - Measured voltage/current readback\n"
            "    - Legacy LD output-power calculation\n\n"
            "  Raman\n"
            "    - Baseline analysis with asPLS, drPLS, and Polynomial/backcor fitting\n"
            "    - Optional WiRE software analysed result overlay\n"
            "    - Mapping WDF/TXT loading, unstacking, Origin TXT export, selected-sequence transfer, and WDF image/location preview\n"
            "    - Insitu EChem TXT/WDF sequence analysis for peak positions, intensities, and normalized ratios\n"
            "    - Electrical tab reserved for a future Raman tool"
        )
        wx.MessageBox(message, "Versions", wx.OK | wx.ICON_INFORMATION, self)

    def on_developer(self, event):
        message = (
            "Developer: Douglas\n"
            "Email: xiaocen.dong@hotmail.com\n"
            "Github: https://github.com/notmuchgeek\n"
            "X: https://x.com/XiaocenDong\n\n"
            "Please contact me for bug fixes, improvements, feature requests, "
            "or collaboration on adding new functions."
        )
        wx.MessageBox(message, "Developer", wx.OK | wx.ICON_INFORMATION, self)

    def on_about(self, event):
        message = (
            "Controllers & Analysers v14 is a wxPython workspace for experiment control "
            "and analysis workflows.\n\n"
            "Current tools include AFM/KPFM Keithley control and image analysis, APS/DWF/SPV "
            "analysis, TPC laser-diode control, Raman substrate-baseline correction, Raman "
            "Mapping WDF/TXT processing, and Raman Insitu EChem sequence analysis.\n\n"
            "The Restore menu controls whether the app remembers View, Tab, or Parameters "
            "between launches."
        )
        wx.MessageBox(message, "About", wx.OK | wx.ICON_INFORMATION, self)


class CaWxApp(wx.App):
    def OnInit(self):
        frame = CaAppFrame()
        frame.Show()
        return True


def main():
    app = CaWxApp(False)
    app.MainLoop()


if __name__ == "__main__":
    main()
