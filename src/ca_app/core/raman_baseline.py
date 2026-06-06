"""Raman substrate-baseline correction logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import warnings

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve


METHOD_ASPLS = "asPLS"
METHOD_DRPLS = "drPLS"
METHOD_BACKCOR = "Polynomial/backcor"
METHODS = (METHOD_ASPLS, METHOD_DRPLS, METHOD_BACKCOR)

ASPLS_LAMBDA_VALUES = (
    1e6,
    1.5e6,
    2e6,
    2.5e6,
    3e6,
    3.5e6,
    4e6,
    1e7,
    5e7,
)
ASPLS_K_VALUES = (1.0, 1.5, 2.0)
DRPLS_LAMBDA_VALUES = (
    1e4,
    3e4,
    1e5,
    1.5e5,
    2e5,
    2.5e5,
    3e5,
    3.5e5,
    4e5,
    1e6,
    1.5e6,
    2e6,
)
DRPLS_ETA_VALUES = (0.00, 0.05, 0.1, 0.15, 0.2, 0.25)
BACKCOR_ORDER_VALUES = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
BACKCOR_THRESHOLD_VALUES = (
    0.001,
    0.002,
    0.003,
    0.004,
    0.005,
    0.0075,
    0.010,
    0.0125,
    0.015,
    0.0175,
    0.020,
    0.0225,
    0.024,
    0.03,
)
BACKCOR_COST_FUNCTION = "atq"
DEFAULT_BACKCOR_BELOW_BASELINE_FRACTION = 0.25

DIFFERENCE_ORDER = 2
ASPLS_MAX_ITERATIONS = 30
DRPLS_MAX_ITERATIONS = 35
CONVERGENCE_TOLERANCE = 1e-4
TARGET_NEGATIVE_FRACTION = 0.15
ASPLS_NEGATIVE_FRACTION_TOLERANCE = 0.04
DRPLS_NEGATIVE_FRACTION_TOLERANCE = 0.05
BACKCOR_EDGE_FRACTION = 0.05


class RamanBaselineError(ValueError):
    pass


@dataclass
class RamanSpectrum:
    raman_shift: np.ndarray
    intensity: np.ndarray
    name: str = "no_name"


@dataclass
class RamanBaselineSettings:
    method: str = METHOD_ASPLS
    auto: bool = True
    lambda_values: tuple[float, ...] = ASPLS_LAMBDA_VALUES
    secondary_values: tuple[float, ...] = ASPLS_K_VALUES
    lambda_value: float | None = None
    secondary_value: float | None = None
    order_values: tuple[int, ...] = BACKCOR_ORDER_VALUES
    threshold_values: tuple[float, ...] = BACKCOR_THRESHOLD_VALUES
    order_value: int | None = None
    threshold_value: float | None = None
    below_baseline_fraction: float = DEFAULT_BACKCOR_BELOW_BASELINE_FRACTION


@dataclass
class RamanBaselineResult:
    spectrum: RamanSpectrum
    method: str
    auto: bool
    baseline: np.ndarray
    corrected: np.ndarray
    selected_parameters: dict[str, object]
    search_records: list[dict[str, object]] = field(default_factory=list)


def read_raman_txt(path: str | Path) -> RamanSpectrum:
    """Read a Raman text file with at least two numeric columns."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find Raman file: {path}")

    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.strip().replace(",", " ").split()
            if not parts:
                continue
            nums = []
            for item in parts:
                try:
                    nums.append(float(item))
                except ValueError:
                    pass
            if len(nums) >= 2:
                rows.append(nums[:2])

    if not rows:
        raise RamanBaselineError(f"No two-column numeric Raman data found in {path}")

    data = np.asarray(rows, dtype=float)
    finite = np.isfinite(data).all(axis=1)
    data = data[finite]
    if len(data) == 0:
        raise RamanBaselineError(f"No finite Raman data found in {path}")
    return RamanSpectrum(data[:, 0], data[:, 1], name=path.name)


def default_output_name(path: str | Path) -> str:
    path = Path(path)
    return f"{path.stem}_Copy.txt"


def parse_numeric_list(text: str, name: str) -> tuple[float, ...]:
    values = []
    for item in text.replace(",", " ").replace(";", " ").split():
        try:
            values.append(float(item))
        except ValueError as exc:
            raise RamanBaselineError(f"{name} contains an invalid number: {item}") from exc
    if not values:
        raise RamanBaselineError(f"{name} must contain at least one number.")
    return tuple(values)


def normalize_method(method: str) -> str:
    text = str(method).strip()
    if text in METHODS:
        return text
    lowered = text.lower()
    if lowered == "aspls":
        return METHOD_ASPLS
    if lowered == "drpls":
        return METHOD_DRPLS
    if lowered in {"polynomial/backcor", "backcor", "polynomial backcor"}:
        return METHOD_BACKCOR
    raise RamanBaselineError(f"Unknown Raman baseline method: {method}")


def validate_settings(settings: RamanBaselineSettings) -> RamanBaselineSettings:
    method = normalize_method(settings.method)
    below_baseline_fraction = float(settings.below_baseline_fraction)
    if not 0.0 < below_baseline_fraction < 1.0:
        raise RamanBaselineError("Below-baseline fraction must be greater than 0 and less than 1.")

    if method == METHOD_BACKCOR:
        if settings.auto:
            order_values = tuple(parse_backcor_order(value) for value in settings.order_values)
            threshold_values = tuple(float(value) for value in settings.threshold_values)
        else:
            if settings.order_value is None or settings.threshold_value is None:
                raise RamanBaselineError("Manual Polynomial/backcor fitting requires order and threshold values.")
            order_values = (parse_backcor_order(settings.order_value),)
            threshold_values = (float(settings.threshold_value),)
        if any(value <= 0 for value in threshold_values):
            raise RamanBaselineError("Polynomial/backcor thresholds must be greater than 0.")
        return RamanBaselineSettings(
            method=method,
            auto=settings.auto,
            order_values=order_values,
            threshold_values=threshold_values,
            order_value=order_values[0],
            threshold_value=threshold_values[0],
            below_baseline_fraction=below_baseline_fraction,
        )

    if settings.auto:
        if (
            method == METHOD_DRPLS
            and settings.lambda_values == ASPLS_LAMBDA_VALUES
            and settings.secondary_values == ASPLS_K_VALUES
        ):
            lambda_values = DRPLS_LAMBDA_VALUES
            secondary_values = DRPLS_ETA_VALUES
        else:
            lambda_values = tuple(float(value) for value in settings.lambda_values)
            secondary_values = tuple(float(value) for value in settings.secondary_values)
    else:
        if settings.lambda_value is None or settings.secondary_value is None:
            raise RamanBaselineError("Manual Raman baseline fitting requires two parameter values.")
        lambda_values = (float(settings.lambda_value),)
        secondary_values = (float(settings.secondary_value),)

    if any(value <= 0 for value in lambda_values):
        raise RamanBaselineError("lambda values must be greater than 0.")
    if method == METHOD_ASPLS:
        if any(value <= 0 for value in secondary_values):
            raise RamanBaselineError("asPLS k values must be greater than 0.")
    else:
        if any(value < 0 or value > 1 for value in secondary_values):
            raise RamanBaselineError("drPLS eta values must be between 0 and 1.")

    return RamanBaselineSettings(
        method=method,
        auto=settings.auto,
        lambda_values=lambda_values,
        secondary_values=secondary_values,
        lambda_value=lambda_values[0],
        secondary_value=secondary_values[0],
        below_baseline_fraction=below_baseline_fraction,
    )


def parse_backcor_order(value: int | float) -> int:
    if isinstance(value, bool):
        raise RamanBaselineError("Polynomial/backcor orders must be positive integers.")
    order = int(value)
    if not np.isclose(float(value), float(order)) or order < 1:
        raise RamanBaselineError("Polynomial/backcor orders must be positive integers.")
    return order


def fit_raman_baseline(spectrum: RamanSpectrum, settings: RamanBaselineSettings) -> RamanBaselineResult:
    settings = validate_settings(settings)
    x = np.asarray(spectrum.raman_shift, dtype=float)
    y = np.asarray(spectrum.intensity, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y):
        raise RamanBaselineError("Raman shift and intensity must be one-dimensional arrays of equal length.")
    if len(y) <= DIFFERENCE_ORDER + 2:
        raise RamanBaselineError("Not enough Raman data points for baseline fitting.")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise RamanBaselineError("Raman data contains NaN or Inf.")

    if settings.method == METHOD_BACKCOR:
        if settings.auto:
            best_record, baseline, corrected, records = automatic_backcor_search(x, y, settings)
        else:
            baseline, iterations, applied_shift, metrics = evaluate_backcor_candidate(
                x,
                y,
                settings.order_value,
                settings.threshold_value,
                below_baseline_fraction=settings.below_baseline_fraction,
            )
            corrected = y - baseline
            best_record = {
                "order": int(settings.order_value),
                "threshold": float(settings.threshold_value),
                "below_baseline_fraction": float(settings.below_baseline_fraction),
                "cost_function": BACKCOR_COST_FUNCTION,
                "iterations": int(iterations),
                "baseline_vertical_shift": float(applied_shift),
                **metrics,
            }
            records = [best_record]
    elif settings.auto:
        best_record, baseline, corrected, records = automatic_baseline_search(x, y, settings)
    else:
        corrected, baseline, iterations = estimate_baseline(
            y,
            settings.method,
            settings.lambda_value,
            settings.secondary_value,
        )
        best_record = {
            "lambda": float(settings.lambda_value),
            secondary_parameter_name(settings.method): float(settings.secondary_value),
            "difference_order": float(DIFFERENCE_ORDER),
            "iterations": float(iterations),
            **baseline_quality_score(x, y, baseline, corrected, settings.method),
        }
        records = [best_record]

    return RamanBaselineResult(
        spectrum=spectrum,
        method=settings.method,
        auto=settings.auto,
        baseline=baseline,
        corrected=corrected,
        selected_parameters=best_record,
        search_records=records,
    )


def automatic_baseline_search(
    x: np.ndarray,
    y: np.ndarray,
    settings: RamanBaselineSettings,
) -> tuple[dict[str, float], np.ndarray, np.ndarray, list[dict[str, float]]]:
    records = []
    results = []
    secondary_name = secondary_parameter_name(settings.method)

    for lambda_value in settings.lambda_values:
        for secondary_value in settings.secondary_values:
            corrected, baseline, iterations = estimate_baseline(
                y,
                settings.method,
                lambda_value,
                secondary_value,
            )
            record = {
                "lambda": float(lambda_value),
                secondary_name: float(secondary_value),
                "difference_order": float(DIFFERENCE_ORDER),
                "iterations": float(iterations),
                **baseline_quality_score(x, y, baseline, corrected, settings.method),
            }
            records.append(record)
            results.append((record, baseline, corrected))

    results.sort(key=lambda item: item[0]["score"])
    records = [item[0] for item in results]
    best_record, best_baseline, best_corrected = results[0]
    return best_record, best_baseline, best_corrected, records


def automatic_backcor_search(
    x: np.ndarray,
    y: np.ndarray,
    settings: RamanBaselineSettings,
) -> tuple[dict[str, object], np.ndarray, np.ndarray, list[dict[str, object]]]:
    records = []
    results = []
    for order in settings.order_values:
        for threshold in settings.threshold_values:
            baseline, iterations, applied_shift, metrics = evaluate_backcor_candidate(
                x,
                y,
                order,
                threshold,
                below_baseline_fraction=settings.below_baseline_fraction,
            )
            record = {
                "order": int(order),
                "threshold": float(threshold),
                "below_baseline_fraction": float(settings.below_baseline_fraction),
                "cost_function": BACKCOR_COST_FUNCTION,
                "iterations": int(iterations),
                "baseline_vertical_shift": float(applied_shift),
                **metrics,
            }
            records.append(record)
            results.append((record, baseline, y - baseline))
    if not results:
        raise RamanBaselineError("No valid Polynomial/backcor baseline candidate was found.")
    results.sort(key=lambda item: (item[0]["score"], item[0]["order"], item[0]["threshold"]))
    records = [item[0] for item in results]
    best_record, best_baseline, best_corrected = results[0]
    return best_record, best_baseline, best_corrected, records


def estimate_baseline(
    y: np.ndarray,
    method: str,
    lambda_value: float,
    secondary_value: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    if method == METHOD_ASPLS:
        return estimate_baseline_aspls(y, lambda_value=lambda_value, k=secondary_value)
    if method == METHOD_DRPLS:
        return estimate_baseline_drpls(y, lambda_value=lambda_value, eta=secondary_value)
    raise RamanBaselineError(f"Unknown Raman baseline method: {method}")


def secondary_parameter_name(method: str) -> str:
    if method == METHOD_DRPLS:
        return "eta"
    return "k"


def robust_scale(y: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    scale = np.nanpercentile(y, 95) - np.nanpercentile(y, 5)
    if not np.isfinite(scale) or scale <= 0:
        scale = np.nanstd(y)
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    return float(scale)


def difference_matrix(n_points: int, order: int = 2):
    if order < 1:
        raise RamanBaselineError("Difference order must be >= 1.")
    matrix = sparse.eye(n_points, format="csr")
    for _ in range(order):
        matrix = matrix[1:, :] - matrix[:-1, :]
    return matrix.tocsc()


def estimate_baseline_aspls(
    y: np.ndarray,
    lambda_value: float = 1e5,
    order: int = DIFFERENCE_ORDER,
    k: float = 0.5,
    itermax: int = ASPLS_MAX_ITERATIONS,
    epsilon: float = CONVERGENCE_TOLERANCE,
) -> tuple[np.ndarray, np.ndarray, int]:
    y = np.asarray(y, dtype=float).ravel()
    n = len(y)
    diff = difference_matrix(n, order=order)
    smooth_penalty = float(lambda_value) * (diff.T @ diff)

    weights = np.ones(n, dtype=float)
    adapt = np.ones(n, dtype=float)
    scale = robust_scale(y)
    eps_scale = max(scale * 1e-12, 1e-12)
    baseline = y.copy()

    for iteration in range(1, itermax + 1):
        weight_matrix = sparse.diags(weights, 0, shape=(n, n), format="csc")
        adapt_matrix = sparse.diags(adapt, 0, shape=(n, n), format="csc")
        matrix = weight_matrix + adapt_matrix @ smooth_penalty
        baseline = spsolve(matrix, weights * y)

        residual = y - baseline
        max_abs_residual = np.max(np.abs(residual))
        if not np.isfinite(max_abs_residual) or max_abs_residual < eps_scale:
            break
        adapt = np.abs(residual) / max_abs_residual

        negative_residual = residual[residual < 0]
        sigma = np.std(negative_residual) if len(negative_residual) >= 3 else np.std(residual)
        sigma = max(float(sigma), eps_scale)
        exponent = k * (residual - sigma) / sigma
        exponent = np.clip(exponent, -60, 60)
        next_weights = 1.0 / (1.0 + np.exp(exponent))

        change = np.sum(np.abs(weights - next_weights)) / max(np.sum(np.abs(weights)), eps_scale)
        weights = next_weights
        if change < epsilon:
            break

    return y - baseline, baseline, iteration


def estimate_baseline_drpls(
    y: np.ndarray,
    lambda_value: float = 1e5,
    order: int = DIFFERENCE_ORDER,
    eta: float = 0.5,
    itermax: int = DRPLS_MAX_ITERATIONS,
    epsilon: float = CONVERGENCE_TOLERANCE,
) -> tuple[np.ndarray, np.ndarray, int]:
    y = np.asarray(y, dtype=float).ravel()
    if not 0 <= eta <= 1:
        raise RamanBaselineError("eta must be between 0 and 1.")

    n = len(y)
    smooth_diff = difference_matrix(n, order=order)
    smooth_penalty = float(lambda_value) * (smooth_diff.T @ smooth_diff)
    first_diff = difference_matrix(n, order=1)
    first_penalty = first_diff.T @ first_diff
    identity = sparse.eye(n, format="csc")

    weights = np.ones(n, dtype=float)
    scale = robust_scale(y)
    eps_scale = max(scale * 1e-12, 1e-12)
    baseline = y.copy()

    for iteration in range(1, itermax + 1):
        weight_matrix = sparse.diags(weights, 0, shape=(n, n), format="csc")
        matrix = first_penalty + smooth_penalty + weight_matrix @ (identity - eta * smooth_penalty)
        baseline = spsolve(matrix.tocsc(), weights * y)

        next_weights, exit_early = drpls_weights(y, baseline, iteration, eps_scale)
        if exit_early:
            break
        change = relative_difference(weights, next_weights, eps=eps_scale)
        weights = next_weights
        if change < epsilon:
            break

    return y - baseline, baseline, iteration


def drpls_weights(y: np.ndarray, baseline: np.ndarray, iteration: int, eps_scale: float) -> tuple[np.ndarray, bool]:
    residual = y - baseline
    negative_residual = residual[residual < 0]
    if len(negative_residual) < 2:
        warnings.warn(
            "Almost all baseline points are below the data; stopping drPLS iterations early.",
            RuntimeWarning,
            stacklevel=2,
        )
        return np.zeros_like(y), True

    sigma = max(float(np.std(negative_residual, ddof=1)), eps_scale)
    center = 2 * sigma - float(np.mean(negative_residual))
    inner = (np.exp(min(iteration, 100)) / sigma) * (residual - center)
    inner = np.clip(inner, -1e300, 1e300)
    weights = 0.5 * (1.0 - inner / (1.0 + np.abs(inner)))
    return weights, False


def relative_difference(old: np.ndarray, new: np.ndarray, eps: float = 1e-12) -> float:
    old = np.asarray(old, dtype=float)
    new = np.asarray(new, dtype=float)
    return float(np.linalg.norm(old - new) / max(np.linalg.norm(old), eps))


def backcor(
    x_values: np.ndarray,
    y_values: np.ndarray,
    order: int = 1,
    threshold: float = 0.01,
    fct: str = BACKCOR_COST_FUNCTION,
    tol: float = 1e-9,
    max_iter: int = 10000,
) -> tuple[np.ndarray, np.ndarray, int]:
    if fct not in {"sh", "ah", "stq", "atq"}:
        raise RamanBaselineError("backcor cost function must be one of: sh, ah, stq, atq.")
    x_values = np.asarray(x_values, dtype=float).ravel()
    y_values = np.asarray(y_values, dtype=float).ravel()
    order = parse_backcor_order(order)
    threshold = float(threshold)
    if threshold <= 0:
        raise RamanBaselineError("Polynomial/backcor threshold must be greater than 0.")
    if x_values.size != y_values.size:
        raise RamanBaselineError("Raman shift and intensity must have the same length for Polynomial/backcor.")
    if x_values.size < order + 1:
        raise RamanBaselineError("Not enough data points for the selected Polynomial/backcor order.")

    sort_idx = np.argsort(x_values)
    x_sorted = x_values[sort_idx]
    y_sorted = y_values[sort_idx]
    if np.isclose(x_sorted[-1], x_sorted[0]):
        raise RamanBaselineError("Raman shift values must span a non-zero range for Polynomial/backcor.")

    max_y = np.max(y_sorted)
    half_range_y = (max_y - np.min(y_sorted)) / 2.0
    if np.isclose(half_range_y, 0.0):
        return y_values.copy(), np.zeros(order + 1), 0

    scaled_x = 2.0 * (x_sorted - x_sorted[-1]) / (x_sorted[-1] - x_sorted[0]) + 1.0
    scaled_y = (y_sorted - max_y) / half_range_y + 1.0
    vandermonde = np.vander(scaled_x, N=order + 1, increasing=True)
    transform = np.linalg.pinv(vandermonde.T @ vandermonde) @ vandermonde.T

    coeffs = transform @ scaled_y
    baseline_scaled = vandermonde @ coeffs
    alpha = 0.99 * 0.5
    previous_baseline = np.ones(len(x_sorted))
    iterations = 0

    while np.sum((baseline_scaled - previous_baseline) ** 2) / np.sum(previous_baseline**2) > tol:
        iterations += 1
        if iterations > max_iter:
            break
        previous_baseline = baseline_scaled.copy()
        residual = scaled_y - baseline_scaled
        if fct == "sh":
            correction = (
                (residual * (2 * alpha - 1)) * (np.abs(residual) < threshold)
                + (-alpha * 2 * threshold - residual) * (residual <= -threshold)
                + (alpha * 2 * threshold - residual) * (residual >= threshold)
            )
        elif fct == "ah":
            correction = (
                (residual * (2 * alpha - 1)) * (residual < threshold)
                + (alpha * 2 * threshold - residual) * (residual >= threshold)
            )
        elif fct == "stq":
            correction = (
                (residual * (2 * alpha - 1)) * (np.abs(residual) < threshold)
                - residual * (np.abs(residual) >= threshold)
            )
        else:
            correction = (
                (residual * (2 * alpha - 1)) * (residual < threshold)
                - residual * (residual >= threshold)
            )
        coeffs = transform @ (scaled_y + correction)
        baseline_scaled = vandermonde @ coeffs

    baseline_sorted = (baseline_scaled - 1.0) * half_range_y + max_y
    unsort_idx = np.argsort(sort_idx)
    baseline = baseline_sorted[unsort_idx]
    coeffs_out = coeffs.copy()
    coeffs_out[0] = coeffs_out[0] - 1.0
    coeffs_out = coeffs_out * half_range_y
    return baseline, coeffs_out, iterations


def robust_intensity_scale(y_values: np.ndarray) -> float:
    y_values = np.asarray(y_values, dtype=float)
    scale = np.nanpercentile(y_values, 95) - np.nanpercentile(y_values, 5)
    if not np.isfinite(scale) or scale <= 0:
        scale = np.nanmax(y_values) - np.nanmin(y_values)
    if not np.isfinite(scale) or scale <= 0:
        scale = np.nanstd(y_values)
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    return float(scale)


def estimate_noise_from_differences(y_values: np.ndarray) -> float:
    y_values = np.asarray(y_values, dtype=float)
    diffs = np.diff(y_values)
    diffs = diffs[np.isfinite(diffs)]
    if diffs.size < 5:
        return 0.0
    mad = np.nanmedian(np.abs(diffs - np.nanmedian(diffs)))
    noise = 1.4826 * mad / np.sqrt(2.0)
    if not np.isfinite(noise):
        noise = 0.0
    return float(noise)


def position_baseline_by_quantile(
    y_values: np.ndarray,
    baseline: np.ndarray,
    below_baseline_fraction: float = DEFAULT_BACKCOR_BELOW_BASELINE_FRACTION,
) -> tuple[np.ndarray, float]:
    quantile = 1.0 - float(below_baseline_fraction)
    excess = np.asarray(baseline, dtype=float) - np.asarray(y_values, dtype=float)
    shift = float(np.nanquantile(excess, quantile))
    return np.asarray(baseline, dtype=float) - shift, shift


def backcor_quality_metrics(
    x_values: np.ndarray,
    y_values: np.ndarray,
    baseline: np.ndarray,
    poly_order: int,
    threshold: float,
    below_baseline_fraction: float,
) -> dict[str, float]:
    x_values = np.asarray(x_values, dtype=float)
    y_values = np.asarray(y_values, dtype=float)
    baseline = np.asarray(baseline, dtype=float)
    corrected = y_values - baseline

    scale = robust_intensity_scale(y_values)
    noise = estimate_noise_from_differences(corrected)
    negative_fraction = float(np.nanmean(corrected < 0))
    negative_fraction_penalty = abs(negative_fraction - below_baseline_fraction)

    q01 = float(np.nanquantile(corrected, 0.01))
    q05 = float(np.nanquantile(corrected, 0.05))
    q25 = float(np.nanquantile(corrected, 0.25))
    q40 = float(np.nanquantile(corrected, 0.40))
    deep_negative_penalty = max(0.0, -q01 - 3.0 * noise) / scale
    moderate_negative_penalty = max(0.0, -q05 - 1.5 * noise) / scale
    lower_quartile_offset = abs(q25) / scale
    background_gap = max(0.0, q40) / scale

    edge_n = max(3, int(round(BACKCOR_EDGE_FRACTION * len(corrected))))
    edge_values = np.r_[corrected[:edge_n], corrected[-edge_n:]]
    edge_offset = abs(float(np.nanmedian(edge_values))) / scale

    sort_idx = np.argsort(x_values)
    baseline_sorted = baseline[sort_idx]
    if len(baseline_sorted) >= 3:
        curvature = float(np.sqrt(np.nanmean(np.diff(baseline_sorted, n=2) ** 2)) / scale)
    else:
        curvature = 0.0
    complexity = 0.006 * max(0, int(poly_order) - 4) ** 2

    score = (
        2.00 * negative_fraction_penalty
        + 5.00 * deep_negative_penalty
        + 2.00 * moderate_negative_penalty
        + 0.75 * lower_quartile_offset
        + 1.25 * background_gap
        + 0.35 * edge_offset
        + 0.10 * curvature
        + complexity
    )
    return {
        "score": float(score),
        "negative_fraction": negative_fraction,
        "corrected_q01": q01,
        "corrected_q05": q05,
        "corrected_q25": q25,
        "corrected_q40": q40,
        "noise_estimate": noise,
        "deep_negative_penalty": float(deep_negative_penalty),
        "background_gap_scaled": float(background_gap),
        "edge_offset_scaled": float(edge_offset),
        "curvature_scaled": float(curvature),
    }


def evaluate_backcor_candidate(
    x_values: np.ndarray,
    y_values: np.ndarray,
    poly_order: int,
    threshold: float,
    below_baseline_fraction: float = DEFAULT_BACKCOR_BELOW_BASELINE_FRACTION,
) -> tuple[np.ndarray, int, float, dict[str, float]]:
    baseline_raw, _, iterations = backcor(
        x_values,
        y_values,
        order=poly_order,
        threshold=threshold,
        fct=BACKCOR_COST_FUNCTION,
    )
    baseline, applied_shift = position_baseline_by_quantile(
        y_values,
        baseline_raw,
        below_baseline_fraction=below_baseline_fraction,
    )
    metrics = backcor_quality_metrics(
        x_values,
        y_values,
        baseline,
        poly_order,
        threshold,
        below_baseline_fraction,
    )
    return baseline, iterations, applied_shift, metrics


def baseline_quality_score(
    x: np.ndarray,
    y: np.ndarray,
    baseline: np.ndarray,
    corrected: np.ndarray,
    method: str,
) -> dict[str, float]:
    y = np.asarray(y, dtype=float)
    baseline = np.asarray(baseline, dtype=float)
    corrected = np.asarray(corrected, dtype=float)
    scale = robust_scale(y)
    tolerance = (
        DRPLS_NEGATIVE_FRACTION_TOLERANCE
        if method == METHOD_DRPLS
        else ASPLS_NEGATIVE_FRACTION_TOLERANCE
    )

    negative_fraction = float(np.mean(corrected < 0))
    negative_fraction_penalty = ((negative_fraction - TARGET_NEGATIVE_FRACTION) / tolerance) ** 2

    background_mask = corrected <= np.nanquantile(corrected, 0.35)
    if np.sum(background_mask) < max(5, int(0.05 * len(y))):
        background_mask = np.ones(len(y), dtype=bool)

    background_median_abs = abs(float(np.nanmedian(corrected[background_mask]))) / scale
    background_spread = (
        float(np.nanpercentile(corrected[background_mask], 90) - np.nanpercentile(corrected[background_mask], 10))
        / scale
    )
    lower_tail_depth = abs(min(float(np.nanquantile(corrected, 0.01)), 0.0)) / scale

    high_signal_mask = y >= np.nanquantile(y, 0.85)
    if np.any(high_signal_mask):
        peak_negative_fraction = float(np.mean(corrected[high_signal_mask] < 0))
        peak_lower_tail = abs(min(float(np.nanquantile(corrected[high_signal_mask], 0.02)), 0.0)) / scale
    else:
        peak_negative_fraction = 0.0
        peak_lower_tail = 0.0

    edge_n = max(5, int(0.05 * len(y)))
    edge_offset = (
        abs(float(np.nanmedian(corrected[:edge_n])))
        + abs(float(np.nanmedian(corrected[-edge_n:])))
    ) / (2 * scale)

    second_diff = np.diff(baseline, n=2)
    smoothness = float(np.sqrt(np.nanmean(second_diff**2))) / scale if len(second_diff) else 0.0
    score = (
        3.0 * negative_fraction_penalty
        + 8.0 * background_median_abs
        + 2.0 * background_spread
        + 6.0 * lower_tail_depth
        + 8.0 * peak_negative_fraction
        + 8.0 * peak_lower_tail
        + 4.0 * edge_offset
        + 1.0 * smoothness
    )

    return {
        "score": float(score),
        "negative_fraction": negative_fraction,
        "background_median_abs_scaled": float(background_median_abs),
        "background_spread_scaled": float(background_spread),
        "lower_tail_depth_scaled": float(lower_tail_depth),
        "peak_negative_fraction": float(peak_negative_fraction),
        "peak_lower_tail_scaled": float(peak_lower_tail),
        "edge_offset_scaled": float(edge_offset),
        "smoothness_scaled": float(smoothness),
    }


def interpolate_to_reference_x(source_x: np.ndarray, source_y: np.ndarray, reference_x: np.ndarray) -> np.ndarray:
    source_x = np.asarray(source_x, dtype=float)
    source_y = np.asarray(source_y, dtype=float)
    reference_x = np.asarray(reference_x, dtype=float)
    order = np.argsort(source_x)
    return np.interp(reference_x, source_x[order], source_y[order])


def save_corrected_txt(result: RamanBaselineResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("#Wave\t\t#Intensity\n")
        for x_value, y_value in zip(result.spectrum.raman_shift, result.corrected):
            handle.write(f"{x_value:.6f}\t{y_value:.6f}\n")
    return path
