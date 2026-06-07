# Developer Guide

Version: `v16.11.260607.0040`

This guide is for coding agents and human maintainers.

## Edit Strategy

Read the relevant panel and core module before editing. The project contains several workflows that look similar but preserve different scientific labels, file formats, and hardware constraints.

Prefer:

- Existing GUI patterns over new layout styles.
- Core helpers over duplicated parsing logic.
- Small targeted changes over broad refactors.
- Tests for shared core behavior.

Avoid:

- Changing hardware command order without explicit review.
- Parsing disabled GUI fields.
- Renumbering user-visible Raman sequence labels.
- Adding automatic file outputs after a run.
- Saving active hardware state in app-state restore.
- Logging raw data, full user file paths, measured hardware traces, or measured voltage/current values.

## GUI Pattern

Most workspaces use a fixed layout:

- Left: parameters and command buttons.
- Right top: preview notebook.
- Right bottom: compact log/status area.

Do not replace this with a resizable splitter unless the user asks for a broader UX change.

The main frame lazy-loads workspace panels. Code that touches a workspace from `CaAppFrame` should call `show_workspace()` or `ensure_workspace_panel()` before reading `workspace_panels[name]`. When adding a new notebook or parameter adapter, preserve saved state for unbuilt workspaces and bind notebook save events after any lazy page is created.

## Module Boundaries

Use these boundaries when adding code:

- `gui/`: wxPython widgets, event binding, preview drawing, state adapters.
- `core/`: numerical processing, parsing, model fitting, analysis logic.
- `hardware/`: device command primitives.
- `runtime/`: future worker/service extraction.
- `io/`: future explicit import/export boundaries.
- `resources/`: bundled data files.
- `tests/`: non-hardware tests.

## Usage Logging

Use `ca_app.runtime.usage_logger.log_usage_event()` from GUI code when adding a new user workflow, expensive fit, file load/save, or workspace-level action. Keep event metadata small and sanitized:

- OK: workspace name, tab name, method name, duration in ms, row/spectrum/image counts, output kind, file basename and extension.
- Not OK: full file paths, raw spectra/image arrays, measured hardware traces, measured voltages/currents, calibration CSV rows, comments, or exported data contents.

Logging must stay best-effort. Never make a user action fail because a usage log cannot be written.

`sanitize_metadata()` redacts obviously unsafe metadata keys as a last-resort guard. Treat that as protection against mistakes, not permission to pass sensitive values.

## Version Updates

For any code or documentation implementation from a plan, update:

- `src/ca_app/gui/main_frame.py` `APP_VERSION`
- `src/ca_app/__init__.py` `__version__`
- `pyproject.toml` `version`
- Root `README.md`
- Root `README.zh-CN.md`
- Root `AGENTS.md`
- Relevant docs under `docs/en/`

See [Versioning](versioning.md).

## Raman Electrical Notes

The Electrical tab was implemented from `current_voltage_single_file_processor_v2.ipynb`.

It follows the Mapping/Insitu layout and has:

- Electrical file loader.
- Shared raw preview seconds textbox and slider.
- Preview controls for V_Gate and V_Drain first-second windows.
- Raw data preview with four plots.
- V_Gate/V_Drain dual-axis preview.
- Pulse-summary table.
- Bottom log.

Raw preview linewidth is computed from preview seconds. Do not hard-code one linewidth for all windows unless the user asks.

## Review Checklist

Before finalizing changes:

- Run compile and tests.
- Search for stale version strings.
- Search for stale workspace text that describes Electrical as blank or not implemented.
- Confirm English and Chinese docs stay in matching structure.
- Keep accidental generated caches out of the folder if possible.

