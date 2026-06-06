# Agent Instructions for Controllers & Analysers

This file is the source of truth for coding agents working inside the `ca_app` project.

## 1. Active Project

The active runnable application is the packaged v14 application:

```text
ca_app/
  run_ca_app.py
  src/ca_app/
```

Run from this folder:

```cmd
python run_ca_app.py
```

The top-level GUI shell is:

```text
src/ca_app/gui/main_frame.py
```

The AFM/KPFM controller behavior was migrated from the v10 reconstruction and should remain hardware-compatible unless explicitly changed.

## 2. Project Purpose

Controllers & Analysers is a wxPython GUI for experiment control and analysis workflows. It currently includes AFM/KPFM Keithley control, AFM/KPFM CPD image analysis, APS/DWF/SPV analysis, TPC laser-diode control, Raman baseline correction, Raman Mapping, Raman Insitu EChem sequence analysis, and reserved workspaces for future tools.

The AFM/KPFM controller sources current through a Keithley source meter over RS-232 serial communication. It applies ON/OFF timing patterns, reads measured voltage live, and can control by target optical intensity using a current-intensity calibration CSV.

The Keithley always receives current commands. In intensity mode, target intensity is converted to required current before sending commands to the Keithley.

When `START` is clicked, AFM/KPFM sequence execution uses a frozen run snapshot. Calibration method/range changes, function edits, and preview updates made during a run are GUI-only and must not affect the active Keithley output current until the next `START`.

Core Keithley mode:

```text
Source: current
Measure: voltage
Voltage limit: voltage compliance
Communication: serial COM3, 38400 baud by default; hardware tabs allow 9600, 19200, 38400, or 57600
```

Core SCPI commands:

```text
*RST
:SOUR:FUNC CURR
:SOUR:CURR:MODE FIXED
:SENS:FUNC "VOLT"
:FORM:ELEM VOLT,CURR
:SENS:VOLT:PROT <compliance_v>
:SENS:VOLT:NPLC 0.1
:SOUR:CURR:LEV <current_A>
:OUTP ON
:OUTP OFF
:READ?
```

`:READ?` is used only during ON-stage measurement. OFF stages must not query the Keithley because output-off measurement requests can trigger Keithley error 803.

## 3. Environment

Known working environment:

```text
Windows
Python 3.13.x
wxPython 4.2.x
pyserial 3.5
numpy
matplotlib
scipy
```

Install for development:

```cmd
pip install -e .
```

Run tests:

```cmd
python -m unittest discover -s tests
```

Compile check:

```cmd
python -m compileall src tests
```

## 4. Structure

```text
src/ca_app/app.py
  Application entrypoint.

src/ca_app/constants.py
  Import-safe defaults shared by modules.

src/ca_app/gui/main_frame.py
  Main window shell, View menu, Restore menu, workspace switching,
  app-state persistence, and About dialogs.

src/ca_app/gui/panels/
  Independent workspace panels.

src/ca_app/gui/panels/afm_kpfm_panel.py
  AFM/KPFM notebook containing Controller and Analysis tabs.

src/ca_app/gui/panels/afm_controller_panel.py
  Keithley controller UI and runtime behavior.

src/ca_app/gui/panels/afm_analysis_panel.py
  AFM/KPFM CPD TIFF/PNG image analysis, illuminated regions, masks, row/time
  profiles, HOPG reference fitting, and parameter restore.

src/ca_app/gui/panels/aps_panel.py
  APS, DWF, workfunction, DOS, and SPV analysis GUI.

src/ca_app/gui/panels/raman_panel.py
  Raman notebook with Baseline, Mapping, Insitu EChem, and reserved Electrical tabs.

src/ca_app/core/raman_mapping.py
  Raman WiRE WDF/TXT loading, mapping unstacking, Origin TXT export,
  selected-sequence TXT export, and WDF image/location metadata helpers.

src/ca_app/core/raman_baseline.py
  Raman text import, asPLS, drPLS, and Polynomial/backcor substrate-baseline
  fitting, WiRE overlay interpolation, and corrected text export.

src/ca_app/core/raman_insitu_echem.py
  Raman sequence import, peak-window extraction, peak position/intensity
  summaries, normalized intensity ratios, and CSV export for Insitu EChem.

src/ca_app/gui/panels/tpc_panel.py
  TPC laser-diode control GUI.

src/ca_app/core/intensity_profile_tools.py
  Current core implementation for function expressions, calibration CSV loading,
  empirical fitting, stats, and intensity-current inversion.

src/ca_app/core/calibration_models.py
  Stable public calibration-model import surface.

src/ca_app/core/function_profiles.py
  Stable public function-expression import surface.

src/ca_app/hardware/keithley_serial.py
  Serial settings and SCPI command primitives for future runtime extraction.

src/ca_app/runtime/
  Planned extraction area for sequence/quick-test worker services.

src/ca_app/io/
  File import/export boundaries.

src/ca_app/resources/
  Bundled calibration CSVs.

tests/
  Non-hardware tests.
```

## 5. Refactor Rule

The v14 application separates the main shell from independent workspace panels. The AFM/KPFM controller panel still intentionally keeps the tested Keithley runtime behavior together to avoid changing hardware semantics during naming and structure cleanup.

When refactoring further:

- Move non-GUI logic into `core/`, `runtime/`, `hardware/`, or `io/`.
- Keep behavior unchanged unless the user asks for a feature change.
- Add or update tests before changing shared core behavior.
- Do not alter Keithley command timing or STOP behavior without explicit review.

## 6. Important Defaults

```python
DEFAULT_COM_PORT = "COM3"
DEFAULT_BAUDRATE = 38400
DEFAULT_COMPLIANCE_V = 5.0
DEFAULT_INTERNAL_MAX_CURRENT_MA = 110.0
DEFAULT_CALIBRATION_FILENAME = "default_intensity_calibration.csv"
DEFAULT_CALIBRATION_FIT_X_MIN_MA = "67"
DEFAULT_CALIBRATION_FIT_X_MAX_MA = "94"
DEFAULT_FUNCTION_EXPR = "x*m+b"
DEFAULT_FUNCTION_X_MIN = "0"
DEFAULT_FUNCTION_X_MAX = "180"
DEFAULT_FUNCTION_Y_MIN = "0.1"
DEFAULT_FUNCTION_Y_MAX = "4.99"
SERIAL_TIMEOUT_S = 5.0
QUICK_TEST_PREVIEW_TIME_S = 10.0
FUNCTION_PROFILE_POINTS = 300
FUNCTION_EXEC_MIN_INTERVAL_S = 0.05
```

Preserve these unless the user explicitly changes them.

## 7. GUI Requirements

Preserve current GUI behavior:

- Fixed left/right layout, not a resizable splitter.
- COM port defaults to editable `COM3` in each hardware controller tab.
- Baudrate defaults to `38400` and is selectable from `9600`, `19200`, `38400`, and `57600` in each hardware controller tab.
- Voltage compliance remains editable.
- Internal max current remains visible and editable.
- Measured voltage is visible.
- Measured current is not shown in the GUI.
- Source mode uses radio buttons: Current mode and Intensity mode.
- Quick Test is standalone with its own ON/OFF button.
- Quick Test and Function control are mutually exclusive.
- Function control is an overlay on Recurrent or Step ON stages.
- When Function control is enabled, Recurrent and Step ON value fields are disabled/greyed because `f(x)` supplies the ON-stage current or intensity.
- Function-enabled sequence building must not require or parse the disabled ON value fields; ON durations still define where `f(x)` is injected.
- Recurrent control and Step control are the base timing patterns.
- Step control is default.
- Preview updates automatically.
- No Update Preview button.
- Enabling Function control automatically selects the Function profile preview tab.
- Enabling Quick Test automatically selects the Source profile preview tab.
- Successfully loading a calibration CSV automatically selects the Intensity calibration preview tab.
- When a calibration model is loaded, the Source profile preview shows source current on the left y-axis and optical intensity on the right y-axis where applicable.
- The Calibration tab shows compact fit statistics as six static labels in two rows, not a multiline text box.
- The Intensity calibration / Function control section should remain compact; the Function control tab is intentionally arranged in dense rows so the notebook does not leave large blank space.
- The Live voltage preview shows measured voltage on the left axis and source current on the right axis. It starts at 0 V / 0 mA when `START` is pressed and continues plotting 0 V / 0 mA software-known points during OFF stages.
- The bottom controller buttons use two rows: `Save CSV (Source)`, `Save Parameters`, `Load Parameters`; then `Save Keithley CSV`, `START`, `STOP`.

## 8. Safety Logic

All source currents must be checked against the GUI value `Internal max current / mA`.

This applies to:

- Quick Test current.
- Current-mode recurrent ON current.
- Current-mode step ON currents.
- Current-mode function profile.
- Intensity-mode converted current.
- Intensity-mode converted function profile.

If any required current exceeds the internal max current, the program must not turn the Keithley output on. Warnings should tell the user to increase `Internal max current / mA` only if safe.

Sequence runs must isolate runtime state from GUI edits:

- `START` builds a frozen run snapshot before opening the serial port.
- The snapshot contains global serial/compliance settings, source mode, control pattern, calibration metadata, frozen calibration model, and fully built sequence steps.
- Fixed ON steps store the exact source current in mA at `START`.
- Function ON steps store frozen `x`, target, and source-current profiles at `START`.
- Worker-thread execution must not read `self.calibration_model`, calibration controls, or function text fields after `START`.
- During a run, users may still change calibration method/range and function controls for preview/editing only. Those edits apply only to the next run.

OFF stages must not send `:READ?`, `:INIT`, or `:FETCH?`. OFF stages send `:OUTP OFF`, log a local run-data row with source current `0 mA` and blank measured voltage/current, and wait while plotting software-known 0 V / 0 mA live points.

Every sequence cleanup path must send a safety output-off command before closing serial where possible: set source current to 0, then send `:OUTP OFF`. This applies to normal finish, user stop, and exceptions.

Hardware checks should only be done with the user's explicit confirmation and safe current/compliance settings.

## 9. Calibration

Default calibration CSV:

```text
src/ca_app/resources/default_intensity_calibration.csv
```

It auto-loads at startup when present.

Calibration CSV format:

```text
Current_mA,Intensity_mW
```

The loader also accepts two numeric columns, where the first numeric column is current in mA and the second is intensity in mW.

Default fit range:

```text
67 to 94 mA
```

Fit methods:

```text
Empirical power-exp
Two threshold power
Two stage softplus slope
Generalized exponential power
Polynomial degree 3
Interpolation
Linear
Quadratic
Cubic
```

Default method:

```text
Empirical power-exp
```

Empirical methods are smooth calibration fits for interpolation within measured data. They are not physical laser diode equations and should not be used for extrapolation far outside 67 to 94 mA.

The Status / log box reports empirical fit progress: fit range, trial start/completion, periodic evaluation-count/RMSE updates during long solves, and final selected parameters.

Changing calibration method or fit range while a sequence is running may update visible calibration statistics and preview plots, but must not change the active run snapshot or commanded Keithley current.

## 10. Function Control

Default:

```text
f(x) = x*m+b
X min = 0
X max = 180
Y min = 0.1
Y max = 4.99
```

The `Fit it` button on the `f(x)` row solves parameterized templates. If the expression contains names other than `x`, allowed constants/functions, or `np`, those names are treated as fit parameters.

Examples:

```text
x*m+b
a*x^2+b*x+c
```

When fit parameters are present, automatic endpoint calculation is disabled. The user must fill all four endpoint fields and press `Fit it`.

After fitting, the expression is replaced with a numeric expression so preview, CSV export, validation, and execution use the safe evaluator.

If the template cannot fit both endpoint points, show an error. For underdetermined templates such as `a*x^2+b*x+c`, the app uses a deterministic minimum-norm solution and logs that choice.

## 11. Sequence Model

Central architecture:

```text
User input
-> Source mode decides whether value is current or intensity
-> START freezes source mode, calibration, function settings, and sequence steps
-> Intensity mode converts mW to mA using the frozen calibration snapshot
-> Recurrent or Step builds ON/OFF timing
-> Function control optionally replaces each ON stage value with a frozen f(x) current profile
-> Internal max current validates all required current values
-> Keithley only receives current commands
-> GUI reads measured voltage live during ON periods and plots software-known 0 V / 0 mA during OFF periods
```

OFF step:

```text
Send :OUTP OFF, append 0 V / 0 mA live points, log blank measured values, and wait
```

Fixed ON step:

```text
Set source current, send :OUTP ON, read voltage live
```

Function ON step:

```text
progress = elapsed_ON_time / total_ON_time
interpolate source current from the frozen f(x) current profile
send required current -> Keithley
```

In Function control, the Recurrent/Step ON value field is intentionally ignored. The checked ON rows and their ON durations still define the function-controlled ON stages.

## 12. Save/Load

Save Parameters and Load Parameters use JSON.

`Restore` controls automatic `app_state.json` persistence:

- `View` remembers only the last opened top-level workspace.
- `Tab` remembers the workspace and selected notebook tabs.
- `Parameters` remembers workspace, tabs, loaded file paths, typed values, choices, and checkboxes where panel app-state adapters support it.

Automatic app-state restore is separate from manual Save Parameters / Load Parameters files and must not influence those explicit user-selected files.

Important restore-maintenance rule:

- Whenever any new workspace tab, nested preview notebook, or additional function panel is added, double-check `app_state.json` restore behavior.
- Tab restore must match notebooks by page names, not just recursive notebook order, because adding a nested notebook can otherwise restore saved selections onto the wrong notebook.
- Parameter restore must preserve user-typed values after any automatic file reload. Do not reload a file after applying saved fields if the reload resets those fields.

`Save CSV (Source)` exports the planned source profile only.

`Save Keithley CSV` saves measured run data rows only when the user clicks the button. Sequence completion must not automatically create `keithley_run_data_*.csv` files.

Do not save or restore active hardware state in manual parameter files or automatic app-state restore:

- measured voltage
- runtime/status text
- log text
- whether output is currently ON
- live voltage data
- run data rows

Loading parameters must never turn output ON.

## 13. Raman Baseline

The active Raman workspace is available from:

```text
View -> Raman -> Baseline
```

The Raman workspace uses the same fixed left/right layout style as APS:

- Left side: file loading, method selection, parameters, output filename, Fit, and Save.
- Right side: one `Preview` tab containing two stacked figures.
- Bottom-right: Raman log.

Preview layout:

```text
Preview
  top: raw Raman spectrum with estimated baseline
  bottom: baseline-corrected Raman spectrum, with optional WiRE software analysed result overlay
```

Raman text files use the same two-column numeric format as the example files:

```text
#Wave    #Intensity
1820.535156    3780.142822
...
```

The loader accepts at least two numeric columns and uses the first two numeric columns as Raman shift and intensity.

Fitting methods:

```text
asPLS
drPLS
Polynomial/backcor
```

User-visible method names are case-sensitive in the GUI. Use `asPLS` and `drPLS`, not `ASPLS` or `DRPLS`.

`asPLS` parameters:

```text
lambda values: 1e6, 1.5e6, 2e6, 2.5e6, 3e6, 3.5e6, 4e6, 1e7, 5e7
k values: 1.0, 1.5, 2.0
```

`drPLS` parameters:

```text
lambda values: 1e4, 3e4, 1e5, 1.5e5, 2e5, 2.5e5, 3e5, 3.5e5, 4e5, 1e6, 1.5e6, 2e6
eta values: 0.00, 0.05, 0.1, 0.15, 0.2, 0.25
```

`Polynomial/backcor` parameters:

```text
Orders: 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
Thresholds: 0.001, 0.002, 0.003, 0.004, 0.005, 0.0075, 0.010, 0.0125, 0.015, 0.0175, 0.020, 0.0225, 0.024, 0.03
Below-baseline fraction: 0.25
```

`Polynomial/backcor` uses internal `cost_function = "atq"`. This setting must not be exposed to the user unless explicitly requested.

Auto/manual behavior:

- Auto mode evaluates the visible candidate lists.
- Manual mode requires one value per parameter and only refits when the user clicks `Fit`.
- Loading a raw Raman file in Auto mode runs fitting automatically.
- Changing the fitting method in Auto mode runs fitting automatically when a raw file is loaded.

Output behavior:

- Output filename defaults to the raw file stem plus `_Copy.txt`.
- Save writes only the baseline-corrected spectrum in two-column text format.
- Optional WiRE software analysed results can be loaded from a `_Copy.txt` file and overlaid on the corrected-spectrum figure only.

## 14. Raman Mapping

The active Raman Mapping workspace is available from:

```text
View -> Raman -> Mapping
```

Mapping follows the same fixed left/right layout style:

- Left side: Parameters, Load file, Averaging, Mapping & Selecting, and Save.
- Right side: preview notebook with `Avg./Norm.`, `Raw data`, `Location`, and `Selected`.
- Bottom-right: Mapping log.

Input support:

- WiRE WDF mapping files such as `map_WiRE.wdf`.
- WiRE stacked TXT mapping files with columns `#X`, `#Y`, `#Wave`, `#Intensity`, such as `map_format.txt`.

Mapping behavior:

- Load WDF/TXT and unstack spectra into a wide table where column 1 is wavenumber, column 2 onward are individual spectra, then averaged intensity, then normalised intensity.
- `Save` in Averaging exports Origin-friendly TXT with long-name and unit rows.
- `Every N for preview` and `Legend` live in the Load file section. `Every N = 1` plots all spectra; `Every N > 1` plots every N-th spectrum in `Raw data`.
- The Mapping `Legend` checkbox affects only the `Raw data` tab and is enabled only when `Every N > 1`.
- `Mapping & Selecting` uses Raman range min/max fields and a 1-based selected-column list with inclusive ranges such as `1,2-4,5` or `45-60`.
- `Save selected` exports `#Sequence`, `#Wave`, `#Intensity` TXT compatible with Insitu EChem.
- `Load to Insitu Echem` transfers the selected spectra in memory to the Insitu EChem tab and does not create an automatic hidden TXT file.
- Mapping selected spectra must preserve their original selected-column/sequence numbers in both saved TXT and Insitu EChem transfer. Do not renumber selected columns from 1 during export, transfer, plotting, or analysis.
- `Location` shows only mapping locations and WDF embedded image/location metadata where available; sequence WDF files may legitimately have no image/location metadata.
- `Selected` shows only selected spectra. Its legend labels are short spectrum/sequence numbers and must not include X/Y coordinates.

## 15. Raman Insitu EChem

The active Insitu EChem workspace is available from:

```text
View -> Raman -> Insitu EChem
```

The Insitu EChem workspace uses the same fixed left/right layout style:

- Left side: file loading, x-axis mode, peak windows, normalized peak, Update, and save buttons.
- Right side: preview notebook.
- Bottom-right: Insitu EChem log.

Input files use Raman sequence text format:

```text
#Time    #Wave    #Intensity
0.000000    2063.746094    3895.066162
...
```

Insitu EChem also accepts:

```text
#Sequence    #Wave    #Intensity
1.000000    1728.768555    64.341232
...
```

and WDF sequence files such as `seq_raw.wdf`.

When the first column is `#Sequence`, or when data is loaded from WDF/Mapping in-memory transfer, the Time x-axis option must be disabled/greyed and Sequence mode forced. `#Sequence` values and Mapping selected-column numbers are real sequence labels and must be preserved, not remapped to 1..N.

The loader maps sorted raw `#Time` sequence codes to `sequence_index = 1..N`. Time mode uses:

```text
time_s = Time Offset + sequence_index * Time per sequence
```

Defaults:

```text
Time Offset = 5.00 s
Time per sequence = 2.09 s
Window preview every N = 20
Result spectra every N = 10
Peak windows = 1371 +/- 5, 1423 +/- 6, 1516 +/- 5, 1606 +/- 5
Normalized peak = 1423 when present, otherwise the first peak
```

X-axis section:

- Default mode is `Sequence`.
- `Time` mode shows `Time Offset` and `Time per sequence`.
- Plot labels, titles, and legends must update for sequence vs time mode.

Window section:

- Each row contains a peak position and window size.
- Users can add peak/window rows and delete the last peak/window row. The final remaining row cannot be deleted.
- Valid peak/window edits auto-update the preview; the `Update` button forces an immediate refresh when delayed text updates do not fire cleanly.
- For each peak window, the analysis extracts the local maximum intensity and its Raman shift for every sequence.

Right preview tabs:

```text
Peak windows
  Every N-th spectrum with all peak windows highlighted.

Analysis
  2x2 layout:
    top-left: every N-th spectrum with red-to-green sequence/time gradient
    top-right: peak positions vs selected x-axis
    bottom-left: peak intensities vs selected x-axis
    bottom-right: intensity ratios normalized to the selected peak
```

The `Peak windows` preview uses distinct colors for each peak-window span. The `Legend` checkbox beside `Update` affects only the top-left every-N spectrum plot in the `Analysis` tab and must not change legends on other figures.

Save buttons:

- `Save spectra plot/data`
- `Save peak positions plot/data`
- `Save peak intensities plot/data`
- `Save ratios plot/data`

Each button saves one PNG and one CSV for the corresponding result plot.

The Raman notebook also has a fourth `Electrical` tab. It is intentionally blank/reserved unless explicitly requested.

## 16. Testing Checklist

After code edits, run:

```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

Manual GUI checks without hardware:

1. Program opens from `python run_ca_app.py`.
2. COM port defaults to `COM3` and remains editable.
3. Baudrate defaults to `38400` and can be changed to `9600`, `19200`, or `57600`.
4. Voltage compliance field is editable.
5. Internal max current defaults to 110.0 and is editable.
6. Source mode radio buttons are exclusive.
7. Default calibration auto-loads from package resources.
8. Default fit method is `Empirical power-exp`.
9. Default calibration fit range is 67 to 94.
10. Function tab defaults to `x*m+b`, 0, 180, 0.1, 4.99.
11. `Fit it` solves `m` and `b`.
12. Empirical fit progress appears in Status / log.
13. Function preview works after fitting.
14. Step/Recurrent previews work.
15. Save CSV (Source) refuses Quick Test.
16. STOP remains available during sequence execution.
17. Enabling Function control greys Recurrent/Step ON value fields and switches to Function profile preview.
18. Function control works with empty ON value fields as long as ON durations are valid.
19. Enabling Quick Test switches to Source profile preview.
20. Loading a calibration CSV switches to Intensity calibration preview.
21. With calibration loaded, Source profile preview shows current on the left y-axis and intensity on the right y-axis.
22. Calibration fit statistics are shown as six compact static labels in two rows.
23. The Intensity calibration / Function control section has no large blank area below the calibration statistics.
24. Live voltage/current plotting starts immediately at 0 V / 0 mA and continues through OFF stages with 0 V / 0 mA points.
25. OFF stages do not query Keithley measurements while output is off.
26. A normal finish, STOP, or exception sends current 0 and output OFF before serial close.
27. Changing calibration fit method/range during a running sequence does not affect the active run current; changes apply only to preview and the next `START`.
28. Keithley run data is saved only via `Save Keithley CSV`.





