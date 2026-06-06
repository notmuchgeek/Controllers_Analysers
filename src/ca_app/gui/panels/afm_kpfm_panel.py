"""AFM/KPFM workspace panel."""

from __future__ import annotations

import wx

from ca_app.gui.panels.afm_controller_panel import AfmControllerPanel


class AfmKpfmPanel(wx.Panel):
    """Owns the AFM/KPFM Controller and Analysis notebook."""

    def __init__(self, parent):
        super().__init__(parent)
        self.analysis_page = None
        self.analysis_placeholder = None
        self.pending_analysis_parameters = None
        self.build_ui()

    def build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)
        self.controller_page = AfmControllerPanel(self.notebook)
        self.analysis_placeholder = self.build_analysis_placeholder()
        self.notebook.AddPage(self.controller_page, "Controller")
        self.notebook.AddPage(self.analysis_placeholder, "Analysis")
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_notebook_page_changed)
        sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)

    def build_analysis_placeholder(self):
        panel = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(panel, label="Loading AFM/KPFM Analysis...")
        sizer.AddStretchSpacer(1)
        sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 12)
        sizer.AddStretchSpacer(1)
        panel.SetSizer(sizer)
        return panel

    def on_notebook_page_changed(self, event):
        if self.notebook.GetSelection() == 1:
            self.ensure_analysis_page()
        event.Skip()

    def ensure_active_lazy_pages(self):
        if self.notebook.GetSelection() == 1:
            self.ensure_analysis_page()

    def has_unloaded_lazy_pages(self):
        return self.analysis_page is None

    def preload_lazy_pages(self):
        selection = self.notebook.GetSelection()
        self.ensure_analysis_page()
        if self.notebook.GetSelection() != selection and 0 <= selection < self.notebook.GetPageCount():
            self.notebook.SetSelection(selection)

    def ensure_analysis_page(self):
        if self.analysis_page is not None:
            return self.analysis_page
        from ca_app.gui.panels.afm_analysis_panel import AfmAnalysisPanel

        was_selected = self.notebook.GetSelection() == 1
        self.notebook.DeletePage(1)
        self.analysis_page = AfmAnalysisPanel(self.notebook)
        self.notebook.InsertPage(1, self.analysis_page, "Analysis", select=was_selected)
        if isinstance(self.pending_analysis_parameters, dict):
            self.analysis_page.apply_parameters(self.pending_analysis_parameters)
            self.pending_analysis_parameters = None
        self.Layout()
        return self.analysis_page

    def collect_app_parameters(self):
        params = {
            "controller": self.controller_page.collect_parameters(),
        }
        if self.analysis_page is not None:
            params["analysis"] = self.analysis_page.collect_parameters()
        elif isinstance(self.pending_analysis_parameters, dict):
            params["analysis"] = self.pending_analysis_parameters
        return params

    def apply_app_parameters(self, params):
        if not isinstance(params, dict):
            return
        if isinstance(params.get("controller"), dict):
            self.controller_page.apply_parameters(params["controller"])
        if isinstance(params.get("analysis"), dict):
            if self.analysis_page is not None:
                self.analysis_page.apply_parameters(params["analysis"])
            else:
                self.pending_analysis_parameters = dict(params["analysis"])
