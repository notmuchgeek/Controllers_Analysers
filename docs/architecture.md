# Architecture

Controllers & Analysers separates the top-level application shell from independent experiment/control workspaces.

## Layers

- `gui`: wxPython frame and workspace panels.
- `core`: calibration models, function expressions, validation, and sequence logic.
- `hardware`: Keithley serial settings and SCPI command primitives.
- `runtime`: planned extraction area for worker-thread execution services.
- `io`: CSV/JSON file boundaries.
- `resources`: bundled calibration CSV files.

## Current Boundary

`gui/main_frame.py` owns the main window, View menu, Restore menu, About menu, workspace switching, and app-state persistence. AFM/KPFM, APS, TPC, Raman, and reserved workspaces live in `gui/panels/`.

Current panel boundaries:

- `afm_kpfm_panel.py`: AFM/KPFM notebook with Controller and Analysis tabs.
- `afm_controller_panel.py`: Keithley controller UI and runtime behavior.
- `afm_analysis_panel.py`: AFM/KPFM CPD TIFF/PNG image analysis, illuminated regions, masks, HOPG fitting, and image/profile previews.
- `aps_panel.py`: APS, DWF, workfunction, DOS, and SPV GUI.
- `raman_panel.py`: Raman GUI with Baseline, Mapping, Insitu EChem, and reserved Electrical tabs.
- `tpc_panel.py`: TPC laser-diode control GUI.

The AFM/KPFM controller panel still owns the tested Keithley control behavior. Future extraction should move runtime and serial orchestration into `runtime/` and `hardware/` one behavior at a time.

## GUI State Rules

`app_state.json` supports three restore levels from the top-level `Restore` menu:

- `View`: restore only the last top-level workspace.
- `Tab`: restore the workspace and selected notebook tabs.
- `Parameters`: restore workspace, tabs, loaded file paths, typed values, choices, and checkboxes where supported by panel app-state adapters.

Automatic app-state restore is separate from manual Save/Load Parameters files. It must not restore active hardware output, measured values, logs, run data, or worker-thread state.

Function control is an overlay on top of Recurrent or Step control, not a separate base timing mode. Checked ON rows and ON durations define where `f(x)` runs. The base ON current/intensity value fields are disabled while Function control is enabled and are not parsed by sequence construction.

Preview tab selection follows the active editing task:

- Function control enable selects `Function profile`.
- Quick Test enable selects `Source profile`.
- Successful calibration CSV load selects `Intensity calibration`.

When calibration is available, the Source profile preview can display a dual-axis plot: source current on the left y-axis and intensity on the right y-axis. The Keithley command path remains current-only.

AFM/KPFM sequence execution is isolated from live GUI edits by a START-time run snapshot:

- Fixed ON steps store source current in mA before the worker starts.
- Function ON steps store frozen `x`, target, and current profiles before the worker starts.
- The worker receives the snapshot and must not read calibration widgets, function widgets, or `self.calibration_model` during execution.
- Calibration and function GUI changes during a run are preview/editing state for the next `START`.

OFF stages are local software-timed stages. They send `:OUTP OFF`, do not query Keithley measurements, log blank measured voltage/current values, and keep the live plot updated with 0 V / 0 mA points.

Run data rows remain in memory after execution. `Save Keithley CSV` is the only path that writes measured run data to disk.

## Raman Boundary

Raman baseline algorithms live in `core/raman_baseline.py`; the wx panel owns only file dialogs, parameter controls, preview drawing, logging, and save actions.

The Substrate Baseline preview is a single right-side `Preview` tab with two vertically stacked figures:

- raw Raman spectrum with estimated baseline
- baseline-corrected Raman spectrum with optional WiRE software analysed result overlay

Supported Raman fitting methods are `asPLS`, `drPLS`, and `Polynomial/backcor`. `Polynomial/backcor` exposes Orders, Thresholds, and Below-baseline fraction; its cost function remains fixed internally as `atq`.

Insitu EChem sequence-analysis logic lives in `core/raman_insitu_echem.py`; the wx panel owns file dialogs, compact filename display, dynamic add/delete peak-window rows, x-axis mode controls, forced Update refresh, preview drawing, logging, and save actions.

The Insitu EChem preview has two right-side tabs:

- `Peak windows`: every N-th spectrum with user-defined peak windows highlighted.
- `Analysis`: 2x2 plot layout for gradient spectra, peak positions, peak intensities, and normalized intensity ratios.

Mapping logic lives in `core/raman_mapping.py`; the wx panel owns file dialogs, parameters, preview drawing, logging, and save/transfer actions. Mapping supports WiRE WDF/TXT loading, unstacked Origin-friendly TXT export, raw spectra previews, location/image preview, selected spectra preview, selected-sequence TXT export, and in-memory transfer into Insitu EChem.

Mapping selected columns are 1-based and accept inclusive ranges such as `1,2-4,5` or `45-60`. Selected spectra must preserve their original selected-column/sequence numbers across TXT export, Insitu EChem transfer, plotting, and analysis.

Insitu EChem has two sequence sources with different indexing semantics:

- `#Time` input maps sorted raw time codes to ordinal `sequence_index = 1..N`, then computes calibrated time from that ordinal.
- `#Sequence` input and Mapping/WDF in-memory transfer preserve the provided sequence labels and force Sequence mode with the Time x-axis disabled.

## Safety

All current sourcing remains validated against the GUI internal max current field. The Keithley receives current commands only, including when the source mode is intensity.

Every sequence cleanup path attempts to set source current to 0 and send `:OUTP OFF` before closing the serial connection. This safety OFF applies to normal finish, STOP, and exceptions.

