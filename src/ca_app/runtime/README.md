# Runtime Package

The AFM/KPFM controller panel still keeps worker-thread orchestration locally to preserve tested hardware behavior in the v13 application.

Planned extraction targets:

- `quick_test_runner.py`: owns Quick Test worker lifecycle.
- `sequence_runner.py`: owns sequence execution, STOP handling, live reads, and run-data rows.
- `run_snapshot.py`: immutable START-time settings, sequence, calibration, and function-profile state.
- `run_state.py`: shared thread-safe runtime state and live plotting buffers.

Extraction should preserve current GUI/runtime semantics:

- Quick Test is standalone and mutually exclusive with Function control.
- Function control overlays Recurrent or Step ON durations and ignores the base ON value fields while enabled.
- Sequence execution sends current commands only, including intensity-mode and function-mode sequences.
- START-time run snapshots isolate the active worker from later GUI calibration/function edits.
- Function-mode execution uses frozen current profiles computed at START.
- OFF stages do not query Keithley measurements and instead emit software-known 0 V / 0 mA live plot points.
- Sequence cleanup sets source current to 0 and sends `:OUTP OFF` for normal finish, STOP, and exceptions.
- Measured run data is saved only by the explicit `Save Keithley CSV` action.
- Preview tab auto-selection is GUI-only and should stay outside future runtime services.

Do not change Keithley command timing or STOP behavior during extraction without hardware-safe review.
