# Calibration Models

Default calibration range is 67 to 94 mA.

Empirical model choices:

- `Empirical power-exp`
- `Two threshold power`
- `Two stage softplus slope`
- `Generalized exponential power`
- `Polynomial degree 3`

These models are empirical interpolation functions. They are not physical laser diode equations and should not be used for extrapolation far outside the measured calibration range.

The Status / log panel reports fit range, trial progress, periodic evaluation-count/RMSE updates during long solves, final RMSE, and selected parameters.

The Calibration tab shows compact fit statistics as six labels:

- R2
- RMSE
- MAE
- Max error
- Current range
- Intensity range

## GUI Preview Integration

After a calibration CSV loads successfully, the GUI switches to the `Intensity calibration` preview tab.

When a calibration model is loaded, the `Source profile` preview may show both representations of the planned source:

- Left y-axis: required/source current in mA.
- Right y-axis: target or predicted intensity in mW.

In intensity mode, the right axis is the requested target intensity and the left axis is the current converted through the calibration model. In current mode, the left axis is the requested current and the right axis is the model-predicted intensity.

## Runtime Isolation

Calibration edits are live preview/editing state until the next run starts. When `START` is clicked, the controller freezes the selected calibration method, fit range, calibration path, and calibration model into a run snapshot.

Changing fit method or fit range during a running sequence may update this tab and the preview plots, but it must not change the active Keithley output current. The worker uses only currents and function current profiles computed from the frozen snapshot.
