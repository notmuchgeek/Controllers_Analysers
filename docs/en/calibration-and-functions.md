# Calibration And Function Profiles

Version: `v16.11.260607.0040`

This document describes the two transformation layers used by the AFM/KPFM controller: current-intensity calibration and function-profile generation.

## Calibration Purpose

The Keithley only sources current. Intensity mode exists for the user, not for the instrument. When the user requests optical intensity in `mW`, the application converts that target into the source current required by the calibration model.

## Default Calibration

The default calibration file is:

```text
src/ca_app/resources/default_intensity_calibration.csv
```

Expected headers:

```text
Current_mA,Intensity_mW
```

The loader also accepts any CSV with at least two numeric columns. The first numeric column is treated as current in mA and the second as intensity in mW.

## Default Fit Range

The default fit range is:

```text
67 to 94 mA
```

Empirical fits are intended for smooth interpolation inside the measured region. They are not physical laser diode equations and should not be used for far extrapolation.

## Supported Fit Methods

The GUI exposes:

- Empirical power-exp.
- Two threshold power.
- Two stage softplus slope.
- Generalized exponential power.
- Polynomial degree 3.
- Interpolation.
- Linear.
- Quadratic.
- Cubic.

The public import surface is `src/ca_app/core/calibration_models.py`. The implementation logic is concentrated in `src/ca_app/core/intensity_profile_tools.py`.

## Fit Statistics

The calibration tab shows compact statistics as labels, not as a free text report. This is intentional because the calibration panel must remain dense enough to fit the fixed GUI layout.

The log still reports longer fit progress, including fit range, trial progress, evaluation counts for long empirical fits, and final selected parameters.

## Function Profile

The default function profile is:

```text
f(x) = x*m+b
X min = 0
X max = 180
Y min = 0.1
Y max = 4.99
```

The `Fit it` button solves parameterized expressions. Unknown names other than `x`, allowed functions/constants, and `np` are treated as fit parameters.

Examples:

```text
x*m+b
a*x^2+b*x+c
```

`Parameterise` converts numeric constants in the current expression back into alphabetic fit parameters from left to right. Equal numeric values are intentionally treated as separate parameters.

When parameters are fitted, the expression is replaced with a numeric expression. Preview, validation, export, and runtime execution then use the same safe evaluated form.

## Function Execution

Function control overlays the base timing pattern. Recurrent or Step still decides where ON stages occur and how long each ON stage lasts. The function supplies the ON-stage source value.

When Function control is enabled:

- Recurrent/Step ON value fields are disabled.
- Disabled ON values must not be parsed.
- ON durations remain active and define function-profile injection windows.
- Current-mode functions produce current directly.
- Intensity-mode functions produce target intensity, then convert through the frozen calibration snapshot.

## Runtime Safety

Function arrays and calibration models are frozen at `START`. GUI edits after `START` update previews only and must not change the active output current.

