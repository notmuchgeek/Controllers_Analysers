# Testing

Version: `v16.17.260608.0011`

Testing has two layers: automated non-hardware tests and manual GUI checks. Hardware tests require explicit user confirmation.

## Automated Checks

Run from the project root:

```cmd
python -m compileall src tests
python -m unittest discover -s tests
```

The compile check catches syntax and import problems. The unit test suite covers non-hardware behavior such as profile generation, calibration logic, Raman parsing, state adapters, and GUI-safe helper behavior.

## Manual Startup Check

Run:

```cmd
python run_ca_app.py
```

Confirm that the window title is:

```text
Controller & Analysers v16.17.260608.0011
```

Open `Help -> About` and confirm the same version appears in the Versions section.

## AFM/KPFM Controller Checks

Without connecting hardware, verify:

- COM port defaults to editable `COM3`.
- Baudrate defaults to `38400` and offers `9600`, `19200`, `38400`, `57600`.
- Compliance voltage is editable.
- Internal max current is visible and editable.
- Current mode and Intensity mode radio buttons are exclusive.
- Default calibration auto-loads when the resource CSV is present.
- Default fit method is `Empirical power-exp`.
- Default fit range is `67` to `94`.
- Function tab defaults to `x*m+b`, `0`, `180`, `0.1`, `4.99`.
- `Fit it` solves `m` and `b`.
- Function control disables Recurrent/Step ON value fields.
- Function control can build a preview without parsing disabled ON value fields.
- Quick Test and Function control remain mutually exclusive.
- Save CSV (Source) refuses Quick Test.

## Raman Checks

Baseline:

- `Load txt/wdf` loads a two-column Raman file, sequence TXT, or WDF.
- Multi-spectrum Baseline inputs enable `Selected columns` and require `Update` to redraw preview selections.
- Single-spectrum Baseline inputs disable `Selected columns` and `Update`.
- Auto mode fits after loading.
- Manual mode waits for `Fit`.
- Save writes corrected data in the same logical format as the input.

Mapping:

- `Load wdf/txt` loads mapping WDF or stacked TXT.
- `Avg./Norm.` uses an aligned table preview.
- Save file can include/exclude averaged and normalised columns.
- Save file uses `cm\+(-1)` and third-row `Sequence N` labels for Origin compatibility.
- `Raw data` honors preview stride and legend behavior.
- Selected spectra preserve original sequence/column labels.
- `Load to Insitu Echem` transfers in memory.

Insitu EChem:

- `Load wdf/txt` accepts WDF and sequence TXT.
- `#Sequence` input disables Time mode.
- Sequence labels are preserved.
- Peak-window edits update previews.
- Figure legend checkboxes independently show/hide Spectrum, Peak Position, Peak Intensity, and Peak Ratio legends.
- Save Plot/Data buttons are arranged as Save Spectra / Save Peak Position and Save Peak Intensity / Save Peak Ratios.
- Figure titles use title case with small connector words such as `to`, `vs`, `and`, and `with` kept lower-case unless an acronym, unit, or scientific notation requires otherwise.

Electrical:

- `Load csv` switches to the `Vg/Vd` preview tab.
- The shared Raw preview seconds control adjusts all four raw plots.
- V_Gate/V_Drain first-second controls update the dual-axis preview.
- V_Gate/I_Drain uses the shared Raw preview seconds control, raw linewidth scaling, mA drain current, and red gate-pulse spans.
- Tables use `-` for not-applicable pulse fields.
- Raw plot linewidth decreases as preview seconds increase.

## State Restore Checks

Use the Restore menu:

- `View` restores only the top-level workspace.
- `Tab` restores workspace and selected notebook pages.
- `Parameters` restores supported values and loaded paths.

Never restore active hardware output, measured voltage, runtime log text, live plot data, or run-data rows.

## Hardware Checks

Only perform hardware checks after explicit confirmation. See [Hardware safety](hardware-safety.md).




