"""Independent GUI workspace panels."""

from ca_app.gui.panels.afm_analysis_panel import AfmAnalysisPanel
from ca_app.gui.panels.afm_controller_panel import AfmControllerPanel
from ca_app.gui.panels.afm_kpfm_panel import AfmKpfmPanel
from ca_app.gui.panels.aps_panel import ApsAnalysisPanel
from ca_app.gui.panels.raman_panel import RamanAnalysisPanel
from ca_app.gui.panels.tpc_panel import TpcLaserDiodePanel

__all__ = [
    "AfmAnalysisPanel",
    "AfmControllerPanel",
    "AfmKpfmPanel",
    "ApsAnalysisPanel",
    "RamanAnalysisPanel",
    "TpcLaserDiodePanel",
]
