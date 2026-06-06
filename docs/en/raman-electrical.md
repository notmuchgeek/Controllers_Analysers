# Raman Electrical

Raman Electrical is a CSV preview and voltage-classification tool in the Raman workspace.

## Required CSV Columns

The loader intentionally requires exact names:

```text
Gate Time
Gate Voltage
Gate Current
Drain Time
Drain Voltage
Drain Current
```

Missing columns are reported; the program does not infer channels from filenames or aliases.

## Preview Tabs

`Raw data` shows four subplots:

1. Gate V
2. Drain V
3. Gate I
4. Drain I

The Electrical section has one shared `Raw data / s` text box and slider. It controls the first-N-second window for all four raw plots. Raw linewidth is automatic: short windows use thicker lines and long windows use thinner lines, clamped between 0.25 and 1.5.

`V_Gate/V_Drain` plots V_Gate and V_Drain on one figure with two y-axes. It has separate `V_Gate / s` and `V_Drain / s` controls.

## Classification

`core/raman_electrical.py` classifies voltage traces:

- `missing`: required time or voltage column is absent or empty.
- `const`: voltage range is within tolerance.
- `pulse`: active segments are detected against the most common baseline.
- `changing`: voltage changes but does not form a clean pulse.

The summary table shows row count, total time, classification, constant voltage, pulse count, initial pulse time, and median pulse duration. Not-applicable values display as `-`.

