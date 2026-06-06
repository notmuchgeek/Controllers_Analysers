"""AFM/KPFM workspace panel."""

from __future__ import annotations

import wx

from ca_app.gui.panels.afm_analysis_panel import AfmAnalysisPanel
from ca_app.gui.panels.afm_controller_panel import AfmControllerPanel


class AfmKpfmPanel(wx.Panel):
    """Owns the AFM/KPFM Controller and Analysis notebook."""

    def __init__(self, parent):
        super().__init__(parent)
        self.build_ui()

    def build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)
        self.controller_page = AfmControllerPanel(self.notebook)
        self.analysis_page = AfmAnalysisPanel(self.notebook)
        self.notebook.AddPage(self.controller_page, "Controller")
        self.notebook.AddPage(self.analysis_page, "Analysis")
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)

    def collect_app_parameters(self):
        return {
            "controller": self.controller_page.collect_parameters(),
            "analysis": self.analysis_page.collect_parameters(),
        }

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        if isinstance(params.get("controller"), dict):
            self.controller_page.apply_parameters(params["controller"])
        if isinstance(params.get("analysis"), dict):
            self.analysis_page.apply_parameters(params["analysis"])
