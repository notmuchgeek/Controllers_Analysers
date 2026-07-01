# File Formats

Version: `v16.22.260701.0042`

This document lists the user-facing file formats expected by the application.

## Calibration CSV

Preferred header:

```text
Current_mA,Intensity_mW
```

The loader also accepts two numeric columns where column 1 is current in mA and column 2 is intensity in mW.

## Raman Baseline TXT/WDF

Single-spectrum TXT files may use two numeric columns:

```text
#Wave    #Intensity
1820.535156    3780.142822
```

The loader uses the first two numeric columns as Raman shift and intensity.

Baseline also accepts multi-spectrum TXT using `#Time/#Wave/#Intensity`, `#Sequence/#Wave/#Intensity`, or Origin-style wide data where the first numeric column is wavenumber and remaining numeric columns are spectra. Single-spectrum and multi-spectrum WDF files are supported when `renishawWiRE` is installed.

Saved corrected output follows the loaded logical input format: two-column TXT, `#Time/#Wave/#Intensity`, `#Sequence/#Wave/#Intensity`, or Origin-style wide TXT.

Baseline `Save all` chooses one destination folder and writes every successfully
fitted source as `<source_stem>_Copy.txt`. Duplicate source stems receive `_2`,
`_3`, and later suffixes while every output preserves its own logical input
format.

## Raman Converting WDF/TXT

Converting accepts WDF, stacked mapping/sequence TXT, Origin-style wide TXT, and two-column TXT. Each list item exports independently in Origin-friendly wide TXT format with three header rows, a wavenumber column, and one column per spectrum. Converting exports do not add averaged or normalised columns.

Baseline-corrected list entries use the source stem plus `_baselined`; WDF source extensions are replaced with `.txt` during export.

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

Mapping Save file exports Origin-friendly TXT with repeated `Intensity` long names, `cm\+(-1)` as the wavenumber unit, `Sequence N` labels in the third header row, and optional averaged/normalised columns.

Mapping `Save one for each` writes `<source_stem>_sequence_<sequence>.txt` for every raw spectrum. These individual files have two header rows (`Wavenumber`/`Intensity`, then `cm\+(-1)`/`a.u.`) and two numeric columns. They do not contain a third sequence row, averaged intensity, or normalised intensity.

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




