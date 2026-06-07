# AFM/KPFM Analysis

AFM/KPFM image analysis is split between GUI controls in `afm_analysis_panel.py` and core image functions in `core/afm_kpfm_analysis.py`.

## Inputs

- TIFF CPD images: loader searches image-sized raw float metadata/tag arrays.
- PNG CPD images: user supplies voltage min/max for rescaling.
- Optional masks: loaded and resized with nearest-neighbor semantics.

## Main Concepts

- CPD mode displays contact-potential values.
- Energy mode converts CPD using HOPG work-function references.
- Slow scan direction controls row ordering and profile interpretation.
- Illuminated regions define dark/light comparisons.
- One-mask workflow creates inverse masks.
- Two-mask workflow creates upper/lower/middle masks.

## Outputs

The panel supports image previews, histograms, masked histograms, row profiles, time profiles, and HOPG Gaussian peak fitting. Parameter restore should preserve user-typed values and loaded paths but never restore transient preview state.

## Core Responsibilities

Core functions handle loading, mask construction, row ordering, histograms, Gaussian fitting, region validation, and CPD-to-energy conversion. GUI code should not duplicate these calculations.




