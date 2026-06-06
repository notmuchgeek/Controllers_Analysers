"""Raman in-situ electrochemistry sequence analysis."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from ca_app.core.raman_mapping import RamanDataset, load_raman_data


DEFAULT_TIME_OFFSET_S = 5.00
DEFAULT_TIME_PER_SEQUENCE_S = 2.09
DEFAULT_PEAK_WINDOWS = ((1371.0, 5.0), (1423.0, 6.0), (1516.0, 5.0), (1606.0, 5.0))
DEFAULT_WINDOW_PREVIEW_EVERY_N = 20
DEFAULT_RESULT_SPECTRA_EVERY_N = 10
DEFAULT_RAMAN_RANGE_MIN_CM1 = 1300.0
DEFAULT_RAMAN_RANGE_MAX_CM1 = 1700.0


class RamanInsituError(ValueError):
    pass


@dataclass(frozen=True)
class PeakWindow:
    center_cm1: float
    tolerance_cm1: float

    @property
    def low_cm1(self) -> float:
        return self.center_cm1 - self.tolerance_cm1

    @property
    def high_cm1(self) -> float:
        return self.center_cm1 + self.tolerance_cm1


@dataclass
class RamanSequenceData:
    sequence_code: np.ndarray
    raman_cm1: np.ndarray
    intensity: np.ndarray
    sequence_index: np.ndarray
    time_s: np.ndarray
    name: str = "no_name"
    sequence_source: str = "time"

    @property
    def sequence_values(self) -> np.ndarray:
        return np.unique(self.sequence_index)


@dataclass
class PeakSeries:
    window: PeakWindow
    sequence_index: np.ndarray
    sequence_code: np.ndarray
    time_s: np.ndarray
    peak_position_cm1: np.ndarray
    peak_intensity: np.ndarray


@dataclass
class RatioSeries:
    center_cm1: float
    normalized_center_cm1: float
    sequence_index: np.ndarray
    time_s: np.ndarray
    ratio: np.ndarray


@dataclass
class InsituAnalysisResult:
    data: RamanSequenceData
    windows: tuple[PeakWindow, ...]
    peak_series: list[PeakSeries]
    ratios: list[RatioSeries]
    normalized_peak_cm1: float


def _integer_sequence_indices(sequence_code: np.ndarray, label: str) -> np.ndarray:
    rounded = np.rint(np.asarray(sequence_code, dtype=float))
    if not np.allclose(sequence_code, rounded, rtol=0.0, atol=1e-6):
        raise RamanInsituError(f"{label} values must be integer sequence numbers.")
    return rounded.astype(int)


def load_raman_sequence(
    path: str | Path,
    time_offset_s: float = DEFAULT_TIME_OFFSET_S,
    time_per_sequence_s: float = DEFAULT_TIME_PER_SEQUENCE_S,
) -> RamanSequenceData:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find Raman sequence file: {path}")
    if path.suffix.lower() == ".wdf":
        return raman_dataset_to_sequence(load_raman_data(path, input_mode="wdf"), name=path.name)
    try:
        rows = np.genfromtxt(path, names=True, dtype=float, encoding="utf-8")
    except Exception as exc:
        raise RamanInsituError(f"Could not read Raman sequence file: {path}") from exc
    if rows.size == 0:
        raise RamanInsituError(f"No Raman sequence data found in {path}")
    rows = np.atleast_1d(rows)
    names = set(rows.dtype.names or ())
    sequence_field = "Time" if "Time" in names else ("Sequence" if "Sequence" in names else "")
    required = {sequence_field, "Wave", "Intensity"} if sequence_field else {"Time", "Wave", "Intensity"}
    missing = required.difference(names)
    if missing:
        raise RamanInsituError(f"Missing required columns: {sorted(missing)}")

    sequence_code = np.asarray(rows[sequence_field], dtype=float).ravel()
    raman_cm1 = np.asarray(rows["Wave"], dtype=float).ravel()
    intensity = np.asarray(rows["Intensity"], dtype=float).ravel()
    finite = np.isfinite(sequence_code) & np.isfinite(raman_cm1) & np.isfinite(intensity)
    sequence_code = sequence_code[finite]
    raman_cm1 = raman_cm1[finite]
    intensity = intensity[finite]
    if len(sequence_code) == 0:
        raise RamanInsituError(f"No finite Raman sequence data found in {path}")

    if sequence_field == "Time":
        sequence_order = np.sort(np.unique(sequence_code))
        seq_map = {code: index + 1 for index, code in enumerate(sequence_order)}
        sequence_index = np.asarray([seq_map[code] for code in sequence_code], dtype=int)
        time_s = float(time_offset_s) + sequence_index.astype(float) * float(time_per_sequence_s)
        sequence_source = "time"
    else:
        sequence_index = _integer_sequence_indices(sequence_code, "#Sequence")
        time_s = sequence_index.astype(float)
        sequence_source = "sequence"

    order = np.lexsort((raman_cm1, sequence_index))
    return RamanSequenceData(
        sequence_code=sequence_code[order],
        raman_cm1=raman_cm1[order],
        intensity=intensity[order],
        sequence_index=sequence_index[order],
        time_s=time_s[order],
        name=path.name,
        sequence_source=sequence_source,
    )


def raman_dataset_to_sequence(
    dataset: RamanDataset,
    selected_indices: Iterable[int] | None = None,
    name: str | None = None,
) -> RamanSequenceData:
    if selected_indices is None:
        selected_indices = range(dataset.n_spectra)
    selected_indices = [int(index) for index in selected_indices]
    if not selected_indices:
        raise RamanInsituError("No spectra were selected for Insitu EChem.")
    invalid = [index for index in selected_indices if index < 0 or index >= dataset.n_spectra]
    if invalid:
        raise RamanInsituError(f"Selected spectrum indexes out of range: {invalid}.")

    sequence_meta = np.asarray(dataset.metadata.get("Sequence", np.arange(1, dataset.n_spectra + 1)), dtype=float).ravel()
    sequence_index_meta = _integer_sequence_indices(sequence_meta, "Mapping sequence")
    sequence_code_values = []
    raman_values = []
    intensity_values = []
    sequence_index_values = []
    time_values = []
    for source_index in selected_indices:
        source_sequence = float(sequence_meta[source_index])
        source_sequence_index = int(sequence_index_meta[source_index])
        for wave, intensity in zip(dataset.wavenumber, dataset.intensity_matrix[:, source_index]):
            sequence_code_values.append(source_sequence)
            raman_values.append(float(wave))
            intensity_values.append(float(intensity))
            sequence_index_values.append(source_sequence_index)
            time_values.append(float(source_sequence_index))

    order = np.lexsort((np.asarray(raman_values), np.asarray(sequence_index_values)))
    return RamanSequenceData(
        sequence_code=np.asarray(sequence_code_values, dtype=float)[order],
        raman_cm1=np.asarray(raman_values, dtype=float)[order],
        intensity=np.asarray(intensity_values, dtype=float)[order],
        sequence_index=np.asarray(sequence_index_values, dtype=int)[order],
        time_s=np.asarray(time_values, dtype=float)[order],
        name=name or dataset.source_path.name,
        sequence_source="sequence",
    )




def filter_raman_range(data: RamanSequenceData, min_cm1: float, max_cm1: float) -> RamanSequenceData:
    min_cm1 = float(min_cm1)
    max_cm1 = float(max_cm1)
    if not np.isfinite(min_cm1) or not np.isfinite(max_cm1):
        raise RamanInsituError("Raman range values must be finite.")
    if min_cm1 >= max_cm1:
        raise RamanInsituError("Raman range minimum must be less than maximum.")
    mask = (data.raman_cm1 >= min_cm1) & (data.raman_cm1 <= max_cm1)
    if not np.any(mask):
        raise RamanInsituError(f"No Raman data points found in {min_cm1:.6g} to {max_cm1:.6g} cm^-1.")
    return RamanSequenceData(
        sequence_code=data.sequence_code[mask],
        raman_cm1=data.raman_cm1[mask],
        intensity=data.intensity[mask],
        sequence_index=data.sequence_index[mask],
        time_s=data.time_s[mask],
        name=data.name,
        sequence_source=data.sequence_source,
    )
def validate_peak_windows(windows: Iterable[PeakWindow]) -> tuple[PeakWindow, ...]:
    validated = []
    for window in windows:
        center = float(window.center_cm1)
        tolerance = float(window.tolerance_cm1)
        if not np.isfinite(center):
            raise RamanInsituError("Peak position must be finite.")
        if not np.isfinite(tolerance) or tolerance <= 0:
            raise RamanInsituError("Window size must be greater than 0.")
        validated.append(PeakWindow(center, tolerance))
    if not validated:
        raise RamanInsituError("At least one peak window is required.")
    return tuple(validated)


def extract_peak_in_window(data: RamanSequenceData, window: PeakWindow) -> PeakSeries:
    window = validate_peak_windows([window])[0]
    sequence_values = data.sequence_values
    positions = []
    intensities = []
    codes = []
    times = []
    found_any = False
    for seq in sequence_values:
        seq_mask = data.sequence_index == seq
        mask = seq_mask & (data.raman_cm1 >= window.low_cm1) & (data.raman_cm1 <= window.high_cm1)
        seq_codes = data.sequence_code[seq_mask]
        seq_times = data.time_s[seq_mask]
        codes.append(float(seq_codes[0]) if len(seq_codes) else np.nan)
        times.append(float(seq_times[0]) if len(seq_times) else np.nan)
        if not np.any(mask):
            positions.append(np.nan)
            intensities.append(np.nan)
            continue
        found_any = True
        indexes = np.where(mask)[0]
        local_index = indexes[int(np.nanargmax(data.intensity[indexes]))]
        positions.append(float(data.raman_cm1[local_index]))
        intensities.append(float(data.intensity[local_index]))
    if not found_any:
        raise RamanInsituError(
            f"No data points found in {window.low_cm1:.6g} to {window.high_cm1:.6g} cm^-1."
        )
    return PeakSeries(
        window=window,
        sequence_index=sequence_values.astype(int),
        sequence_code=np.asarray(codes, dtype=float),
        time_s=np.asarray(times, dtype=float),
        peak_position_cm1=np.asarray(positions, dtype=float),
        peak_intensity=np.asarray(intensities, dtype=float),
    )


def analyze_insitu_sequence(
    data: RamanSequenceData,
    windows: Iterable[PeakWindow],
    normalized_peak_cm1: float,
) -> InsituAnalysisResult:
    windows = validate_peak_windows(windows)
    peak_series = [extract_peak_in_window(data, window) for window in windows]
    normalized = find_normalized_peak(windows, normalized_peak_cm1)
    ratios = build_intensity_ratios(peak_series, normalized)
    return InsituAnalysisResult(
        data=data,
        windows=windows,
        peak_series=peak_series,
        ratios=ratios,
        normalized_peak_cm1=normalized,
    )


def find_normalized_peak(windows: tuple[PeakWindow, ...], requested_peak_cm1: float) -> float:
    centers = np.asarray([window.center_cm1 for window in windows], dtype=float)
    if len(centers) == 0:
        raise RamanInsituError("No peaks are available for normalization.")
    requested = float(requested_peak_cm1)
    index = int(np.argmin(np.abs(centers - requested)))
    return float(centers[index])


def build_intensity_ratios(peak_series: list[PeakSeries], normalized_peak_cm1: float) -> list[RatioSeries]:
    if not peak_series:
        raise RamanInsituError("No peak series are available for ratio calculation.")
    centers = np.asarray([series.window.center_cm1 for series in peak_series], dtype=float)
    normalized_index = int(np.argmin(np.abs(centers - float(normalized_peak_cm1))))
    denominator = peak_series[normalized_index].peak_intensity.astype(float)
    denominator = np.where(np.isclose(denominator, 0.0), np.nan, denominator)
    ratios = []
    for series in peak_series:
        if np.isclose(series.window.center_cm1, centers[normalized_index]):
            ratio = np.ones_like(denominator, dtype=float)
        else:
            ratio = series.peak_intensity / denominator
        ratios.append(
            RatioSeries(
                center_cm1=series.window.center_cm1,
                normalized_center_cm1=float(centers[normalized_index]),
                sequence_index=series.sequence_index,
                time_s=series.time_s,
                ratio=ratio,
            )
        )
    return ratios


def selected_sequence_values(data: RamanSequenceData, every_n: int) -> np.ndarray:
    every_n = max(int(every_n), 1)
    return data.sequence_values[::every_n]


def x_values_for_mode(series: PeakSeries | RatioSeries, x_mode: str) -> np.ndarray:
    if x_mode == "time":
        return series.time_s
    return series.sequence_index


def x_label_for_mode(x_mode: str) -> str:
    if x_mode == "time":
        return "Time (s)"
    return "Sequence"


def legend_title_for_mode(x_mode: str) -> str:
    if x_mode == "time":
        return "Time"
    return "Sequence"


def format_peak_label(value: float) -> str:
    return f"{float(value):g}"


def save_peak_summary_csv(result: InsituAnalysisResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = peak_summary_rows(result)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def save_ratio_csv(result: InsituAnalysisResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ratio_rows(result)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def peak_summary_rows(result: InsituAnalysisResult) -> list[dict[str, float]]:
    if not result.peak_series:
        raise RamanInsituError("No peak data to save.")
    base = result.peak_series[0]
    rows = []
    for index in range(len(base.sequence_index)):
        row = {
            "sequence_index": int(base.sequence_index[index]),
            "sequence_code": float(base.sequence_code[index]),
            "time_s": float(base.time_s[index]),
        }
        for series in result.peak_series:
            label = format_peak_label(series.window.center_cm1)
            row[f"peak{label}_position_cm1"] = float(series.peak_position_cm1[index])
            row[f"peak{label}_intensity"] = float(series.peak_intensity[index])
        rows.append(row)
    return rows


def ratio_rows(result: InsituAnalysisResult) -> list[dict[str, float]]:
    if not result.ratios:
        raise RamanInsituError("No ratio data to save.")
    base = result.ratios[0]
    rows = []
    for index in range(len(base.sequence_index)):
        row = {
            "sequence_index": int(base.sequence_index[index]),
            "time_s": float(base.time_s[index]),
        }
        for ratio in result.ratios:
            label = format_peak_label(ratio.center_cm1)
            norm_label = format_peak_label(ratio.normalized_center_cm1)
            row[f"ratio_{label}_to_{norm_label}"] = float(ratio.ratio[index])
        rows.append(row)
    return rows


