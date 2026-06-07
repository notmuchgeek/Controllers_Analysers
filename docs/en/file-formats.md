# File Formats

Version: `v16.11.260607.0040`

This document lists the user-facing file formats expected by the application.

## Calibration CSV

Preferred header:

```text
Current_mA,Intensity_mW
```

The loader also accepts two numeric columns where column 1 is current in mA and column 2 is intensity in mW.

## Raman Baseline TXT

Two numeric columns:

```text
#Wave    #Intensity
1820.535156    3780.142822
```

The loader uses the first two numeric columns as Raman shift and intensity.

Saved corrected output is also two-column text.

## Raman Mapping TXT

Stacked mapping text:

```text
#X    #Y    #Wave    #Intensity
```

The loader unpacks stacked spectra into a wide table with:

- Wavenumber column.
- One column per spectrum.
- Averaged intensity.
- Normalised intensity.

## Raman Mapping WDF

WiRE `.wdf` mapping files are supported when `renishawWiRE` is installed.

Location and embedded image metadata are shown when available. Some sequence WDF files legitimately have no location or image metadata.

## Selected Spectra TXT

Mapping selected export uses:

```text
#Sequence    #Wave    #Intensity
```

The `#Sequence` value is the original selected spectrum/column label. It must not be renumbered to `1..N`.

## Insitu EChem TXT

Supported sequence formats:

```text
#Time    #Wave    #Intensity
```

and:

```text
#Sequence    #Wave    #Intensity
```

Time mode maps sorted raw time sequence codes to `sequence_index = 1..N` and then uses:

```text
time_s = Time Offset + sequence_index * Time per sequence
```

Sequence mode preserves sequence labels.

## Electrical CSV

The Raman Electrical workspace reads a current-voltage CSV compatible with the workflow migrated from `current_voltage_single_file_processor_v2.ipynb`.

Expected signal columns are:

- Gate voltage.
- Gate current.
- Drain voltage.
- Drain current.

The GUI presents these as `V_Gate`, `I_Gate`, `V_Drain`, and `I_Drain`, with Gate and Drain rendered as subscripts where the GUI toolkit allows.

The Electrical tab does not display the filename in the pulse summary table. The table focuses on pulse counts, timing, const/pulse mode, and values.

## Exports

Export behavior is intentionally explicit:

- AFM/KPFM `Save CSV (Source)` exports planned source profile only.
- AFM/KPFM `Save Keithley CSV` exports measured run data only when clicked.
- Raman analysis buttons save their corresponding PNG and CSV/TXT outputs.
- Sequence completion must not auto-create run-data files.

