"""AFM/KPFM CPD image analysis logic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import curve_fit


DEFAULT_HOPG_WORK_FUNCTION_EV = 4.6
DEFAULT_HISTOGRAM_BINS = 100


class AfmKpfmAnalysisError(ValueError):
    pass


@dataclass(frozen=True)
class KpfmImage:
    values: np.ndarray
    path: str
    source: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class MaskSet:
    labels: tuple[str, ...]
    masks: tuple[np.ndarray, ...]


@dataclass(frozen=True)
class Region:
    start_row: int
    end_row: int


def _candidate_shapes_from_1d_array(arr: np.ndarray, preview_size: tuple[int, int]) -> list[tuple[int, int]]:
    width, height = preview_size
    shapes = []
    if arr.size == width * height:
        shapes.append((height, width))
    side = int(round(np.sqrt(arr.size)))
    if side * side == arr.size:
        shape = (side, side)
        if shape not in shapes:
            shapes.append(shape)
    return shapes


def find_raw_float_image_in_tiff_tags(
    tags,
    preview_size: tuple[int, int],
    preferred_tag: int | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    candidates = []
    for tag_id, value in tags.items():
        if not isinstance(value, (bytes, bytearray)):
            continue
        for dtype in ("<f4", "<f8"):
            itemsize = np.dtype(dtype).itemsize
            if len(value) % itemsize != 0:
                continue
            arr = np.frombuffer(value, dtype=dtype)
            for shape in _candidate_shapes_from_1d_array(arr, preview_size):
                if np.prod(shape) < 4096:
                    continue
                arr2d = arr.reshape(shape).astype(float)
                finite = np.isfinite(arr2d)
                if finite.mean() < 0.99:
                    continue
                values = arr2d[finite]
                robust_min, robust_max = np.nanpercentile(values, [1, 99])
                if robust_max - robust_min <= 0:
                    continue
                if np.nanmax(np.abs(values)) > 1e6:
                    continue
                score = arr2d.size
                if dtype == "<f4":
                    score *= 2
                if preferred_tag is not None and int(tag_id) == int(preferred_tag):
                    score *= 10
                candidates.append(
                    {
                        "tag_id": int(tag_id),
                        "dtype": dtype,
                        "shape": shape,
                        "array": arr2d,
                        "score": score,
                        "min": float(np.nanmin(values)),
                        "max": float(np.nanmax(values)),
                        "mean": float(np.nanmean(values)),
                        "std": float(np.nanstd(values)),
                    }
                )
    if not candidates:
        raise AfmKpfmAnalysisError(
            "No image-sized raw float array was found in the TIFF tags. "
            "This file may be an exported preview only."
        )
    candidates = sorted(candidates, key=lambda item: item["score"], reverse=True)
    return candidates[0], candidates


def load_tiff_cpd(path: str | Path, preferred_tag: int | None = None) -> KpfmImage:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find CPD TIFF file: {path}")
    with Image.open(path) as img:
        selected, candidates = find_raw_float_image_in_tiff_tags(
            img.tag_v2,
            preview_size=img.size,
            preferred_tag=preferred_tag,
        )
    metadata = {key: value for key, value in selected.items() if key != "array"}
    metadata["candidate_count"] = len(candidates)
    metadata["flipped_vertical"] = True
    values = np.flipud(np.asarray(selected["array"], dtype=float))
    return KpfmImage(values, str(path), "tiff", metadata)


def load_png_cpd(path: str | Path, voltage_min: float, voltage_max: float) -> KpfmImage:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find CPD PNG file: {path}")
    voltage_min = float(voltage_min)
    voltage_max = float(voltage_max)
    if not np.isfinite(voltage_min) or not np.isfinite(voltage_max):
        raise AfmKpfmAnalysisError("PNG voltage min/max must be finite.")
    if voltage_min >= voltage_max:
        raise AfmKpfmAnalysisError("PNG voltage minimum must be less than maximum.")
    with Image.open(path) as img:
        raw = np.asarray(img.convert("I"), dtype=float)
    values = (raw / 65535.0) * (voltage_max - voltage_min) + voltage_min
    return KpfmImage(
        values,
        str(path),
        "png",
        {"min": float(np.nanmin(values)), "max": float(np.nanmax(values)), "shape": values.shape},
    )


def load_cpd_image(path: str | Path, voltage_min: float | None = None, voltage_max: float | None = None) -> KpfmImage:
    suffix = Path(path).suffix.lower()
    if suffix in {".tif", ".tiff"}:
        return load_tiff_cpd(path)
    if suffix == ".png":
        if voltage_min is None or voltage_max is None:
            raise AfmKpfmAnalysisError("PNG CPD loading requires voltage min and voltage max.")
        return load_png_cpd(path, voltage_min, voltage_max)
    raise AfmKpfmAnalysisError("Load a TIFF or PNG CPD image.")


def load_mask(path: str | Path, target_shape: tuple[int, int] | None = None) -> np.ndarray:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find mask file: {path}")
    with Image.open(path) as img:
        mask = np.asarray(img.convert("L"), dtype=np.uint8) > 127
    if target_shape is not None:
        mask = resize_mask_to_image(mask, target_shape)
    return mask


def resize_mask_to_image(mask: np.ndarray, target_shape: tuple[int, int]) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    if mask.shape == tuple(target_shape):
        return mask
    img = Image.fromarray((mask.astype(np.uint8) * 255))
    resized = img.resize((int(target_shape[1]), int(target_shape[0])), Image.Resampling.NEAREST)
    return np.asarray(resized, dtype=np.uint8) > 127


def build_one_mask_set(mask: np.ndarray, target_shape: tuple[int, int]) -> MaskSet:
    first = resize_mask_to_image(mask, target_shape)
    return MaskSet(("Mask", "Inverse"), (first, ~first))


def build_two_mask_set(upper_mask: np.ndarray, lower_mask: np.ndarray, target_shape: tuple[int, int]) -> MaskSet:
    upper = resize_mask_to_image(upper_mask, target_shape)
    lower = resize_mask_to_image(lower_mask, target_shape)
    middle = ~(upper | lower)
    return MaskSet(("Upper", "Middle", "Lower"), (upper, middle, lower))


def ordered_rows(values: np.ndarray, slow_scan_direction: str) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    direction = slow_scan_direction.lower()
    if direction == "up":
        return values[::-1, :]
    if direction == "down":
        return values
    raise AfmKpfmAnalysisError("Slow scan direction must be up or down.")


def average_per_processed_row(values: np.ndarray, slow_scan_direction: str = "down") -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return np.nanmean(ordered_rows(values, slow_scan_direction), axis=1)


def average_per_processed_row_with_masks(
    values: np.ndarray,
    masks: tuple[np.ndarray, ...] | list[np.ndarray],
    slow_scan_direction: str = "down",
) -> list[np.ndarray]:
    ordered_values = ordered_rows(values, slow_scan_direction)
    profiles = []
    for mask in masks:
        ordered_mask = ordered_rows(np.asarray(mask, dtype=bool), slow_scan_direction).astype(bool)
        with np.errstate(invalid="ignore"):
            profiles.append(np.nanmean(np.where(ordered_mask, ordered_values, np.nan), axis=1))
    return profiles


def x_values_for_rows(num_rows: int, mode: str = "row", scan_rate_hz: float | None = None, total_scan_time_s: float | None = None) -> np.ndarray:
    if num_rows <= 0:
        raise AfmKpfmAnalysisError("Number of rows must be greater than 0.")
    mode = mode.lower()
    if mode == "row":
        return np.arange(1, num_rows + 1, dtype=float)
    if mode != "time":
        raise AfmKpfmAnalysisError("X axis mode must be row or time.")
    if total_scan_time_s is not None:
        total = float(total_scan_time_s)
        if not np.isfinite(total) or total <= 0:
            raise AfmKpfmAnalysisError("Total scan time must be greater than 0.")
        return np.linspace(0.0, total, num_rows)
    rate = float(scan_rate_hz) if scan_rate_hz is not None else np.nan
    if not np.isfinite(rate) or rate <= 0:
        raise AfmKpfmAnalysisError("Scan rate must be greater than 0 Hz.")
    return np.arange(num_rows, dtype=float) * (2.0 / rate)


def cpd_to_energy(cpd_values: np.ndarray, hopg_work_function_ev: float, hopg_cpd_peak_v: float) -> np.ndarray:
    work_function = float(hopg_work_function_ev)
    hopg_peak = float(hopg_cpd_peak_v)
    if not np.isfinite(work_function) or not np.isfinite(hopg_peak):
        raise AfmKpfmAnalysisError("HOPG work function and CPD peak must be finite.")
    return work_function + hopg_peak - np.asarray(cpd_values, dtype=float)


def average_hopg_references(values: list[float] | tuple[float, ...]) -> float:
    refs = np.asarray(values, dtype=float)
    refs = refs[np.isfinite(refs)]
    if refs.size == 0:
        raise AfmKpfmAnalysisError("Enter or load at least one HOPG reference.")
    return float(np.mean(refs))


def histogram(values: np.ndarray, bins: int = DEFAULT_HISTOGRAM_BINS, value_range: tuple[float, float] | None = None):
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise AfmKpfmAnalysisError("No finite values are available for histogramming.")
    return np.histogram(finite, bins=int(bins), range=value_range)


def height_distribution_density(
    values: np.ndarray,
    bins: int = DEFAULT_HISTOGRAM_BINS,
    value_range: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise AfmKpfmAnalysisError("No finite values are available for histogramming.")
    density, edges = np.histogram(finite, bins=int(bins), range=value_range, density=True)
    centers = (edges[:-1] + edges[1:]) / 2.0
    return centers, density, edges


def gaussian_height_distribution(x, y0, a, x0, b):
    return y0 + a * np.exp(-((x - x0) ** 2) / (b**2))


def fit_gaussian_peak_from_values(values: np.ndarray, bins: int = DEFAULT_HISTOGRAM_BINS) -> tuple[float, dict[str, float]]:
    centers, density, edges = height_distribution_density(values, bins=bins)
    if density.size < 4 or np.nanmax(density) <= 0:
        raise AfmKpfmAnalysisError("Not enough histogram data for Gaussian fitting.")
    peak_index = int(np.nanargmax(density))
    y0 = float(np.nanmin(density))
    amplitude = float(np.nanmax(density) - y0)
    center0 = float(centers[peak_index])
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    b0 = float(max(np.nanstd(finite) * np.sqrt(2.0), np.diff(edges).mean()))
    try:
        params, _ = curve_fit(
            gaussian_height_distribution,
            centers,
            density.astype(float),
            p0=(y0, amplitude, center0, b0),
            maxfev=10000,
        )
    except Exception as exc:
        raise AfmKpfmAnalysisError("Gaussian HOPG histogram fit failed.") from exc
    y0, amplitude, center, b = [float(value) for value in params]
    if not np.isfinite(center):
        raise AfmKpfmAnalysisError("Gaussian HOPG histogram fit returned an invalid peak.")
    return center, {
        "y0": y0,
        "a": amplitude,
        "x0": center,
        "b": abs(b),
        "offset": y0,
        "amplitude": amplitude,
        "center": center,
        "sigma": abs(b) / np.sqrt(2.0),
    }


def validate_regions(regions: list[Region] | tuple[Region, ...], num_rows: int) -> list[Region]:
    validated = []
    for region in regions:
        start = int(region.start_row)
        end = int(region.end_row)
        if start > end:
            start, end = end, start
        if start < 1 or end > num_rows:
            raise AfmKpfmAnalysisError(f"Illuminated region {start}-{end} is outside row range 1-{num_rows}.")
        validated.append(Region(start, end))
    return sorted(validated, key=lambda item: item.start_row)


def first_dark_and_illuminated_regions(regions: list[Region] | tuple[Region, ...], num_rows: int) -> tuple[Region | None, Region | None]:
    validated = validate_regions(regions, num_rows)
    if not validated:
        return None, None
    first_light = validated[0]
    if first_light.start_row > 1:
        return Region(1, first_light.start_row - 1), first_light
    if first_light.end_row < num_rows:
        return Region(first_light.end_row + 1, num_rows), first_light
    return None, first_light


def processed_region_mask(region: Region, num_rows: int) -> np.ndarray:
    mask = np.zeros(num_rows, dtype=bool)
    start = max(1, int(region.start_row))
    end = min(num_rows, int(region.end_row))
    if start <= end:
        mask[start - 1 : end] = True
    return mask


def image_row_span_for_processed_region(region: Region, num_rows: int, slow_scan_direction: str) -> tuple[int, int]:
    direction = slow_scan_direction.lower()
    start = int(region.start_row)
    end = int(region.end_row)
    if direction == "down":
        return start - 1, end - 1
    if direction == "up":
        return num_rows - end, num_rows - start
    raise AfmKpfmAnalysisError("Slow scan direction must be up or down.")
