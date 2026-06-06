"""Raman WiRE mapping and sequence file utilities."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


class RamanMappingError(ValueError):
    pass


@dataclass(frozen=True)
class RamanDataset:
    source_path: Path
    source_type: str
    wavenumber: np.ndarray
    intensity_matrix: np.ndarray
    metadata: dict[str, np.ndarray]
    image_bytes: bytes | None = None
    image_origins: np.ndarray | None = None
    image_dimensions: np.ndarray | None = None
    image_cropbox: tuple[int, int, int, int] | None = None

    @property
    def n_points(self) -> int:
        return int(self.intensity_matrix.shape[0])

    @property
    def n_spectra(self) -> int:
        return int(self.intensity_matrix.shape[1])

    @property
    def intensity_columns(self) -> list[str]:
        width = max(2, len(str(self.n_spectra)))
        return [f"Intensity_{index:0{width}d}" for index in range(1, self.n_spectra + 1)]


def _base_name(name: object) -> str:
    return str(name).strip().lstrip("#").strip().lower()


def _find_name(names: Iterable[str], target: str) -> str | None:
    target = target.lower()
    for name in names:
        if _base_name(name) == target:
            return name
    return None


def infer_rows_per_spectrum(wavenumber_values: np.ndarray, atol: float = 1e-5) -> int:
    waves = np.asarray(wavenumber_values, dtype=float).ravel()
    if waves.size == 0:
        raise RamanMappingError("No wavenumber values found.")
    repeats = np.where(np.isclose(waves, waves[0], rtol=0.0, atol=atol))[0]
    if repeats.size >= 2:
        return int(repeats[1] - repeats[0])
    return int(np.unique(waves).size)


def read_wire_txt(path: str | Path, rows_per_spectrum: int | None = None) -> RamanDataset:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find Raman TXT file: {path}")
    try:
        rows = np.genfromtxt(path, names=True, dtype=float, encoding="utf-8")
    except Exception as exc:
        raise RamanMappingError(f"Could not read Raman TXT file: {path}") from exc
    if rows.size == 0:
        raise RamanMappingError(f"No Raman data found in {path}")
    rows = np.atleast_1d(rows)
    names = list(rows.dtype.names or ())
    wave_name = _find_name(names, "wave")
    intensity_name = _find_name(names, "intensity")
    if wave_name is None or intensity_name is None:
        raise RamanMappingError(f"Cannot find Wave and Intensity columns in {path.name}.")

    waves_flat = np.asarray(rows[wave_name], dtype=float).ravel()
    intensity_flat = np.asarray(rows[intensity_name], dtype=float).ravel()
    finite = np.isfinite(waves_flat) & np.isfinite(intensity_flat)
    waves_flat = waves_flat[finite]
    intensity_flat = intensity_flat[finite]
    if rows_per_spectrum is None:
        rows_per_spectrum = infer_rows_per_spectrum(waves_flat)
    rows_per_spectrum = int(rows_per_spectrum)
    if rows_per_spectrum <= 0:
        raise RamanMappingError("rows_per_spectrum must be greater than 0.")
    if waves_flat.size % rows_per_spectrum != 0:
        raise RamanMappingError(
            f"Row count {waves_flat.size} is not divisible by rows_per_spectrum={rows_per_spectrum}."
        )

    n_spectra = waves_flat.size // rows_per_spectrum
    waves = waves_flat.reshape(n_spectra, rows_per_spectrum)
    intensities = intensity_flat.reshape(n_spectra, rows_per_spectrum)
    first_wave = waves[0]
    if not np.allclose(waves, first_wave, rtol=0.0, atol=1e-4):
        raise RamanMappingError("The Raman-shift axis is not identical across all spectra.")

    first_row_indexes = np.arange(0, rows.size, rows_per_spectrum, dtype=int)
    metadata: dict[str, np.ndarray] = {"Sequence": np.arange(1, n_spectra + 1, dtype=int)}
    source_type = "txt_sequence"
    for source_name, out_name in [("x", "X"), ("y", "Y"), ("z", "Z"), ("time", "Time"), ("sequence", "Sequence")]:
        column_name = _find_name(names, source_name)
        if column_name is not None:
            values = np.asarray(rows[column_name], dtype=float).ravel()[first_row_indexes]
            metadata[out_name] = values
    if "X" in metadata and "Y" in metadata:
        source_type = "txt_map"

    return RamanDataset(
        source_path=path,
        source_type=source_type,
        wavenumber=first_wave,
        intensity_matrix=intensities.T,
        metadata=metadata,
    )


def read_wire_wdf(path: str | Path) -> RamanDataset:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find Raman WDF file: {path}")
    try:
        from renishawWiRE import WDFReader
    except ImportError as exc:
        raise RamanMappingError(
            "renishawWiRE is required for .wdf files. Install it with: pip install renishawWiRE"
        ) from exc

    reader = WDFReader(path)
    try:
        wave = np.asarray(reader.xdata, dtype=float)
        spectra = np.asarray(reader.spectra, dtype=float)
        if spectra.ndim == 1:
            intensity_matrix = spectra.reshape(-1, 1)
        elif spectra.shape[-1] == wave.size:
            intensity_matrix = spectra.reshape(-1, wave.size).T
        elif spectra.shape[0] == wave.size:
            intensity_matrix = spectra.reshape(wave.size, -1)
        else:
            raise RamanMappingError(f"Unexpected WDF spectra shape {spectra.shape} for wavenumber size {wave.size}.")

        n_spectra = int(intensity_matrix.shape[1])
        metadata: dict[str, np.ndarray] = {"Sequence": np.arange(1, n_spectra + 1, dtype=int)}
        for attr, out_name in [("xpos", "X"), ("ypos", "Y"), ("zpos", "Z")]:
            try:
                values = np.asarray(getattr(reader, attr), dtype=float).ravel()
            except Exception:
                continue
            if values.size == n_spectra and (out_name == "Z" or not np.allclose(values, 0.0)):
                metadata[out_name] = values

        image_bytes = None
        image_origins = None
        image_dimensions = None
        image_cropbox = None
        try:
            reader.img.seek(0)
            image_bytes = bytes(reader.img.read())
            image_origins = np.asarray(reader.img_origins, dtype=float)
            image_dimensions = np.asarray(reader.img_dimensions, dtype=float)
            image_cropbox = tuple(int(v) for v in reader.img_cropbox)
        except Exception:
            pass
    finally:
        try:
            reader.close()
        except Exception:
            pass

    return RamanDataset(
        source_path=path,
        source_type="wdf",
        wavenumber=wave,
        intensity_matrix=intensity_matrix,
        metadata=metadata,
        image_bytes=image_bytes,
        image_origins=image_origins,
        image_dimensions=image_dimensions,
        image_cropbox=image_cropbox,
    )


def load_raman_data(
    path: str | Path,
    input_mode: str = "auto",
    rows_per_spectrum: int | None = None,
) -> RamanDataset:
    path = Path(path)
    mode = input_mode.lower().strip()
    if mode == "auto":
        mode = "wdf" if path.suffix.lower() == ".wdf" else "txt"
    if mode == "txt":
        return read_wire_txt(path, rows_per_spectrum=rows_per_spectrum)
    if mode == "wdf":
        return read_wire_wdf(path)
    raise RamanMappingError("input_mode must be 'txt', 'wdf', or 'auto'.")


def build_unstacked_table(dataset: RamanDataset) -> tuple[list[str], list[list[float]]]:
    headers = ["Wavenumber"] + dataset.intensity_columns + ["Averaged Intensity", "Normalised Intensity"]
    intensities = np.asarray(dataset.intensity_matrix, dtype=float)
    average = np.nanmean(intensities, axis=1)
    denom = float(np.nanmax(average) - np.nanmin(average)) if average.size else 0.0
    normalised = np.zeros_like(average) if np.isclose(denom, 0.0) else (average - np.nanmin(average)) / denom
    rows = []
    for row_index, wave in enumerate(dataset.wavenumber):
        rows.append(
            [float(wave)]
            + [float(value) for value in intensities[row_index, :]]
            + [float(average[row_index]), float(normalised[row_index])]
        )
    return headers, rows


def export_origin_txt(dataset: RamanDataset, output_file: str | Path) -> Path:
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    headers, rows = build_unstacked_table(dataset)
    long_names = (
        ["Wavenumber"]
        + [f"Intensity {index}" for index in range(1, dataset.n_spectra + 1)]
        + ["Averaged Intensity", "Normalised Intensity"]
    )
    units = ["cm^(-1)"] + ["a.u."] * dataset.n_spectra + ["a.u.", "a.u."]
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(long_names)
        writer.writerow(units)
        writer.writerows([f"{value:.6f}" for value in row] for row in rows)
    return output_file


def _parse_selected_token(token: str) -> list[int]:
    if "-" not in token:
        try:
            return [int(token)]
        except ValueError as exc:
            raise RamanMappingError(f"Invalid selected spectrum: {token!r}.") from exc

    parts = token.split("-")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise RamanMappingError(f"Invalid selected spectrum range: {token!r}.")
    try:
        start = int(parts[0].strip())
        stop = int(parts[1].strip())
    except ValueError as exc:
        raise RamanMappingError(f"Invalid selected spectrum range: {token!r}.") from exc
    if stop < start:
        raise RamanMappingError(f"Selected spectrum range must ascend: {token!r}.")
    return list(range(start, stop + 1))


def parse_selected_spectra(selected: str | Iterable[int], n_spectra: int) -> list[int]:
    if isinstance(selected, str):
        values: list[int] = []
        for item in selected.replace(";", ",").split(","):
            token = item.strip()
            if token:
                values.extend(_parse_selected_token(token))
    else:
        values = [int(item) for item in selected]
    if not values:
        raise RamanMappingError("No spectra were selected.")
    invalid = [value for value in values if value < 1 or value > n_spectra]
    if invalid:
        raise RamanMappingError(f"Selected spectra out of range: {invalid}. Valid range is 1 to {n_spectra}.")
    return [value - 1 for value in values]


def export_selected_sequence_txt(
    dataset: RamanDataset,
    selected: str | Iterable[int],
    output_file: str | Path,
    sequence_number_format: str = "float6",
) -> Path:
    indices = parse_selected_spectra(selected, dataset.n_spectra)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        handle.write("#Sequence\t\t#Wave\t\t#Intensity\n")
        for index in indices:
            seq = int(np.asarray(dataset.metadata["Sequence"]).ravel()[index])
            seq_text = f"{seq:.6f}" if sequence_number_format == "float6" else str(seq)
            for wave, intensity in zip(dataset.wavenumber, dataset.intensity_matrix[:, index]):
                handle.write(f"{seq_text}\t{float(wave):.6f}\t{float(intensity):.6f}\n")
    return output_file


def image_from_dataset(dataset: RamanDataset):
    if dataset.image_bytes is None:
        return None
    try:
        from PIL import Image
    except ImportError as exc:
        raise RamanMappingError("Pillow is required to read embedded WDF images.") from exc
    return Image.open(io.BytesIO(dataset.image_bytes))
