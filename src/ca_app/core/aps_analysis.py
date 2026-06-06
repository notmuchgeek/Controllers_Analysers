"""APS and workfunction analysis logic for KP Technology APS04 data."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
import re

import numpy as np
from scipy.optimize import shgo
from scipy.signal import savgol_filter
from scipy.special import erf


@dataclass
class ApsFitSettings:
    fit_lower_bound: float = 1.5
    fit_upper_bound: float = 6.5
    points: int = 7
    sqrt: bool = False
    fit_domain: str = "signal"


@dataclass
class DwfSettings:
    ref_aps_fit_lower_bound: float = 15.0
    ref_aps_fit_upper_bound: float = 35.0
    ref_aps_fit_points: int = 10
    ref_dwf_stat_length_s: float = 50.0
    sample_dwf_stat_length_s: float = 200.0
    ref_aps_fit_domain: str = "signal"


@dataclass
class DosSmoothSettings:
    window_length: int = 7
    polyorder: int = 3
    scale: float = 4.122623
    y0: float = 0.1


@dataclass
class SpvSettings:
    timemap: tuple[float, ...] = (20.0, 100.0, 150.0, 100.0, 150.0)
    normalize_zone: int = 1


def build_spv_timemap(initial_dark_s: float, light_s: float, dark_s: float, repeats: int) -> tuple[float, ...]:
    values = (float(initial_dark_s), float(light_s), float(dark_s))
    if any(value <= 0 for value in values):
        raise ApsAnalysisError("SPV timing values must be greater than 0 s.")
    if isinstance(repeats, bool) or not isinstance(repeats, int):
        raise ApsAnalysisError("SPV repeats must be a positive integer.")
    if repeats <= 0:
        raise ApsAnalysisError("SPV repeats must be a positive integer.")
    timemap = [float(initial_dark_s)]
    for _ in range(repeats):
        timemap.extend([float(light_s), float(dark_s)])
    return tuple(timemap)


@dataclass
class ApsDatMetadata:
    values: dict[str, str]

    @property
    def has_fit_window(self) -> bool:
        return self.e_low_ev is not None and self.e_high_ev is not None

    @property
    def e_low_ev(self) -> float | None:
        return self._mev_value("ELo")

    @property
    def e_high_ev(self) -> float | None:
        return self._mev_value("EHi")

    @property
    def e_thresh_ev(self) -> float | None:
        return self._mev_value("EThresh")

    @property
    def wf_ev(self) -> float | None:
        return self._mev_value("WF")

    @property
    def r2(self) -> float | None:
        return self._float_value("R2")

    @property
    def power(self) -> str | None:
        return self.values.get("Power")

    @property
    def suggested_sqrt(self) -> bool | None:
        if self.power == "1/2":
            return True
        if self.power == "1/3":
            return False
        return None

    def _mev_value(self, key: str) -> float | None:
        value = self._float_value(key)
        if value is None:
            return None
        return value / 1000.0

    def _float_value(self, key: str) -> float | None:
        try:
            return float(self.values[key])
        except (KeyError, TypeError, ValueError):
            return None


@dataclass
class ApsAnalysisResult:
    data: list["ApsData"]


@dataclass
class WorkfunctionAnalysisResult:
    dwf_data: list["DwfData"]
    ref_aps: "ApsData"
    ref_dwf: "DwfData"
    tip_dwf: float


@dataclass
class SpvAnalysisResult:
    data: list["SpvData"]


class ApsAnalysisError(ValueError):
    pass


def dwf_preview_percent_from_slider(value: int) -> float:
    """Map a 0-100 slider to last-X-percent preview range with fine control below 30%."""
    clamped = min(max(int(value), 0), 100)
    if clamped <= 70:
        return 1.0 + (29.0 * clamped / 70.0)
    return 30.0 + (70.0 * (clamped - 70) / 30.0)


class ApsData:
    def __init__(
        self,
        energy: Sequence[float],
        pes_raw: Sequence[float],
        sqrt: bool = False,
        name: str = "no_name",
        metadata: ApsDatMetadata | None = None,
    ):
        self.energy = np.asarray(energy, dtype=float)
        self.pes_raw = np.asarray(pes_raw, dtype=float)
        self.sqrt = bool(sqrt)
        self.name = name
        self.metadata = metadata
        self._dos = self.dos_raw

    @property
    def has_baseline(self) -> bool:
        return hasattr(self, "baseline")

    @property
    def is_analyzed(self) -> bool:
        return hasattr(self, "homo")

    @property
    def has_cutoff(self) -> bool:
        return hasattr(self, "cutoff_energy")

    @property
    def pes(self) -> np.ndarray:
        if self.has_baseline:
            return self.pes_raw - self.baseline
        return self.pes_raw

    @property
    def pes_base(self) -> np.ndarray:
        if not self.has_baseline:
            self.find_baseline()
        return self.pes_raw - self.baseline

    @property
    def dos_raw(self) -> np.ndarray:
        return np.gradient(self.pes, self.energy)

    @property
    def dos(self) -> np.ndarray:
        return self._dos

    @property
    def smooth_dos_values(self) -> np.ndarray:
        return self._dos

    def find_baseline(self, baseline_bounds: tuple[float, float] = (1.0, 10.0)) -> float:
        result = shgo(lambda x: -mofun(x, 0.3, self.pes_raw), [baseline_bounds], iters=2)
        if len(result.x) == 0:
            raise ApsAnalysisError(f"Could not find baseline for {self.name}.")
        baseline = float(result.x[0])
        lower, upper = baseline_bounds
        if np.isclose(baseline, lower) or np.isclose(baseline, upper):
            raise ApsAnalysisError(
                f"Found baseline is on the boundary ({baseline:.6g}) for {self.name}. "
                "Use better baseline bounds or inspect the data."
            )
        self.baseline = baseline
        return baseline

    def find_cutoff(self) -> tuple[int, float]:
        try:
            index = next(len(self.pes_base) - i for i, value in enumerate(self.pes_base[::-1]) if value < 0)
        except StopIteration as exc:
            raise ApsAnalysisError(f"Baseline was not correct for {self.name}; cutoff could not be found.") from exc
        self.cutoff_index = index
        self.cutoff_energy = float(self.energy[index])
        return index, self.cutoff_energy

    def analyze(self, fit_lower_bound: float = 0.5, fit_upper_bound: float = np.inf, points: int = 7) -> None:
        if points <= 2:
            raise ApsAnalysisError("Linear fit must contain more than 2 points.")
        start, stop = self._signal_fit_indexes(fit_lower_bound, fit_upper_bound)
        self._analyze_index_window(start, stop, points, "signal", fit_lower_bound, fit_upper_bound)

    def _signal_fit_indexes(self, fit_lower_bound: float, fit_upper_bound: float) -> tuple[int, int]:
        try:
            start = len(self.energy) - next(i for i, value in enumerate(self.pes_base[::-1]) if value < fit_lower_bound) - 1
        except StopIteration:
            start = 0
        try:
            stop = len(self.energy) - next(i for i, value in enumerate(self.pes_base[::-1]) if value < fit_upper_bound)
        except StopIteration:
            stop = len(self.energy)
        return start, stop

    def analyze_energy_window(self, energy_lower_bound: float, energy_upper_bound: float, points: int = 7) -> None:
        if points <= 2:
            raise ApsAnalysisError("Linear fit must contain more than 2 points.")
        lower = min(float(energy_lower_bound), float(energy_upper_bound))
        upper = max(float(energy_lower_bound), float(energy_upper_bound))
        indexes = np.where((self.energy >= lower) & (self.energy <= upper))[0]
        if len(indexes) <= points:
            raise ApsAnalysisError(f"Energy fitting window is too narrow for {self.name}.")
        self._analyze_index_window(int(indexes[0]), int(indexes[-1]) + 1, points, "energy", lower, upper)

    def _analyze_index_window(self, start: int, stop: int, points: int, fit_domain: str, fit_lower_bound: float, fit_upper_bound: float) -> None:
        self.fit_domain = fit_domain
        self.fit_lower_bound = float(fit_lower_bound)
        self.fit_upper_bound = float(fit_upper_bound)
        self.fit_candidate_start_index = int(start)
        self.fit_candidate_stop_index = int(stop)
        self.std_homo = np.inf
        for i in range(start, stop):
            for j in range(i + points, stop):
                x = self.energy[i:j]
                y = self.pes_base[i:j]
                fit = np.polyfit(x, y, 1)
                if np.isclose(fit[0], 0.0):
                    continue
                x_intercept = -fit[1] / fit[0]
                sig_square = ((np.polyval(fit, x) - y) ** 2).sum() / (j - i - 2)
                design = np.concatenate(([x - x_intercept], [np.repeat(-fit[0], j - i)]), 0)
                try:
                    [[_, _], [_, var_homo]] = np.linalg.inv(design.dot(design.T)) * sig_square
                except np.linalg.LinAlgError:
                    continue
                std_homo = var_homo**0.5
                if std_homo < self.std_homo:
                    self.lin_start_index = i
                    self.lin_stop_index = j
                    self.lin_par = fit
                    self.std_homo = std_homo
                    self.homo = float(x_intercept)
        if self.std_homo == np.inf:
            raise ApsAnalysisError(f"Fitting failed for {self.name}. Rechoose fitting conditions.")

    def smooth_dos(self, settings: DosSmoothSettings) -> None:
        if settings.window_length <= settings.polyorder:
            raise ApsAnalysisError("DOS smoothing window length must be greater than polynomial order.")
        if settings.window_length % 2 == 0:
            raise ApsAnalysisError("DOS smoothing window length must be odd.")
        if settings.window_length > len(self.energy):
            raise ApsAnalysisError(f"DOS smoothing window is longer than data length for {self.name}.")
        if not self.has_cutoff:
            self.find_cutoff()
        cutoff = self.cutoff_energy + 0.053547
        self._dos = self.dos_raw * erfsmooth(self.energy, settings.scale, cutoff, settings.y0)
        self._dos = savgol_filter(self._dos, settings.window_length, settings.polyorder)


class DwfData:
    def __init__(self, time: Sequence[float], cpd_data: Sequence[float], name: str = "no_name"):
        self.time = np.asarray(time, dtype=float)
        self.cpd_data = np.asarray(cpd_data, dtype=float)
        self.name = name
        self.data_type = "CPD"
        self.data_unit = "meV"
        self.calibrated = False

    @property
    def has_statistics(self) -> bool:
        return hasattr(self, "average_cpd")

    def calculate_statistics(self, length_s: float = 200.0) -> None:
        if length_s <= 0:
            raise ApsAnalysisError("DWF statistic length must be greater than 0 s.")
        try:
            start = next(i - 1 for i, value in enumerate(self.time) if value > self.time[-1] - length_s)
        except StopIteration as exc:
            raise ApsAnalysisError("DWF statistic length is larger than data length.") from exc
        self.stat_start_index = max(start, 0)
        self.stat_length_s = length_s
        self.average_cpd = float(np.average(self.cpd_data[self.stat_start_index :]))
        self.std_cpd = float(np.std(self.cpd_data[self.stat_start_index :]))


class SpvData(DwfData):
    def __init__(self, time: Sequence[float], cpd_data: Sequence[float], name: str = "no_name", timemap: Sequence[float] = (20, 100, 150, 100, 150)):
        super().__init__(time, cpd_data, name=name)
        self.timemap = tuple(float(value) for value in timemap)
        self.timeline = np.cumsum(self.timemap)
        self.timeline_index = self._build_timeline_index()
        self.data_type = "raw SPV"
        self.data_unit = "meV"

    @property
    def bg_calibrated(self) -> bool:
        return hasattr(self, "bg_cpd")

    @property
    def is_normalized(self) -> bool:
        return hasattr(self, "norm_spv")

    def _build_timeline_index(self) -> list[int]:
        if len(self.timemap) < 2:
            raise ApsAnalysisError("SPV timemap must contain at least one dark and one light segment.")
        if any(value <= 0 for value in self.timemap):
            raise ApsAnalysisError("SPV timemap values must be greater than 0 s.")
        indexes = []
        for boundary in self.timeline[:-1]:
            try:
                index = next(pos - 1 for pos, value in enumerate(self.time) if value > boundary)
            except StopIteration as exc:
                raise ApsAnalysisError(f"SPV timemap boundary {boundary:g} s is outside the loaded data range for {self.name}.") from exc
            indexes.append(max(index, 0))
        return [0, *indexes, len(self.time) - 1]

    def light_spans(self) -> list[tuple[float, float]]:
        return [(float(self.timeline[2 * index]), float(self.timeline[2 * index + 1])) for index in range(len(self.timeline) // 2)]

    def calibrate_background(self) -> None:
        if len(self.timeline_index) < 2 or self.timeline_index[1] <= self.timeline_index[0]:
            raise ApsAnalysisError(f"SPV background interval is empty for {self.name}.")
        self.bg_cpd = float(np.average(self.cpd_data[self.timeline_index[0] : self.timeline_index[1]]))
        self.cpd_data = self.cpd_data - self.bg_cpd
        self.data_type = "SPV"

    def normalize(self, zone: int = 1) -> None:
        if not self.bg_calibrated:
            self.calibrate_background()
        if zone < 0 or zone >= len(self.timeline_index) - 1:
            raise ApsAnalysisError(f"SPV normalization zone {zone} is outside the timemap for {self.name}.")
        segment = self.cpd_data[self.timeline_index[zone] : self.timeline_index[zone + 1]]
        if len(segment) == 0:
            raise ApsAnalysisError(f"SPV normalization zone {zone} is empty for {self.name}.")
        scale = float(np.max(np.abs(segment)))
        if np.isclose(scale, 0.0):
            raise ApsAnalysisError(f"SPV normalization zone {zone} has zero amplitude for {self.name}.")
        self.norm_zone = zone
        self.norm_spv = self.cpd_data / scale


def import_aps_files(paths: Iterable[str], sqrt: bool | None = False) -> list[ApsData]:
    data = []
    for path in paths:
        rows = _read_csv_rows(path)
        metadata = parse_aps_dat_metadata(rows)
        sqrt_type = metadata.suggested_sqrt if sqrt is None and metadata is not None and metadata.suggested_sqrt is not None else bool(sqrt)
        body = rows[1:]
        stop_index = len(body)
        for index, row in enumerate(body):
            try:
                if "WF" not in row[0] and float(row[3]) < 1e4:
                    continue
                stop_index = index
                break
            except (IndexError, ValueError) as exc:
                raise ApsAnalysisError(f"{path} does not have the expected APS04 format.") from exc
        save_index = (2, 6) if sqrt_type else (2, 7)
        values = []
        for row in body[:stop_index]:
            try:
                values.append((float(row[save_index[0]]), float(row[save_index[1]])))
            except (IndexError, ValueError) as exc:
                raise ApsAnalysisError(f"{path} does not contain numeric APS columns {save_index}.") from exc
        if not values:
            raise ApsAnalysisError(f"No APS data found in {path}.")
        array = np.asarray(values, dtype=float)
        data.append(ApsData(array[:, 0], array[:, 1], sqrt=sqrt_type, name=_full_file_name(path), metadata=metadata))
    return data


def import_dwf_files(paths: Iterable[str]) -> list[DwfData]:
    data = []
    for path in paths:
        rows = _read_csv_rows(path)
        if not rows:
            raise ApsAnalysisError(f"No data found in {path}.")
        header = rows[0]
        try:
            time_index = header.index("Time(Secs)")
            wf_index = header.index("WF (mV)")
        except ValueError as exc:
            raise ApsAnalysisError(f"{path} must contain Time(Secs) and WF (mV) columns.") from exc
        values = []
        for row in rows[1:]:
            if len(row) == 1:
                break
            try:
                values.append((float(row[time_index]), float(row[wf_index])))
            except (IndexError, ValueError) as exc:
                raise ApsAnalysisError(f"{path} contains invalid DWF numeric data.") from exc
        if not values:
            raise ApsAnalysisError(f"No DWF data found in {path}.")
        array = np.asarray(values, dtype=float)
        data.append(DwfData(array[:, 0], array[:, 1], name=_full_file_name(path)))
    return data


def import_spv_files(paths: Iterable[str], settings: SpvSettings) -> list[SpvData]:
    data = []
    for item in import_dwf_files(paths):
        data.append(SpvData(item.time, item.cpd_data, name=item.name, timemap=settings.timemap))
    return data


def analyze_aps_files(paths: Sequence[str], settings: ApsFitSettings, dos_settings: DosSmoothSettings) -> ApsAnalysisResult:
    if not paths:
        raise ApsAnalysisError("Load at least one APS file before analysis.")
    data = import_aps_files(paths, sqrt=None if settings.fit_domain in ("energy", "metadata") else settings.sqrt)
    for item in data:
        analyze_with_settings(item, settings)
        item.smooth_dos(dos_settings)
    return ApsAnalysisResult(data=data)


def analyze_spv_files(paths: Sequence[str], settings: SpvSettings) -> SpvAnalysisResult:
    if not paths:
        raise ApsAnalysisError("Load at least one SPV file before analysis.")
    data = import_spv_files(paths, settings)
    for item in data:
        item.calibrate_background()
        item.normalize(settings.normalize_zone)
    return SpvAnalysisResult(data=data)


def analyze_workfunction(
    dwf_paths: Sequence[str],
    ref_aps_path: str,
    ref_dwf_path: str,
    settings: DwfSettings,
) -> WorkfunctionAnalysisResult:
    if not dwf_paths:
        raise ApsAnalysisError("Load at least one DWF file before workfunction analysis.")
    if not ref_aps_path:
        raise ApsAnalysisError("Load one reference APS file before workfunction analysis.")
    if not ref_dwf_path:
        raise ApsAnalysisError("Load one reference DWF file before workfunction analysis.")

    dwf_data = import_dwf_files(dwf_paths)
    [ref_aps] = import_aps_files([ref_aps_path], sqrt=True)
    [ref_dwf] = import_dwf_files([ref_dwf_path])
    analyze_workfunction_ref_aps(ref_aps, settings)
    ref_dwf.calculate_statistics(settings.ref_dwf_stat_length_s)
    tip_dwf = -ref_aps.homo + ref_dwf.average_cpd / 1000.0

    for item in dwf_data:
        item.cpd_data = -item.cpd_data / 1000.0 + tip_dwf
        item.data_type = "Fermi level"
        item.data_unit = "eV"
        item.calibrated = True
        item.ref_dwf = tip_dwf
        item.calculate_statistics(settings.sample_dwf_stat_length_s)

    return WorkfunctionAnalysisResult(dwf_data=dwf_data, ref_aps=ref_aps, ref_dwf=ref_dwf, tip_dwf=tip_dwf)


def analyze_with_settings(item: ApsData, settings: ApsFitSettings) -> None:
    if settings.fit_domain == "metadata":
        if item.metadata is not None and item.metadata.has_fit_window:
            item.analyze_energy_window(item.metadata.e_low_ev, item.metadata.e_high_ev, settings.points)
        else:
            item.analyze(settings.fit_lower_bound, settings.fit_upper_bound, settings.points)
    elif settings.fit_domain == "energy":
        item.analyze_energy_window(settings.fit_lower_bound, settings.fit_upper_bound, settings.points)
    elif settings.fit_domain == "signal":
        item.analyze(settings.fit_lower_bound, settings.fit_upper_bound, settings.points)
    else:
        raise ApsAnalysisError(f"Unknown APS fit domain: {settings.fit_domain}.")


def analyze_workfunction_ref_aps(item: ApsData, settings: DwfSettings) -> None:
    if settings.ref_aps_fit_domain == "metadata" and item.metadata is not None and item.metadata.has_fit_window:
        item.analyze_energy_window(item.metadata.e_low_ev, item.metadata.e_high_ev, settings.ref_aps_fit_points)
    elif settings.ref_aps_fit_domain == "energy":
        item.analyze_energy_window(settings.ref_aps_fit_lower_bound, settings.ref_aps_fit_upper_bound, settings.ref_aps_fit_points)
    elif settings.ref_aps_fit_domain == "signal":
        item.analyze(settings.ref_aps_fit_lower_bound, settings.ref_aps_fit_upper_bound, settings.ref_aps_fit_points)
    else:
        raise ApsAnalysisError(f"Unknown reference APS fit domain: {settings.ref_aps_fit_domain}.")


def save_aps_csv(data: Sequence[ApsData], location: str, filename: str = "APS") -> Path:
    header = [["Energy", "Photoemission\\+(1/2)" if all(item.sqrt for item in data) else "Photoemission\\+(1/3)"], ["eV", "arb. unit"]]
    return save_csv_for_origin(([item.energy for item in data], [item.pes for item in data]), location, filename, [[item.name] for item in data], header)


def save_aps_fit_csv(data: Sequence[ApsData], location: str, filename: str = "APS_linear_regression") -> Path:
    if not all(item.is_analyzed for item in data):
        raise ApsAnalysisError("APS data must be analyzed before saving fit CSV.")
    header = [["Energy", "Photoemission\\+(1/2)" if all(item.sqrt for item in data) else "Photoemission\\+(1/3)"], ["eV", "arb. unit"]]
    x = [np.array([item.homo, item.energy[item.lin_stop_index]]) for item in data]
    y = [np.array([0.0, np.polyval(item.lin_par, item.energy[item.lin_stop_index])]) for item in data]
    return save_csv_for_origin((x, y), location, filename, [[item.name] for item in data], header)


def save_homo_error_csv(data: Sequence[ApsData], location: str, filename: str = "APS_HOMO") -> Path:
    if not all(item.is_analyzed for item in data):
        raise ApsAnalysisError("APS data must be analyzed before saving HOMO CSV.")
    header = [["Material", "Energy", "HOMO std"], [None, "eV", "eV"]]
    return save_csv_for_origin(
        ([[item.name for item in data]], [[-item.homo for item in data]], [[item.std_homo for item in data]]),
        location,
        filename,
        [["HOMO"]],
        header,
    )


def save_dos_csv(data: Sequence[ApsData], location: str, filename: str = "DOS") -> Path:
    header = [["Energy", "DOS"], ["eV", "arb. unit"]]
    return save_csv_for_origin(([item.energy for item in data], [item.dos for item in data]), location, filename, [[item.name] for item in data], header)


def save_dwf_csv(data: Sequence[DwfData], location: str, filename: str = "DWF") -> Path:
    if not data:
        raise ApsAnalysisError("No DWF data to save.")
    header = [["Time", data[0].data_type], ["s", data[0].data_unit]]
    return save_csv_for_origin(([item.time for item in data], [item.cpd_data for item in data]), location, filename, [[item.name] for item in data], header)


def save_dwf_stat_csv(data: Sequence[DwfData], location: str, filename: str = "DWF_stat") -> Path:
    if not all(item.has_statistics for item in data):
        raise ApsAnalysisError("DWF statistics must be calculated before saving statistics CSV.")
    header = [["Material", "Energy", data[0].data_type + " std"], [None, data[0].data_unit, data[0].data_unit]]
    return save_csv_for_origin(
        ([[item.name for item in data]], [[item.average_cpd for item in data]], [[item.std_cpd for item in data]]),
        location,
        filename,
        [[data[0].data_type]],
        header,
    )


def save_spv_csv(data: Sequence[SpvData], location: str, filename: str = "SPV") -> Path:
    if not data:
        raise ApsAnalysisError("No SPV data to save.")
    header = [["Time", data[0].data_type], ["s", data[0].data_unit]]
    return save_csv_for_origin(([item.time for item in data], [item.cpd_data for item in data]), location, filename, [[item.name] for item in data], header)


def save_normalized_spv_csv(data: Sequence[SpvData], location: str, filename: str = "Normalized_SPV") -> Path:
    if not data:
        raise ApsAnalysisError("No SPV data to save.")
    if not all(item.is_normalized for item in data):
        raise ApsAnalysisError("SPV data must be normalized before saving.")
    header = [["Time", "Normalized SPV"], ["s", ""]]
    return save_csv_for_origin(([item.time for item in data], [item.norm_spv for item in data]), location, filename, [[item.name] for item in data], header)


def save_csv_for_origin(data: tuple[Sequence[Sequence[float]], ...], location: str, filename: str, datanames=None, header=None) -> Path:
    output_dir = Path(location)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{filename}.csv"
    data_dim = len(data)
    number_of_data = len(data[0])
    if any(len(column_group) != number_of_data for column_group in data):
        raise ApsAnalysisError("Number of data series does not match.")
    flattened = [series for group in zip(*data) for series in group]
    max_length = max(len(series) for series in flattened)
    rows = np.transpose([np.append(np.asarray(series, dtype=object), [""] * (max_length - len(series))) for series in flattened])
    if datanames is None:
        datanames = [[f"data{i}" for i in range(number_of_data) for _ in range(data_dim)]]
    else:
        datanames = [[entry for names in datanames for entry in ([""] + names + [""] * (data_dim - 1 - len(names)))]]
    if header is None:
        header = datanames + [[""] * number_of_data * data_dim]
    else:
        header = [row * number_of_data for row in header]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerows(header)
        writer.writerows(datanames)
        writer.writerows(rows)
    return path


def mofun(x, c, mo_energy):
    return np.sum([gaussian(x, c, center) for center in mo_energy], axis=0)


def gaussian(x, c, center):
    return np.exp(-((x - center) ** 2) / 2 / c**2) / c / (2 * np.pi) ** 0.5


def erfsmooth(x: np.ndarray, scale: float, cutoff: float, y0: float) -> np.ndarray:
    if y0 < 0:
        raise ApsAnalysisError("DOS smoothing y0 must be >= 0.")
    return erf((x - cutoff) * scale) * (1 - y0) / 2 + (1 + y0) / 2


def parse_aps_dat_metadata(rows: Sequence[Sequence[str]]) -> ApsDatMetadata | None:
    values: dict[str, str] = {}
    for row in rows:
        for cell in row:
            for key, value in re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*([^,\s]+)", cell):
                values[key] = value
    if not values:
        return None
    return ApsDatMetadata(values)


def _read_csv_rows(path: str) -> list[list[str]]:
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.reader(handle))


def _full_file_name(path: str) -> str:
    return Path(path).name
