# Controllers & Analysers

**English** | [简体中文](README.zh-CN.md)

Controllers & Analysers is a desktop research application for running laboratory control workflows and analysing experimental data in one place. It brings together Keithley-based AFM/KPFM light-bias control, CPD image analysis, APS/DWF/SPV analysis, TPC laser-diode control, Raman baseline correction, Raman mapping, and in situ electrochemical Raman sequence analysis.

The project started from a practical lab problem: experimental work often moves between instrument control panels, spreadsheets, plotting scripts, image tools, and manual file conversions. Controllers & Analysers turns those repeated steps into a single wxPython GUI with live previews, saved parameters, safer hardware defaults, and export formats designed for downstream scientific analysis.

This v14 package keeps the tested AFM/KPFM Keithley control behavior from the earlier v10 reconstruction while extending the application into a broader analysis workspace.

## What It Does

At a high level, the software helps with three connected tasks:

1. **Control the experiment**  
   Build AFM/KPFM source-current or optical-intensity timing sequences, preview the planned output, run a Keithley source meter over serial, and monitor live voltage.

2. **Analyse the data**  
   Work with CPD images, APS/DWF/SPV data, Raman spectra, Raman maps, and in situ electrochemical Raman sequences using dedicated GUI workspaces.

3. **Keep workflows reproducible**  
   Save parameters, restore workspace state, export CSV/TXT/PNG outputs, and keep hardware run data separate from planned source profiles.

## Feature Highlights

| Workspace | Main Capabilities |
| --- | --- |
| **AFM/KPFM Controller** | Keithley current-source control, current or calibrated-intensity source mode, Quick Test, recurrent and step timing, function-profile overlay, live voltage plotting, source-profile export, measured-run CSV export |
| **AFM/KPFM Analysis** | CPD TIFF/PNG loading, CPD or energy display, HOPG reference fitting, illuminated-region marking, mask workflows, dark/light histograms, row/time profiles |
| **APS/DWF/SPV** | APS, DWF, workfunction, DOS, and SPV analysis with plotting and CSV export workflows |
| **TPC Control** | Red/green laser-diode current control through Keithley hardware with current-limit handling |
| **Raman Baseline** | Raman TXT loading, `asPLS`, `drPLS`, and `Polynomial/backcor` baseline correction, optional WiRE analysed overlay, corrected-spectrum export |
| **Raman Mapping** | WiRE WDF/TXT mapping import, spectrum unstacking, average/normalised previews, raw/location/selected tabs, Origin-friendly TXT export, selected spectra transfer to Insitu EChem |
| **Raman Insitu EChem** | Sequence/WDF import, peak-window extraction, peak position and intensity tracking, normalised intensity ratios, sequence/time plotting, PNG and CSV export |

## Why This Project Is Useful

Many research scripts solve one step of a workflow. This project tries to connect the full loop:

- **Before the experiment:** build and preview source profiles before sending anything to hardware.
- **During the experiment:** keep source-current commands bounded by an internal safety limit and show live voltage/current context.
- **After the experiment:** analyse images and spectra without manually reshaping files.
- **Across sessions:** restore tabs, parameters, and loaded paths when desired, while never restoring active hardware output.

The result is not a polished commercial instrument suite. It is research software built around real lab routines, where the details matter: disabled fields must not be parsed, OFF stages must not query the Keithley, selected Raman sequence numbers must not be renumbered, and measured hardware data should only be written when the user explicitly saves it.

## Screenshots

The interface is built around a fixed left-control / right-preview layout, so each workspace stays readable while experiments and analysis steps become more complex.

![AFM/KPFM Controller](assets/images/AFM_KPFM_Controller.png)

*AFM/KPFM Controller: source setup, sequence controls, calibration/function tools, and live preview in one workspace.*

![Raman Insitu EChem Analysis](assets/images/Raman_Insitu-Echem_Analysis.png)

*Raman Insitu EChem: sequence spectra, peak positions, peak intensities, and normalised ratios in a single analysis view.*

### Full Gallery

#### AFM/KPFM

![AFM/KPFM Controller](assets/images/AFM_KPFM_Controller.png)

![AFM/KPFM Intensity Calibration](assets/images/AFM_KPFM_Controller_Intensity_Calibration.png)

![AFM/KPFM Analysis](assets/images/AFM_KPFM_Analysis.png)

![AFM/KPFM HOPG Fit](assets/images/AFM_KPFM_Analysis_HOPG_fit.png)

![AFM/KPFM Profiles](assets/images/AFM_KPFM_Analysis_profiles.png)

#### APS/DWF/SPV

![APS Analysis](assets/images/APS_Analysis.png)

![APS Linear Analysis](assets/images/APS_Analysis_APS_analysis.png)

![DOS Analysis](assets/images/APS_Analysis_DOS_analysis.png)

![SPV Analysis](assets/images/APS_Analysis_SPV.png)

#### Raman

![Raman Baseline](assets/images/Raman_Baseline.png)

![Raman Mapping](assets/images/Raman_mapping.png)

![Raman Mapping Location Read](assets/images/Raman_mapping_location-read.png)

![Raman Mapping Selected Spectra](assets/images/Raman_mapping_Selected.png)

![Raman Insitu EChem Peak Windows](assets/images/Raman_Insitu-Echem_Peak-windows.png)

![Raman Insitu EChem Analysis](assets/images/Raman_Insitu-Echem_Analysis.png)

#### TPC

![TPC Controller](assets/images/TPC_controller.png)

## Installation

The known working environment is:

- Windows
- Python 3.13.x
- wxPython 4.2.x
- pyserial 3.5
- numpy
- matplotlib
- scipy
- Pillow
- renishawWiRE, required for `.wdf` Raman files

Install in editable mode from the repository root:

```cmd
pip install -e .
```

If wxPython installation is difficult on a new machine, install a compatible wheel for your Python version first, then rerun the editable install.

## Run

From a source checkout:

```cmd
python run_ca_app.py
```

Or after editable installation:

```cmd
ca-app
```

The active packaged application lives under:

```text
src/ca_app/
```

The top-level GUI shell is:

```text
src/ca_app/gui/main_frame.py
```

## Quick Start

1. Launch the app with `python run_ca_app.py`.
2. Choose a workspace from the `View` menu.
3. For analysis workflows, load the required data file and inspect the preview tabs before saving.
4. For hardware workflows, confirm COM port, baudrate, voltage compliance, and internal max current before enabling output.
5. Use `Save Parameters` / `Load Parameters` for explicit workflow files.
6. Use the `Restore` menu only for automatic app-state restore between launches.

## AFM/KPFM Controller

The AFM/KPFM controller operates a Keithley source meter over RS-232 serial communication.

Core hardware mode:

```text
Source: current
Measure: voltage
Default COM port: COM3
Default baudrate: 38400
Default voltage compliance: 5.0 V
Default internal max current: 110.0 mA
```

The Keithley always receives current commands. In intensity mode, the requested optical intensity is converted to the required source current using the loaded calibration model before any hardware command is sent.

Supported control styles:

- **Quick Test:** standalone ON/OFF hardware test.
- **Recurrent control:** repeated ON/OFF pattern.
- **Step control:** row-based ON/OFF sequence and the default base pattern.
- **Function control:** an `f(x)` profile overlaid onto recurrent or step ON stages.

Function control is not a separate timing pattern. It replaces ON-stage values while preserving the ON durations from the recurrent or step pattern. When Function control is enabled, the base ON value fields are disabled because the function profile supplies the current or intensity.

## Calibration And Function Profiles

The default calibration file is:

```text
src/ca_app/resources/default_intensity_calibration.csv
```

Accepted calibration format:

```text
Current_mA,Intensity_mW
```

The loader also accepts any two numeric columns where the first numeric column is current in mA and the second is intensity in mW.

Default calibration fit range:

```text
67 to 94 mA
```

Available calibration methods:

- `Empirical power-exp`
- `Two threshold power`
- `Two stage softplus slope`
- `Generalized exponential power`
- `Polynomial degree 3`
- `Interpolation`
- `Linear`
- `Quadratic`
- `Cubic`

The empirical models are smooth interpolation fits for measured calibration data. They are not physical laser-diode equations and should not be used for extrapolation far outside the measured range.

Default function profile:

```text
f(x) = x*m+b
X min = 0
X max = 180
Y min = 0.1
Y max = 4.99
```

The `Fit it` button can solve parameterised expressions such as:

```text
x*m+b
a*x^2+b*x+c
```

After fitting, the expression is replaced with a numeric expression so preview, validation, CSV export, and execution use the same safe evaluator.

## Hardware Safety Model

This project intentionally keeps hardware behavior explicit.

- All commanded source currents are checked against `Internal max current / mA`.
- Quick Test and Function control are mutually exclusive.
- Quick Test and sequence execution do not run at the same time.
- `START` freezes a run snapshot before opening the serial port.
- GUI calibration and function edits during a run update previews only; they do not change the active Keithley output current.
- OFF stages send `:OUTP OFF` and do not send `:READ?`, `:INIT`, or `:FETCH?`.
- OFF stages log local software-known `0 mA` source rows with blank measured voltage/current fields.
- Normal finish, STOP, and exception cleanup all attempt to set source current to `0 mA` and then send `:OUTP OFF`.
- Measured Keithley run data is saved only when `Save Keithley CSV` is clicked.

Before connecting hardware, confirm the COM port, baudrate, compliance voltage, internal current limit, wiring, and optical calibration are safe for the actual setup.

## AFM/KPFM Image Analysis

The AFM/KPFM Analysis tab loads CPD images from TIFF or PNG files. TIFF loading attempts to locate raw image-sized metadata/tag arrays automatically. PNG loading uses user-provided voltage min/max values to rescale pixel values.

Main features:

- CPD or Energy display.
- HOPG reference peak fitting for Energy mode.
- Slow scan direction handling.
- Row or time x-axis profiles.
- Illuminated-region marking.
- One-mask and two-mask workflows, including inverse and middle mask generation.
- Dark/light histogram comparison.
- Robust preview colour scaling to reduce outlier-dominated colourbars.
- Selectable image colormaps.

## Raman Workflows

The Raman workspace contains four tabs:

```text
Baseline
Mapping
Insitu EChem
Electrical
```

The `Electrical` tab is currently reserved.

### Raman Baseline

Raman Baseline loads text files with at least two numeric columns:

```text
#Wave    #Intensity
1820.535156    3780.142822
...
```

Available methods:

- `asPLS`
- `drPLS`
- `Polynomial/backcor`

Auto mode evaluates the visible candidate parameter lists. Manual mode accepts one value per parameter and refits only when `Fit` is clicked.

The preview shows:

- raw Raman spectrum with estimated baseline
- baseline-corrected Raman spectrum with optional WiRE analysed overlay

Save writes only the corrected two-column spectrum. The default output filename is the raw file stem plus `_Copy.txt`.

### Raman Mapping

Raman Mapping supports:

- WiRE WDF mapping files
- WiRE stacked TXT mapping files with `#X`, `#Y`, `#Wave`, and `#Intensity`

The workflow unstacks spectra into a wide table where column 1 is wavenumber, later columns are individual spectra, and final columns contain averaged and normalised intensity.

Preview tabs:

- `Avg./Norm.`
- `Raw data`
- `Location`
- `Selected`

Selected spectra use 1-based column labels and accept inclusive ranges:

```text
1,2-4,5
45-60
```

Selected-column numbers are preserved during plotting, TXT export, and in-memory transfer to Insitu EChem.

### Raman Insitu EChem

Insitu EChem accepts Raman sequence text files:

```text
#Time    #Wave    #Intensity
0.000000    2063.746094    3895.066162
...
```

It also accepts:

```text
#Sequence    #Wave    #Intensity
1.000000    1728.768555    64.341232
...
```

and WDF sequence files.

The analysis extracts local peak maxima inside user-defined Raman-shift windows and plots:

- every N-th spectrum with peak windows
- peak positions vs sequence or calibrated time
- peak intensities vs sequence or calibrated time
- intensity ratios normalised to a selected peak

Default peak windows:

```text
1371 +/- 5
1423 +/- 6
1516 +/- 5
1606 +/- 5
```

When input uses `#Sequence`, or when data is transferred from Mapping/WDF sequence workflows, Sequence mode is forced and the Time x-axis option is disabled. Sequence labels are treated as real labels and are not remapped to `1..N`.

## Save, Restore, And Export

Manual parameter files use JSON and are separate from automatic app-state restore.

The `Restore` menu controls how much state is remembered between launches:

- `View`: restore only the last top-level workspace.
- `Tab`: restore the workspace and selected notebook tabs.
- `Parameters`: restore workspace, tabs, loaded file paths, typed values, choices, and checkboxes where supported.

The app does not save or restore active hardware output, measured voltage, runtime logs, live plot data, or measured run data through app-state restore.

Important export paths:

- `Save CSV (Source)`: saves the planned source profile only.
- `Save Keithley CSV`: saves measured AFM/KPFM run data only when clicked.
- Raman Mapping `Save`: exports Origin-friendly TXT.
- Raman Mapping `Save selected`: exports selected Raman sequence TXT.
- Raman Insitu EChem save buttons each write one PNG and one CSV.

## Project Layout

```text
run_ca_app.py
  Source-checkout launcher.

src/ca_app/app.py
  Application entrypoint used by the console script.

src/ca_app/constants.py
  Import-safe application defaults.

src/ca_app/gui/main_frame.py
  Top-level frame, View menu, Restore menu, workspace switching,
  app-state persistence, and About dialogs.

src/ca_app/gui/panels/
  Independent wxPython workspace panels.

src/ca_app/core/
  Analysis, calibration, function-profile, and data-processing logic.

src/ca_app/hardware/
  Keithley serial settings and SCPI command helpers.

src/ca_app/io/
  File import/export boundaries.

src/ca_app/resources/
  Bundled calibration CSVs and example parameter resources.

src/ca_app/runtime/
  Planned extraction area for future worker services.

tests/
  Non-hardware tests for core logic and GUI-state behavior.
```

## Development

Run the non-hardware test suite:

```cmd
python -m unittest discover -s tests
```

Run a compile check:

```cmd
python -m compileall src tests
```

The tests focus on analysis logic, calibration/function-profile behavior, Raman workflows, TPC current handling, COM-port defaults, and workspace state restoration.

## Documentation

Additional notes live in:

- [docs/architecture.md](docs/architecture.md)
- [docs/hardware_safety.md](docs/hardware_safety.md)
- [docs/calibration_models.md](docs/calibration_models.md)
- [src/ca_app/runtime/README.md](src/ca_app/runtime/README.md)

## Project Status

This is active research software. It is designed around real laboratory workflows and has non-hardware tests for the core logic, but hardware operations must still be reviewed against the connected instrument and sample before use.

For new contributors, the safest path is to start with analysis and file-processing workflows, then study the hardware safety notes before changing controller behavior.
