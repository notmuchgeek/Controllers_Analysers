# Workspace Guide

The GUI uses a consistent fixed left/right layout. Left panels contain controls and save/load actions. Right panels contain preview notebooks and logs.

## AFM/KPFM Controller

The Controller tab sources current through a Keithley source meter. It supports current mode and calibrated intensity mode. The Keithley always receives current commands; intensity values are converted through the frozen calibration model before execution.

Sequence controls include Quick Test, Recurrent, Step, and Function control overlay. Function control replaces ON-stage values while preserving ON durations.

## AFM/KPFM Analysis

The Analysis tab loads CPD TIFF/PNG images, supports CPD/Energy display, HOPG reference fitting, illuminated region marking, mask workflows, histograms, and row/time profiles.

## APS

The APS workspace handles APS fitting, DWF/workfunction analysis, DOS smoothing, and SPV normalization. It provides raw-data previews and CSV exports for downstream analysis.

## TPC

The TPC workspace controls red or green laser-diode current using a Keithley current source. It enforces current limits and shows measured readback after output operations.

## Raman

The Raman workspace contains five tabs:

- `Baseline`: substrate-baseline correction for Raman TXT files.
- `Converting`: multi-file WDF/TXT preview, optional baseline correction, and individual Origin-friendly TXT export.
- `Mapping`: WDF/TXT mapping import, unstacking, table preview, selected spectra, and transfer to Insitu EChem.
- `Insitu EChem`: sequence peak-window analysis and normalized ratios.
- `Electrical`: electrical CSV preview, V_Gate/V_Drain classification, and V_Gate/I_Drain drain-current preview with gate-pulse spans.



