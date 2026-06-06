"""Independent GUI workspace panels."""

__all__ = [
    "AfmAnalysisPanel",
    "AfmControllerPanel",
    "AfmKpfmPanel",
    "ApsAnalysisPanel",
    "RamanAnalysisPanel",
    "TpcLaserDiodePanel",
]

_EXPORTS = {
    "AfmAnalysisPanel": ("ca_app.gui.panels.afm_analysis_panel", "AfmAnalysisPanel"),
    "AfmControllerPanel": ("ca_app.gui.panels.afm_controller_panel", "AfmControllerPanel"),
    "AfmKpfmPanel": ("ca_app.gui.panels.afm_kpfm_panel", "AfmKpfmPanel"),
    "ApsAnalysisPanel": ("ca_app.gui.panels.aps_panel", "ApsAnalysisPanel"),
    "RamanAnalysisPanel": ("ca_app.gui.panels.raman_panel", "RamanAnalysisPanel"),
    "TpcLaserDiodePanel": ("ca_app.gui.panels.tpc_panel", "TpcLaserDiodePanel"),
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, class_name = _EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), class_name)
    globals()[name] = value
    return value
