# Architecture

Version: `v16.11.260607.0040`

This file is retained as a compatibility entry point for older links.

Use the current architecture documentation:

- [English architecture](en/architecture.md)
- [Chinese README](../README.zh-CN.md)

The active architecture summary is:

- `run_ca_app.py` starts the application.
- `src/ca_app/gui/main_frame.py` owns the main frame, menus, restore behavior, About dialog, app-state persistence, and workspace switching.
- `src/ca_app/gui/panels/` owns workspace panels.
- `src/ca_app/core/` owns non-GUI analysis and calibration logic.
- `src/ca_app/hardware/` owns hardware command primitives.
- `src/ca_app/runtime/` and `src/ca_app/io/` are planned extraction areas.

Raman Electrical is implemented in the Raman workspace; it is not a reserved blank tab.

