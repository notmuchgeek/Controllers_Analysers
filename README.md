# Controllers & Analysers

**English** | 
Version: `v16.2.260606.2137`

Controllers & Analysers is a wxPython desktop application for laboratory control and scientific analysis workflows. It combines Keithley-based AFM/KPFM control, CPD image analysis, APS/DWF/SPV analysis, TPC laser-diode control, Raman baseline correction, Raman mapping, Raman in situ electrochemical sequence analysis, and Raman Electrical current-voltage preview tools.

## Documentation

The detailed documentation is split by audience and language:

- [English documentation index](docs/en/index.md)
- [Coding-agent instructions](AGENTS.md)

Useful starting points:

- [Project overview](docs/en/project-overview.md)
- [Architecture](docs/en/architecture.md)
- [Workspace guide](docs/en/workspace-guide.md)
- [Developer guide](docs/en/developer-guide.md)
- [Testing](docs/en/testing.md)
- [Versioning](docs/en/versioning.md)

## Main Workspaces

| Workspace | Main capabilities |
| --- | --- |
| AFM/KPFM Controller | Keithley current-source control, current/intensity modes, Quick Test, Recurrent/Step timing, function-profile overlay, calibration, live voltage preview, source CSV export, measured Keithley CSV export |
| AFM/KPFM Analysis | CPD image loading, CPD/energy display, HOPG fitting, illuminated regions, masks, histograms, row/time profiles |
| APS/DWF/SPV | APS, DWF, workfunction, DOS, and SPV analysis with plotting and CSV export workflows |
| TPC Control | Red/green laser-diode current control through Keithley hardware |
| Raman Baseline | TXT loading, `asPLS`, `drPLS`, `Polynomial/backcor`, corrected spectrum export |
| Raman Mapping | WiRE WDF/TXT mapping import, average/normalised previews, raw/location/selected previews, selected spectra export and transfer |
| Raman Insitu EChem | Sequence/WDF import, peak windows, peak positions, peak intensities, normalized ratios, PNG/CSV export |
| Raman Electrical | Electrical CSV import, four-channel raw preview, V_Gate/V_Drain dual-axis preview, pulse summary table |

## Install

Known working environment:

- Windows
- Python 3.13.x
- wxPython 4.2.x
- pyserial 3.5
- numpy
- matplotlib
- scipy
- Pillow
- `renishawWiRE` for `.wdf` Raman files

Install from the project root:

```cmd
pip install -e .
```

## Run

```cmd
python run_ca_app.py
```

The window title should show:

```text
Controller & Analysers v16.2.260606.2137
```

## Test

```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

Hardware tests are not part of the default test suite. Any real Keithley or laser-diode check must be explicitly confirmed with safe current and compliance settings.

## Version Rule

The v16 series uses:

```text
v<major>.<minor>.<YYMMDD>.<HHMM>
```

For `v16.2.260606.2137`, `v16` is the larger version series, `2` is the smaller version inside v16, `260606` is the edit date, and `2137` is the exact 24-hour edit time. See [Versioning](docs/en/versioning.md).

