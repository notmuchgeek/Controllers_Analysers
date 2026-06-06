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
- `runtime`: planned extraction area for worker services; current AFM runtime remains in the controller panel to preserve behavior.
- `resources`: bundled calibration files and example parameter resources.
- `tests`: non-hardware unit tests plus wx GUI behavior tests where wxPython is available.

## Workspace Panels

- `afm_kpfm_panel.py`: notebook containing AFM/KPFM Controller and Analysis tabs.
- `afm_controller_panel.py`: AFM/KPFM Keithley UI and runtime sequence execution.
- `afm_analysis_panel.py`: CPD image analysis UI.
- `aps_panel.py`: APS/DWF/DOS/SPV analysis UI.
- `tpc_panel.py`: TPC laser-diode control UI.
- `raman_panel.py`: Raman Baseline, Mapping, Insitu EChem, and Electrical UI.

## State Flow

User actions update GUI controls. Panels read controls into settings objects or core function arguments. Core modules return structured results. GUI panels render plots/tables/logs and enable save actions.

Hardware control is stricter: `START` creates a frozen run snapshot before opening serial. Worker execution must not read live calibration or function controls after the run starts.

## Restore Flow

`main_frame.py` stores restore state in `app_state.json`:

- `View`: last top-level workspace only.
- `Tab`: workspace plus notebook selections.
- `Parameters`: workspace, tabs, and panel-supported typed values/paths.

Nested notebooks are restored by page names, not recursive order alone.

