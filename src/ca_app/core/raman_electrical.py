"""Electrical CSV processing for Raman electrical previews."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


SAMPLING_RATE_HZ = 100
DEFAULT_PREVIEW_SECONDS = 1.0
VOLTAGE_CONST_TOL = 1e-4

GATE_VOLTAGE_COL = "Gate Voltage"
GATE_CURRENT_COL = "Gate Current"
GATE_TIME_COL = "Gate Time"
DRAIN_VOLTAGE_COL = "Drain Voltage"
DRAIN_CURRENT_COL = "Drain Current"
DRAIN_TIME_COL = "Drain Time"

ELECTRICAL_COLUMNS = (
    GATE_TIME_COL,
    GATE_VOLTAGE_COL,
    GATE_CURRENT_COL,
    DRAIN_TIME_COL,
    DRAIN_VOLTAGE_COL,
    DRAIN_CURRENT_COL,
)


class RamanElectricalError(ValueError):
    pass


@dataclass(frozen=True)
class VoltageTraceInfo:
    status: str
    const_value_v: float | None
    n_pulse: int | None
    t_initial_s: float | None
    t_duration_s: float | None


@dataclass(frozen=True)
class RamanElectricalData:
    source_path: Path
    n_rows: int
    total_time_s: float
    columns: dict[str, np.ndarray]
    missing_columns: tuple[str, ...]

    def column(self, name: str) -> np.ndarray | None:
        return self.columns.get(name)


@dataclass(frozen=True)
class RamanElectricalSummary:
    data: RamanElectricalData
    vg: VoltageTraceInfo
    vd: VoltageTraceInfo


def load_electrical_csv(path: str | Path, sampling_rate_hz: float = SAMPLING_RATE_HZ) -> RamanElectricalData:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find Electrical CSV file: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise RamanElectricalError(f"No CSV header found in {path.name}.")
            rows = list(reader)
    except RamanElectricalError:
        raise
    except Exception as exc:
        raise RamanElectricalError(f"Could not read Electrical CSV file: {path}") from exc
    if not rows:
        raise RamanElectricalError(f"No Electrical data rows found in {path.name}.")

    columns: dict[str, np.ndarray] = {}
    fieldnames = set(reader.fieldnames or ())
    for name in ELECTRICAL_COLUMNS:
        if name in fieldnames:
            columns[name] = numeric_column(row.get(name, "") for row in rows)
    missing = tuple(name for name in ELECTRICAL_COLUMNS if name not in fieldnames)
    return RamanElectricalData(
        source_path=path,
        n_rows=len(rows),
        total_time_s=len(rows) / float(sampling_rate_hz),
        columns=columns,
        missing_columns=missing,
    )


def numeric_column(values: Iterable[object]) -> np.ndarray:
    parsed = []
    for value in values:
        try:
            parsed.append(float(str(value).strip()))
        except (TypeError, ValueError):
            parsed.append(np.nan)
    return np.asarray(parsed, dtype=float)


def most_common_voltage_level(values: np.ndarray, decimals: int = 5) -> float:
    clean = np.asarray(values, dtype=float)
    clean = clean[np.isfinite(clean)]
    if clean.size == 0:
        return float("nan")
    rounded = np.round(clean, decimals)
    levels, counts = np.unique(rounded, return_counts=True)
    return float(levels[np.argmax(counts)])


def find_true_segments(mask: np.ndarray) -> list[tuple[int, int]]:
    mask = np.asarray(mask, dtype=bool)
    if mask.size == 0:
        return []
    padded = np.r_[False, mask, False]
    changes = np.diff(padded.astype(int))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    return list(zip(starts, ends))


def classify_voltage_trace(
    time_values: np.ndarray | None,
    voltage_values: np.ndarray | None,
    const_tol: float = VOLTAGE_CONST_TOL,
    sampling_rate_hz: float = SAMPLING_RATE_HZ,
) -> VoltageTraceInfo:
    if time_values is None or voltage_values is None:
        return VoltageTraceInfo("missing", None, None, None, None)

    t = np.asarray(time_values, dtype=float)
    v = np.asarray(voltage_values, dtype=float)
    valid = np.isfinite(t) & np.isfinite(v)
    t = t[valid]
    v = v[valid]
    if v.size == 0:
        return VoltageTraceInfo("missing", None, None, None, None)

    v_range = float(np.max(v) - np.min(v))
    if v_range <= const_tol:
        return VoltageTraceInfo("const", float(np.median(v)), None, None, None)

    baseline = most_common_voltage_level(v, decimals=5)
    active_threshold = max(float(const_tol), 0.2 * v_range)
    active = np.abs(v - baseline) > active_threshold
    segments = [(start, end) for start, end in find_true_segments(active) if (end - start) >= 2]
    if not segments:
        return VoltageTraceInfo("changing", None, 0, None, None)

    dt = float(np.nanmedian(np.diff(t))) if t.size > 1 else 1.0 / float(sampling_rate_hz)
    starts = [float(t[start]) for start, _ in segments]
    durations = [float(t[end - 1] - t[start] + dt) for start, end in segments]
    return VoltageTraceInfo("pulse", None, len(segments), starts[0], float(np.median(durations)))


def summarize_electrical_data(data: RamanElectricalData) -> RamanElectricalSummary:
    vg = classify_voltage_trace(data.column(GATE_TIME_COL), data.column(GATE_VOLTAGE_COL))
    vd = classify_voltage_trace(data.column(DRAIN_TIME_COL), data.column(DRAIN_VOLTAGE_COL))
    return RamanElectricalSummary(data=data, vg=vg, vd=vd)


def format_summary_value(value: float | int | None) -> str:
    if value is None:
        return "-"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    if not np.isfinite(numeric):
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{numeric:.6g}"


def summary_table_rows(summary: RamanElectricalSummary) -> list[list[str]]:
    return [
        ["n_rows", str(summary.data.n_rows)],
        ["total time / s", f"{summary.data.total_time_s:.6g}"],
        [
            "V_Gate",
            summary.vg.status,
            format_summary_value(summary.vg.const_value_v),
            format_summary_value(summary.vg.n_pulse),
            format_summary_value(summary.vg.t_initial_s),
            format_summary_value(summary.vg.t_duration_s),
        ],
        [
            "V_Drain",
            summary.vd.status,
            format_summary_value(summary.vd.const_value_v),
            format_summary_value(summary.vd.n_pulse),
            format_summary_value(summary.vd.t_initial_s),
            format_summary_value(summary.vd.t_duration_s),
        ],
    ]
