# Runtime Package

Version: `v16.21.260630.2340`

This package contains runtime support services and is also the planned extraction area for future worker services. The AFM/KPFM controller panel still keeps worker-thread orchestration locally to preserve tested hardware behavior.

Current runtime support:

- `usage_logger.py`: best-effort local JSONL workflow logging for usability and performance review. It records sanitized UI actions, file labels, counts, and durations only. The main frame stores these logs in the software folder's `usage_logs/` directory.

Planned extraction targets:

- `quick_test_runner.py`: Quick Test worker lifecycle.
- `sequence_runner.py`: sequence execution, STOP handling, live reads, and run-data rows.
- `run_snapshot.py`: immutable START-time settings, sequence, calibration, and function-profile state.
- `run_state.py`: shared thread-safe runtime state and live plotting buffers.

Extraction must preserve current GUI/runtime semantics:

- Quick Test is standalone and mutually exclusive with Function control.
- Function control overlays Recurrent or Step ON durations and ignores base ON value fields while enabled.
- Sequence execution sends current commands only, including intensity-mode and function-mode sequences.
- START-time run snapshots isolate the active worker from later GUI calibration/function edits.
- Function-mode execution uses frozen current profiles computed at START.
- OFF stages do not query Keithley measurements and instead emit software-known `0 V / 0 mA` live plot points.
- Sequence cleanup sets source current to `0` and sends `:OUTP OFF` for normal finish, STOP, and exceptions.
- Measured run data is saved only by the explicit `Save Keithley CSV` action.
- Preview tab auto-selection is GUI-only and should stay outside future runtime services.

See:

- `docs/en/developer-guide.md`
- `docs/en/hardware-safety.md`

Do not change Keithley command timing or STOP behavior during extraction without hardware-safe review.




