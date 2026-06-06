# Controllers & Analysers

Controllers & Analysers is a wxPython application for experiment control and analysis workflows. It currently includes AFM/KPFM Keithley control, AFM/KPFM CPD image analysis, APS/DWF/SPV analysis, TPC laser-diode control, Raman baseline correction, Raman Mapping, Raman Insitu EChem sequence analysis, and reserved workspaces for future analysis tools.

This v14 build keeps the tested hardware behavior from v10 while adding Raman Mapping, Insitu EChem linkage, AFM/KPFM image analysis, and app-state restore controls.

## Run

From this folder:

```cmd
python run_ca_app.py
```

Or, after editable install:

```cmd
pip install -e .
ca-app
```

## Hardware Defaults

- COM port: `COM3` by default, editable in hardware controller tabs
- Baudrate: `38400` by default, selectable as `9600`, `19200`, `38400`, or `57600`
- Source mode sent to Keithley: current
- Measurement mode: voltage
- Default voltage compliance: `5.0 V`
- Default internal current limit: `110.0 mA`

Check the hardware setup and safe current/compliance limits before enabling output.

## GUI Behavior Notes

- AFM/KPFM `START` locks a run snapshot. Calibration method/range edits and function edits made while a sequence is running update previews only; they do not change the active Keithley output current.
- The `Restore` menu controls what `app_state.json` remembers between launches: `View`, `Tab`, or `Parameters`.
- Restore `Parameters` remembers loaded files, typed values, choices, and checkboxes where a workspace supports automatic app-state restore. It does not restore active hardware output, live measurements, run data, or logs.
- Function control overlays the selected Recurrent or Step ON stages. When it is enabled, ON-stage current/intensity value fields are greyed out because `f(x)` supplies the value during each ON duration.
- ON durations remain meaningful in Function control: they define how long each injected function profile runs.
- Enabling Function control switches the right preview notebook to `Function profile`.
- Enabling Quick Test switches the right preview notebook to `Source profile`.
- Loading a calibration CSV switches the right preview notebook to `Intensity calibration` after the file loads successfully.
- When a calibration model is loaded, `Source profile` shows source current on the left y-axis and optical intensity on the right y-axis where applicable.
- The Calibration tab uses compact fit-statistic labels instead of a multiline statistics box.
- The Live voltage plot starts at 0 V / 0 mA on `START`, uses real Keithley voltage reads during ON periods, and plots software-known 0 V / 0 mA points during OFF periods without querying the Keithley.
- `Save CSV (Source)` exports the planned source profile. `Save Keithley CSV` saves measured run data only when clicked; run completion does not automatically create `keithley_run_data_*.csv`.
- `View -> Raman` includes `Baseline`, `Mapping`, `Insitu EChem`, and a reserved blank `Electrical` tab.
- Substrate Baseline supports asPLS, drPLS, and Polynomial/backcor Raman baseline correction.
- Raman Substrate Baseline uses a single right-side `Preview` tab with two stacked figures: raw spectrum plus estimated baseline on top, and corrected spectrum plus optional WiRE software analysed overlay below.
- Raman Auto mode evaluates visible candidate lists. Manual mode accepts one value per parameter and refits only when `Fit` is clicked.
- Raman output defaults to `_Copy.txt` and saves the corrected two-column Raman spectrum.
- Raman Mapping loads WiRE WDF/TXT map files, unstacks spectra, saves Origin-friendly TXT, plots raw/location/selected spectra, and transfers selected spectra to Insitu EChem.
- Raman Insitu EChem loads sequence files with `#Time`, `#Wave`, and `#Intensity`, sequence files with `#Sequence`, `#Wave`, and `#Intensity`, and WDF sequence files. It extracts local peak maxima in user-defined windows and plots peak positions, peak intensities, and normalized intensity ratios against sequence or calibrated time.

## AFM/KPFM Analysis

The AFM/KPFM Analysis tab loads CPD images from TIFF or PNG files. TIFF loading attempts to find raw image-sized metadata/tag arrays automatically; PNG loading uses the user-entered voltage min/max to rescale pixel values.

Main features:

- CPD or Energy display, with HOPG reference peak fitting for Energy mode.
- Slow scan direction, row/time x-axis, illuminated-region marking, and dark/light histogram comparison.
- One-mask and two-mask workflows, including inverse/middle mask generation.
- Robust preview color scaling to reduce outlier-dominated colorbars.
- Selectable image colormaps in `Uniform`, `Sequential`, `Diverging`, and `Misc` groups.
- Save/load analysis parameters independent of app-state restore.

## Raman Baseline Methods

Raman files are read as two numeric columns: Raman shift and intensity. Additional numeric columns are ignored by the current GUI workflow.

Available methods:

- `asPLS`: parameters are `lambda` and `k`.
- `drPLS`: parameters are `lambda` and `eta`.
- `Polynomial/backcor`: parameters are `Orders`, `Thresholds`, and `Below-baseline fraction`; internal cost function is fixed as `atq`.

The optional WiRE software analysed result uses the same two-column text format and is only shown as an overlay on the corrected-spectrum preview.

## Raman Mapping

Mapping uses a left parameter panel and four right preview tabs:

- `Avg./Norm.`: raw unstacked table plus averaged/normalised intensity preview.
- `Raw data`: every N-th raw spectrum preview, with an optional legend when not plotting all spectra.
- `Location`: mapping locations and WDF embedded image metadata when available.
- `Selected`: selected spectra only.

The selected-column field is 1-based and accepts individual columns and inclusive ranges such as `1,2-4,5` or `45-60`. `Save selected` and `Load to Insitu Echem` must preserve the original selected-column sequence numbers; selecting columns `45-60` produces sequences `45..60`, not `1..16`.

## Raman Insitu EChem

Insitu EChem uses a left parameter panel and two right preview tabs. The loaded filename is shown in a compact read-only field with the full path in the tooltip:

- `Peak windows`: every N-th Raman spectrum with all peak windows highlighted.
- `Analysis`: four plots in one tab: gradient spectra, peak positions, peak intensities, and normalized intensity ratios.

Defaults:

- X-axis mode: `Sequence`
- Time calibration: `Time Offset = 5.00 s`, `Time per sequence = 2.09 s`
- Peak windows: `1371 +/- 5`, `1423 +/- 6`, `1516 +/- 5`, `1606 +/- 5`
- Normalized peak: `1423` when available

When input uses `#Sequence`, or when data is loaded from Mapping/WDF sequence transfer, Sequence mode is forced and the Time x-axis option is disabled. `#Sequence` values are real sequence labels and are not remapped to `1..N`.

Peak-window rows can be added or deleted, and the `Update` button forces a preview refresh after edits. The save buttons each write one PNG and one matching CSV:

- spectra plot/data
- peak positions plot/data
- peak intensities plot/data
- ratios plot/data

## Project Layout

```text
run_ca_app.py
  Source-checkout launcher for the application.

src/ca_app/app.py
  Application entrypoint used by the console script.

src/ca_app/gui/main_frame.py
  Top-level frame, View menu, Restore menu, About menu, workspace switching, and app-state persistence.

src/ca_app/gui/panels/
  Independent workspace panels for AFM/KPFM, APS, TPC, Raman, and future tools.

src/ca_app/gui/panels/afm_kpfm_panel.py
  AFM/KPFM notebook containing Controller and Analysis tabs.

src/ca_app/gui/panels/afm_controller_panel.py
  Keithley controller UI and runtime behavior.

src/ca_app/gui/panels/afm_analysis_panel.py
  AFM/KPFM CPD TIFF/PNG image analysis, masks, illuminated regions, and HOPG fitting.

src/ca_app/gui/panels/aps_panel.py
  APS, DWF, workfunction, DOS, and SPV analysis workspace.

src/ca_app/gui/panels/raman_panel.py
  Raman notebook with Baseline, Mapping, Insitu EChem, and reserved Electrical tabs.

src/ca_app/core/intensity_profile_tools.py
  Function expression evaluation, calibration CSV loading, empirical fitting, and intensity-current inversion.

src/ca_app/core/aps_analysis.py
  APS, DWF, workfunction, DOS, and SPV analysis logic.

src/ca_app/core/raman_baseline.py
  Raman text import, asPLS, drPLS, and Polynomial/backcor baseline fitting, WiRE overlay interpolation, and corrected text export.

src/ca_app/core/raman_mapping.py
  Raman WiRE WDF/TXT loading, mapping unstacking, Origin TXT export, selected-sequence TXT export, and WDF image/location metadata helpers.

src/ca_app/core/raman_insitu_echem.py
  Raman sequence import, Mapping/WDF sequence conversion, peak-window extraction, peak summaries, normalized intensity ratios, and CSV export.

src/ca_app/resources/
  Default and template calibration CSV files.

tests/
  Non-hardware tests for analysis, calibration, and function-profile logic.
```



