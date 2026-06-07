# Module Map

Version: `v16.17.260608.0011`

This map describes the project from the top layer to the lower implementation layers.

## Root

```text
run_ca_app.py
```

Starts the wxPython application from a source checkout.

```text
pyproject.toml
```

Defines package metadata, dependencies, and build configuration.

```text
README.md
README.zh-CN.md
AGENTS.md
```

Human and coding-agent entry points.

## Application Package

```text
src/ca_app/app.py
```

Creates and runs the wx app.

```text
src/ca_app/constants.py
```

Import-safe defaults shared by modules.

```text
src/ca_app/__init__.py
```

Package version metadata.

## GUI Shell

```text
src/ca_app/gui/main_frame.py
```

Owns the main frame, workspace navigation, View menu, Restore menu, About menu, app-state persistence, and window title.

## Panels

```text
src/ca_app/gui/panels/afm_kpfm_panel.py
```

Notebook wrapper for AFM/KPFM Controller and Analysis.

```text
src/ca_app/gui/panels/afm_controller_panel.py
```

Keithley controller UI and runtime orchestration.

```text
src/ca_app/gui/panels/afm_analysis_panel.py
```

CPD image analysis and profile workflows.

```text
src/ca_app/gui/panels/aps_panel.py
```

APS, DWF, DOS, SPV, and workfunction analysis.

```text
src/ca_app/gui/panels/raman_panel.py
```

Raman Baseline, Mapping, Insitu EChem, and Electrical workspaces.

```text
src/ca_app/gui/panels/tpc_panel.py
```

TPC laser-diode current control.

## Core

```text
src/ca_app/core/intensity_profile_tools.py
```

Calibration loading, fitting, inversion, function expression handling, profile generation, and related statistics.

```text
src/ca_app/core/calibration_models.py
src/ca_app/core/function_profiles.py
```

Stable import surfaces for calibration and function behavior.

```text
src/ca_app/core/raman_baseline.py
```

Raman TXT import and baseline correction.

```text
src/ca_app/core/raman_mapping.py
```

WDF/TXT mapping import, unstacking, export, selected spectra, and metadata helpers.

```text
src/ca_app/core/raman_insitu_echem.py
```

Sequence import, peak-window extraction, peak position/intensity analysis, ratios, and export helpers.

## Hardware

```text
src/ca_app/hardware/keithley_serial.py
```

Serial settings and SCPI primitives for future runtime extraction.

## Runtime And IO

```text
src/ca_app/runtime/
src/ca_app/io/
```

Reserved extraction areas for worker services and import/export boundaries. Current behavior still lives mostly in panels and core modules.

## Tests

```text
tests/
```

Non-hardware tests. Add tests here for core changes and state-adapter behavior.




