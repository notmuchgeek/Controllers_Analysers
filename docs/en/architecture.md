# Architecture

The application is layered around a wxPython GUI shell and independent workspace panels. The active source package is under `src/ca_app/`.

## Top Level

- `run_ca_app.py`: source-checkout launcher that prepends `src/` to `sys.path`.
- `src/ca_app/app.py`: console entry point.
- `src/ca_app/gui/main_frame.py`: main frame, menu bar, workspace switching, About/Versions dialogs, and `app_state.json` restore.
- `src/ca_app/constants.py`: import-safe defaults used across modules.

## Layers

- `gui`: wxPython panels, controls, plotting canvases, logs, dialogs, and state adapters.
- `core`: pure or mostly pure data processing, validation, fitting, parsing, and export helpers.
- `hardware`: serial communication primitives and Keithley SCPI helpers.
- `io`: file import/export boundaries that are not tied to GUI state.
- `runtime`: runtime support services, currently including usage logging; current AFM runtime remains in the controller panel to preserve behavior.
- `resources`: bundled calibration files and example parameter resources.
- `tests`: non-hardware unit tests plus wx GUI behavior tests where wxPython is available.

## Workspace Panels

- `afm_kpfm_panel.py`: notebook containing AFM/KPFM Controller and Analysis tabs.
- `afm_controller_panel.py`: AFM/KPFM Keithley UI and runtime sequence execution.
- `afm_analysis_panel.py`: CPD image analysis UI.
- `aps_panel.py`: APS/DWF/DOS/SPV analysis UI.
- `tpc_panel.py`: TPC laser-diode control UI.
- `raman_panel.py`: Raman Baseline, Mapping, Insitu EChem, and Electrical UI.

## Startup Flow

The main frame builds only the restored last workspace immediately, then preloads hidden workspaces during idle time. Preload priority is Raman, AFM/KPFM, APS, then TPC, and preloading never changes the active workspace. Saved tab and parameter state for unbuilt workspaces is preserved in `app_state.json` until those panels are created.

Within AFM/KPFM, the Controller tab is available immediately and the heavier Analysis tab can be built either when selected or during idle preload. The bundled default intensity calibration starts after the first UI pass and fits on a background thread; intensity-mode hardware actions are blocked until that fit is complete.

## State Flow

User actions update GUI controls. Panels read controls into settings objects or core function arguments. Core modules return structured results. GUI panels render plots/tables/logs and enable save actions.

Hardware control is stricter: `START` creates a frozen run snapshot before opening serial. Worker execution must not read live calibration or function controls after the run starts.

## Restore Flow

`main_frame.py` stores restore state in `app_state.json`:

- `View`: last top-level workspace only.
- `Tab`: workspace plus notebook selections.
- `Parameters`: workspace, tabs, and panel-supported typed values/paths.

Nested notebooks are restored by page names, not recursive order alone.

## Usage Logging

`src/ca_app/runtime/usage_logger.py` writes best-effort local JSONL logs under the software root, in `usage_logs/usage_YYYYMMDD.jsonl` next to `run_ca_app.py`.

The logger is for later workflow and performance analysis. It records sanitized events such as app open/close, workspace and tab changes, file load/save actions, fitting start/finish/failure, and operation durations. It records file basenames/extensions and coarse counts only. It must not record full paths, raw scientific data, hardware measurement traces, measured voltages/currents, calibration table rows, user comments, or exported result contents.

Logging failures are swallowed so logging never slows or blocks the GUI, hardware control, fitting, loading, or saving.



