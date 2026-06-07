# Project Overview

Controllers & Analysers is a Windows-first wxPython desktop application for laboratory experiment control and data analysis. It combines Keithley-based AFM/KPFM light-bias control, CPD image analysis, APS/DWF/SPV analysis, TPC laser-diode control, Raman baseline correction, Raman Mapping, Raman Insitu EChem analysis, and Raman Electrical CSV preview/classification.

The project is research software. The goal is not to hide scientific workflow details, but to make repeated experimental operations reproducible, inspectable, and safer. GUI state, file paths, parameter files, source previews, and measured hardware data are deliberately separated.

## Current Version

Current project version: `v16.11.260607.0040`.

The v16 line is a larger documentation and workflow consolidation release. The application title, About/Versions dialogs, package metadata, and documentation must all use the same version.

## Primary Users

- Experimental researchers who need one desktop application for control and analysis.
- Maintainers adding new analysis panels or cleaning old scripts into reusable modules.
- Coding agents that need reliable project context before editing source files.

## Main Workspaces

- `AFM/KPFM`: Keithley source control and AFM/KPFM CPD image analysis.
- `APS`: APS, DWF, workfunction, DOS, and SPV analysis.
- `TPC`: red/green laser-diode current control through Keithley hardware.
- `Raman`: Baseline, Mapping, Insitu EChem, and Electrical analysis tabs.

## Design Priorities

- Hardware safety before convenience.
- Stable file formats and explicit export buttons.
- Fixed left-control/right-preview GUI layout.
- Tests for core logic and state behavior.
- Clear boundaries between GUI, core analysis, hardware, IO, and planned runtime services.


