# Raman Workflows

The Raman workspace is implemented in one wx panel module, `raman_panel.py`, with separate classes for Mapping, Electrical, Insitu EChem, and Baseline. Core logic lives in dedicated modules.

## Baseline

Raman Baseline reads two-column TXT files and fits substrate baselines using `asPLS`, `drPLS`, or `Polynomial/backcor`. Auto mode searches visible candidate lists. Manual mode uses one value per parameter.

## Mapping

Raman Mapping reads WiRE WDF files and stacked TXT mapping files. It unstacks spectra into a wide table, previews raw/location/selected spectra, exports Origin TXT, and transfers selected spectra to Insitu EChem in memory.

Selected spectra use 1-based labels and must preserve their original sequence numbers.

## Insitu EChem

Insitu EChem accepts time-coded TXT, sequence-coded TXT, WDF sequences, and Mapping transfers. It extracts local peak maxima inside user-defined windows and plots peak positions, intensities, and normalized ratios.

`#Sequence` inputs force Sequence mode; do not remap sequence labels.

## Electrical

Raman Electrical reads exact-column electrical CSV files and previews V_Gate, V_Drain, I_Gate, and I_Drain. It classifies V_Gate and V_Drain as missing, const, pulse, or changing.

