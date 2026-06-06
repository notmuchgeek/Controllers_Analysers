# APS, DWF, DOS, And SPV

The APS workspace lives in `aps_panel.py`; core logic lives in `core/aps_analysis.py`.

## Supported Analysis

- APS import and HOMO fitting.
- DWF import and workfunction statistics.
- Reference APS/reference DWF calibration.
- DOS smoothing.
- SPV timing, background correction, and normalization.

## Preview Controls

DWF statistic preview sliders use an uneven mapping: the first 70% of the slider gives fine control over the first 30% of the range. This pattern is reused by Raman Electrical preview sliders.

## File Handling

Core import functions read numeric data and DAT metadata. Save functions write Origin-friendly CSV outputs. GUI code owns file dialogs, preview drawing, and logging.

## Maintenance Notes

Keep settings parsing in the panel and data processing in `core/aps_analysis.py`. When adding a new APS output, add a focused test for the generated CSV shape and header.

