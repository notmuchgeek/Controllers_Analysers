"""Batch Raman WDF/TXT conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from ca_app.core.raman_baseline import (
    RamanBaselineBatchResult,
    RamanBaselineInput,
    baseline_input_from_mapping_dataset,
    read_raman_baseline_input,
)
from ca_app.core.raman_mapping import RamanDataset, export_origin_txt, load_raman_data


class RamanConvertingError(ValueError):
    pass


@dataclass
class RamanConversionItem:
    """One source or derived dataset shown in the Converting list."""

    display_name: str
    dataset: RamanDataset
    baseline_input: RamanBaselineInput
    source_path: Path
    derived: bool = False
    preview_enabled: bool = True

    @property
    def export_stem(self) -> str:
        return Path(self.display_name).stem


def baseline_input_to_dataset(source: RamanBaselineInput, source_type: str = "txt") -> RamanDataset:
    if not source.spectra:
        raise RamanConvertingError("No Raman spectra are available for conversion.")
    reference_x = np.asarray(source.spectra[0].raman_shift, dtype=float)
    columns = []
    for spectrum in source.spectra:
        x = np.asarray(spectrum.raman_shift, dtype=float)
        y = np.asarray(spectrum.intensity, dtype=float)
        if x.shape != reference_x.shape or not np.allclose(x, reference_x, rtol=0.0, atol=1e-6):
            raise RamanConvertingError("All spectra in a conversion item must use the same Raman-shift axis.")
        columns.append(y)
    labels = source.labels or tuple(float(index) for index in range(1, len(columns) + 1))
    return RamanDataset(
        source_path=source.source_path,
        source_type=source_type,
        wavenumber=reference_x,
        intensity_matrix=np.column_stack(columns),
        metadata={"Sequence": np.asarray(labels, dtype=float)},
    )


def load_conversion_item(path: str | Path, display_name: str | None = None) -> RamanConversionItem:
    path = Path(path)
    if path.suffix.lower() not in {".wdf", ".txt"}:
        raise RamanConvertingError(f"Unsupported Raman file type: {path.suffix or '(none)'}.")
    try:
        dataset = load_raman_data(path, input_mode="auto")
        source = baseline_input_from_mapping_dataset(dataset)
    except Exception as mapping_error:
        if path.suffix.lower() != ".txt":
            raise mapping_error
        source = read_raman_baseline_input(path)
        dataset = baseline_input_to_dataset(source, source_type="txt")
    return RamanConversionItem(display_name or path.name, dataset, source, path)


def item_from_baseline_result(
    source_item: RamanConversionItem,
    result: RamanBaselineBatchResult,
    display_name: str,
) -> RamanConversionItem:
    if len(result.results) != source_item.dataset.n_spectra:
        raise RamanConvertingError("Baseline result spectrum count does not match its source item.")
    matrix = np.column_stack([np.asarray(entry.corrected, dtype=float) for entry in result.results])
    dataset = RamanDataset(
        source_path=source_item.source_path,
        source_type=f"{source_item.dataset.source_type}_baselined",
        wavenumber=np.asarray(source_item.dataset.wavenumber, dtype=float).copy(),
        intensity_matrix=matrix,
        metadata={key: np.asarray(value).copy() for key, value in source_item.dataset.metadata.items()},
    )
    baseline_input = baseline_input_from_mapping_dataset(dataset)
    return RamanConversionItem(display_name, dataset, baseline_input, source_item.source_path, derived=True)


def unique_item_name(preferred: str, existing_names: Iterable[str]) -> str:
    existing = {str(name).casefold() for name in existing_names}
    path = Path(preferred)
    suffix = path.suffix or ".txt"
    stem = path.stem
    candidate = f"{stem}{suffix}"
    counter = 2
    while candidate.casefold() in existing:
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def export_conversion_item(item: RamanConversionItem, output_path: str | Path) -> Path:
    return export_origin_txt(
        item.dataset,
        output_path,
        include_averaged=False,
        include_normalised=False,
    )


def export_targets(items: Iterable[RamanConversionItem], output_dir: str | Path) -> list[Path]:
    output_dir = Path(output_dir)
    used: list[str] = []
    targets = []
    for item in items:
        name = unique_item_name(f"{item.export_stem}.txt", used)
        used.append(name)
        targets.append(output_dir / name)
    return targets
