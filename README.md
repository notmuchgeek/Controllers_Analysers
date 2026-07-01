# Controllers & Analysers

**English** | [简体中文](README.zh-CN.md)

Controllers & Analysers is our research-group desktop app for experiment control and data analysis. Choose a workspace, load data or enter experiment settings on the left, inspect previews and logs on the right, and save the results you need.

![AFM/KPFM controller screen](assets/images/AFM_KPFM_Controller.png)

Current version: `Controller & Analysers v16.22.260701.0042`

## First-Time Setup

You can use a normal Windows Python installation or Anaconda. Python 3.10 or newer is required.

1. Double-click `create_ca_app_shortcut.bat`.
2. Paste the full path to `python.exe` or an Anaconda folder. If you are unsure, press Enter and the setup will search common locations automatically.
3. The setup checks whether this Python already has everything the app needs. Missing components are installed automatically. Keep the window open; the first setup may take several minutes and may need an internet connection.
4. Wait for `Shortcut created`, then close the setup window.
5. Double-click `ca_app.lnk` to open the app. You may copy this shortcut to your Desktop.

The successful setup is remembered for that Python installation on this PC. Running the BAT file again normally skips installation unless the requirements or Python environment have changed.

## Everyday Use

1. Open `ca_app.lnk`.
2. Choose a workspace from the `View` menu.
3. Load files or enter settings on the left.
4. Check the plots, tables, and log on the right.
5. Save the required output from the current workspace.

Most analysis workspaces follow the same pattern: load data, adjust parameters, inspect the preview, run the analysis, then save. A message in the log usually explains invalid input or a file that could not be read.

### Remembering Your Work

The `Restore` menu controls what the app remembers when it opens next time:

- `View` remembers only the last workspace.
- `Tab` also remembers the selected tabs.
- `Parameters` also remembers supported loaded-file paths, typed values, choices, and checkboxes.

Manual `Save Parameters` and `Load Parameters` buttons create or open a settings file chosen by you. They are separate from automatic Restore. Hardware output state and measured data are never restored automatically.

The optional local usage log records broad actions and timings, not raw data or hardware traces. Use `About -> Usage Logging` to turn it on or off and `About -> Open Usage Log Folder` to find the files.

## Choosing a Workspace

| What you want to do | Workspace |
| --- | --- |
| Run current or light-intensity timing with a Keithley | `View -> AFM/KPFM -> Controller` |
| Analyse AFM/KPFM CPD images, masks, profiles, or HOPG references | `View -> AFM/KPFM -> Analysis` |
| Analyse workfunction, APS, DWF, DOS, or SPV files | `View -> APS` |
| Control the red or green TPC laser diode | `View -> TPC` |
| Correct Raman baselines | `View -> Raman -> Baseline` |
| Batch-preview, correct, and convert Raman files | `View -> Raman -> Converting` |
| Inspect Raman maps and select spectra | `View -> Raman -> Mapping` |
| Analyse peaks in Raman electrochemistry sequences | `View -> Raman -> Insitu EChem` |
| Preview gate/drain electrical measurements | `View -> Raman -> Electrical` |

## AFM/KPFM Workspace

### Controller

The Controller sends current commands to a Keithley source meter and reads voltage during ON stages. In `Current mode`, source values are entered in mA. In `Intensity mode`, target optical intensity is converted to current using the loaded calibration.

Main controls:

- `Global settings`: choose Current/Intensity mode and check COM port, baudrate, voltage compliance, and internal maximum current.
- `Quick Test`: use its separate ON/OFF button for a short fixed output check. It cannot run at the same time as Function control.
- `Recurrent control`: repeat one ON duration and one OFF duration.
- `Step control`: build a sequence from checked ON/OFF rows. This is the default timing mode.
- `Calibration`: load a current/intensity CSV, choose the fit method and range, and inspect the fit statistics.
- `Function control`: replace ON-stage values with a changing `f(x)` profile while keeping the Recurrent or Step ON durations.

Preview tabs:

- `Source profile`: planned current and, where available, optical intensity against time.
- `Function profile`: the requested `f(x)` values before they are placed into ON stages.
- `Intensity calibration`: measured calibration points, fitted curve, and selected fit range.
- `Live voltage`: measured voltage and commanded source current during a run; OFF stages show the software-known zero values.

Before `START`, inspect the source preview and the internal maximum current. `STOP` safely ends the sequence. `Save CSV (Source)` saves only the planned profile; `Save Keithley CSV` saves measured run rows only when you click it.

### Analysis

Analysis loads CPD TIFF or PNG images. TIFF files can contain calibrated values; PNG files use the voltage limits entered by the user. Choose CPD or Energy display, slow-scan direction, illuminated regions, and optional masks.

Preview tabs:

- `CPD Image`: the image, selected illuminated regions, and display scale.
- `Profile`: histograms plus row/time profiles for comparing dark and illuminated regions.
- `Masks`: loaded or generated upper/lower/middle mask regions.
- `HOPG Fit`: Gaussian fitting of an HOPG reference for CPD-to-energy conversion.

![AFM/KPFM analysis](assets/images/AFM_KPFM_Analysis.png)

## APS Workspace

APS combines related photoelectron and surface-potential workflows in one page:

- `Workfunction Analysis`: load sample DWF files plus reference APS and DWF data, choose statistic regions, and calculate workfunction results.
- `APS Analysis`: load APS files, set the HOMO fitting range, and calculate APS/HOMO results.
- `DOS parameters`: control smoothing and the DOS result generated from APS data.
- `SPV Processing`: load SPV files, choose timing/background settings, and calculate normalised SPV results.

Preview tabs:

- `WF Preview / Results`: sample/reference DWF and reference APS checks, then workfunction results.
- `APS Preview / Results`: APS curves and their selected fitting regions.
- `DOS`: smoothed density-of-states results.
- `SPV Preview / Results`: raw and processed surface-photovoltage results.

Use the matching save button to export each analysis as CSV files.

![APS/SPV analysis](assets/images/APS_Analysis_SPV.png)

## TPC Workspace

TPC controls a red or green laser diode through a Keithley current source.

1. Select the correct laser colour.
2. Check the COM port and baudrate.
3. Enter the requested current and confirm the displayed current limit.
4. Use `ON` only after checking the wiring and optical setup.
5. Use `OFF` before changing connections or leaving the experiment.

The status/log area reports the selected diode, applied current, measured readback, and any communication error.

![TPC controller](assets/images/TPC_controller.png)

## Raman Workspace

### Baseline

Baseline corrects one or many single-/multi-spectrum TXT/WDF files with the same fitting settings.

1. Use `Load txt/wdf` or `Add` to put files in the list. Ctrl/Shift selection, Delete, and drag reordering work like the Converting list.
2. Checked files appear together in the Preview. Checking one of several selected rows applies the same preview state to all selected rows.
3. For multi-spectrum files, enter one shared `Selected columns` value and click `Update`; the same 1-based columns are previewed from every checked multi-spectrum file. Fitting still processes every spectrum.
4. Choose `asPLS`, `drPLS`, or `Polynomial/backcor`, then use Auto mode or click `Fit` in Manual mode. Fit processes every loaded file with one settings snapshot.
5. With exactly one loaded file, `Load fitted`, Output filename, and `Save` keep their previous behavior.
6. `Save all` chooses one folder and writes every successfully fitted item as `<source>_Copy.txt`, preserving its original logical TXT layout.

The `Preview` tab overlays checked raw/baseline curves above and corrected curves below.

![Raman baseline](assets/images/Raman_Baseline.png)

### Converting

Converting is for working with several Raman WDF/TXT files together.

- Add files to the list, Ctrl/Shift-select rows, delete entries, or drag them into a new order.
- Checked rows are included in the preview; selection controls actions such as Delete, `Load to Baseline`, and `Correct Baseline`.
- Set Preview Min/Max to limit the displayed Raman-shift range.
- `Load to Baseline` sends one selected entry to the Baseline tab for checking the fit.
- `Send params to Converting` on the Baseline tab returns the chosen fit settings.
- `Correct Baseline` adds new `_baselined` entries and leaves the originals unchanged.
- `Export All` writes every list entry as a separate Origin-friendly TXT file.

### Mapping

Mapping loads WiRE mapping WDF files or stacked `#X/#Y/#Wave/#Intensity` TXT data.

Controls let you set preview spacing, show a Raw-data legend, include averaged/normalised columns in the combined export, choose a Raman range, and select 1-based spectra such as `1,2-4,5`.

Preview tabs:

- `Avg./Norm.`: the unstacked wide data table with averaged and normalised intensity.
- `Raw data`: every N-th raw spectrum.
- `Location`: mapping positions and embedded WDF image/location information when available.
- `Selected`: only the spectra listed in the selection field.

`Save` writes a combined Origin-friendly TXT. `Save one for each` writes one two-column TXT per raw spectrum. `Save selected` writes a sequence-format TXT, and `Load to Insitu Echem` transfers the selected spectra directly without creating a hidden file.

![Raman mapping](assets/images/Raman_mapping.png)

### Insitu EChem

Insitu EChem analyses peaks through a Raman sequence. It accepts time-coded or sequence-coded TXT, WDF sequences, and spectra transferred from Mapping.

- Choose Sequence or Time for the x-axis. Sequence-labelled and Mapping data stay in Sequence mode.
- Add peak/window rows and choose the peak used for normalisation.
- Set how often spectra appear in the peak-window and result previews.
- Use the four legend checkboxes independently for spectra, peak positions, peak intensities, and peak ratios.
- Select `inverse` when inverse normalised ratios are required.

Preview tabs:

- `Peak windows`: every N-th spectrum with all extraction windows highlighted.
- `Analysis`: spectra, peak positions, peak intensities, and normalised ratios in a four-panel result.

The four save buttons each produce the corresponding plot image and CSV data.

![Raman Insitu EChem analysis](assets/images/Raman_Insitu-Echem_Analysis.png)

### Electrical

Electrical previews CSV files containing exact Gate/Drain time, voltage, and current columns.

Preview tabs:

- `Raw data`: Gate voltage, Drain voltage, Gate current, and Drain current. One shared seconds control selects the displayed duration.
- `V_Gate/V_Drain`: Gate and Drain voltages together with separate preview-duration controls and a summary table.
- `V_Gate/I_Drain`: Drain current in mA with Gate-voltage pulse periods shown as red spans.

The summary classifies Gate and Drain voltage as constant, pulsed, changing, or missing and reports pulse count and timing. Missing required columns are reported explicitly rather than guessed.

## Hardware Safety

Do not press an output `ON` or `START` button until the hardware is connected correctly and the requested settings are known to be safe.

For AFM/KPFM, verify:

- COM port and baudrate
- voltage compliance
- internal maximum current
- Current or Intensity mode
- calibration and source preview when using intensity

For TPC, verify the selected diode, current, current limit, COM port, and baudrate. Always use `STOP` or `OFF` before disconnecting equipment. Ask the maintainer before performing an unfamiliar hardware test.

## Troubleshooting

- `Python could not be found`: run the BAT file again and paste the full `python.exe` path or the folder containing it.
- `Python 3.10 or newer is required`: select a newer Python or Anaconda installation.
- Requirements could not be installed: check the internet connection, keep the project and `wheelhouse` folder together, and rerun the BAT file.
- The shortcut opens and closes immediately: rerun the BAT file and read the setup messages, then contact the maintainer.
- A data file does not load: check the expected format and exact column names, then read the workspace log.
- Hardware does not respond: press `STOP`/`OFF`, check the COM port and cabling, and ask the maintainer before changing safety limits.
