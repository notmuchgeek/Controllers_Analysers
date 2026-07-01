# Raman Workflows

The Raman workspace is implemented in one wx panel module, `raman_panel.py`, with separate classes for Baseline, Converting, Mapping, Insitu EChem, and Electrical. Core logic lives in dedicated modules.

## Baseline

Raman Baseline batch-loads single-spectrum and multi-spectrum TXT/WDF files into
a checked, reorderable list, then fits every loaded file using one shared
`asPLS`, `drPLS`, or `Polynomial/backcor` settings snapshot. Checks affect only
the overlaid preview; Ctrl/Shift row selection controls list operations.

Raman spectrum preview axes display from smaller wavenumbers on the left to larger wavenumbers on the right, even when input files store wavenumbers in descending order.

Multi-spectrum TXT inputs may use `#Time/#Wave/#Intensity`,
`#Sequence/#Wave/#Intensity`, or Origin-style wide data. One shared `Selected
columns` value controls the same preview columns across every checked
multi-spectrum file and requires `Update`; fitting processes every internal
spectrum. Single-file `Save` preserves its previous behavior, while `Save all`
chooses one folder, uses collision-safe `<source_stem>_Copy.txt` names, and
preserves each input's logical format.

## Converting

Raman Converting batch-loads WDF and TXT files into a Ctrl/Shift multi-select list. Every new entry is checked by default, and checked files are overlaid in the overview independently of row selection. Checking or unchecking one selected row applies the same preview state to all selected rows. List entries can be deleted or drag-reordered, while typed Min/Max fields limit the Raman-shift preview range and remain unchanged when more files are loaded.

`Load to Baseline` transfers one selected item in memory for parameter checking. Baseline settings return only through `Send params to Converting`, which validates the visible settings and opens Converting. Ordinary tab changes do not synchronize settings. `Correct Baseline` processes every spectrum in every selected file and adds separate checked `_baselined` list entries without replacing the originals.

`Export All` chooses one folder and writes every list entry as an individual Origin-friendly TXT containing wavenumber and raw spectrum columns. WDF inputs become `.txt`; corrected entries use `_baselined.txt`. Duplicate output names receive numeric suffixes.

## Mapping

Raman Mapping reads WiRE WDF files and stacked TXT mapping files. It unstacks spectra into a wide table, previews raw/location/selected spectra, exports Origin TXT, and transfers selected spectra to Insitu EChem in memory.

Selected spectra use 1-based labels and must preserve their original sequence numbers.

The `Legend` checkbox in the Load file section is available for `Every N = 1` and affects only the `Raw data` preview.

The Save file section can include or exclude averaged and normalised columns. Origin TXT exports use repeated `Intensity` long names, `cm\+(-1)` as the wavenumber unit, and `Sequence N` labels in the third header row.

`Save one for each` chooses one folder and exports every raw spectrum separately as `<source_stem>_sequence_<sequence>.txt`. Each output has only `Wavenumber`/`Intensity` names, `cm\+(-1)`/`a.u.` units, and two-column data; it omits the redundant sequence header row and all averaged/normalised values.

## Insitu EChem

Insitu EChem accepts time-coded TXT, sequence-coded TXT, WDF sequences, and Mapping transfers. It extracts local peak maxima inside user-defined windows and plots peak positions, intensities, normalized ratios, and inverse ratios when `inverse` is checked.

The Figure section has independent legend checkboxes for Spectrum, Peak Position, Peak Intensity, and Peak Ratio. The Save Plot/Data section has two rows of buttons: Save Spectra and Save Peak Position, then Save Peak Intensity and Save Peak Ratios.

`#Sequence` inputs force Sequence mode; do not remap sequence labels.

Spectrum preview axes display from smaller wavenumbers on the left to larger wavenumbers on the right.

## Electrical

Raman Electrical reads exact-column electrical CSV files and previews V_Gate, V_Drain, I_Gate, I_Drain, and the combined V_Gate/I_Drain view. Drain current is shown in mA, and the V_Gate/I_Drain preview marks gate-pulse intervals with red spans. It classifies V_Gate and V_Drain as missing, const, pulse, or changing.



