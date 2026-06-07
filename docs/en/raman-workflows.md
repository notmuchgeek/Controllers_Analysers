# Raman Workflows

The Raman workspace is implemented in one wx panel module, `raman_panel.py`, with separate classes for Mapping, Electrical, Insitu EChem, and Baseline. Core logic lives in dedicated modules.

## Baseline

Raman Baseline reads single-spectrum TXT/WDF files and multi-spectrum TXT/WDF files, then fits substrate baselines using `asPLS`, `drPLS`, or `Polynomial/backcor`. Auto mode searches visible candidate lists. Manual mode uses one value per parameter.

Raman spectrum preview axes display from smaller wavenumbers on the left to larger wavenumbers on the right, even when input files store wavenumbers in descending order.

Multi-spectrum TXT inputs may use `#Time/#Wave/#Intensity`, `#Sequence/#Wave/#Intensity`, or Origin-style wide data. The Baseline section's `Selected columns` field controls preview spectra only and requires `Update`; fitting and saving process every spectrum. Save output follows the loaded logical format.

## Mapping

Raman Mapping reads WiRE WDF files and stacked TXT mapping files. It unstacks spectra into a wide table, previews raw/location/selected spectra, exports Origin TXT, and transfers selected spectra to Insitu EChem in memory.

Selected spectra use 1-based labels and must preserve their original sequence numbers.

The `Legend` checkbox in the Load file section is available for `Every N = 1` and affects only the `Raw data` preview.

The Save file section can include or exclude averaged and normalised columns. Origin TXT exports use repeated `Intensity` long names, `cm\+(-1)` as the wavenumber unit, and `Sequence N` labels in the third header row.

## Insitu EChem

Insitu EChem accepts time-coded TXT, sequence-coded TXT, WDF sequences, and Mapping transfers. It extracts local peak maxima inside user-defined windows and plots peak positions, intensities, normalized ratios, and inverse ratios when `inverse` is checked.

The Figure section has independent legend checkboxes for Spectrum, Peak Position, Peak Intensity, and Peak Ratio. The Save Plot/Data section has two rows of buttons: Save Spectra and Save Peak Position, then Save Peak Intensity and Save Peak Ratios.

`#Sequence` inputs force Sequence mode; do not remap sequence labels.

Spectrum preview axes display from smaller wavenumbers on the left to larger wavenumbers on the right.

## Electrical

Raman Electrical reads exact-column electrical CSV files and previews V_Gate, V_Drain, I_Gate, I_Drain, and the combined V_Gate/I_Drain view. Drain current is shown in mA, and the V_Gate/I_Drain preview marks gate-pulse intervals with red spans. It classifies V_Gate and V_Drain as missing, const, pulse, or changing.



