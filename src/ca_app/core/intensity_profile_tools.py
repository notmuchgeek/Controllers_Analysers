"""
Helper functions for Keithley laser source control.

This module contains non-GUI logic for:
- loading current-intensity calibration CSV files
- fitting / interpolating intensity-current curves
- converting target intensity into required source current
- safely evaluating user f(x) profiles where x is normalized from 0 to 1

Expected calibration CSV columns are either named columns such as:
Current_mA, Intensity_mW
or any two numeric columns, where the first numeric column is current in mA
and the second numeric column is intensity in mW.
"""

from __future__ import annotations

import ast
import csv
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Tuple

import numpy as np

_least_squares = None
_least_squares_import_failed = False


def get_least_squares():
    global _least_squares, _least_squares_import_failed
    if _least_squares is not None:
        return _least_squares
    if _least_squares_import_failed:
        return None
    try:
        from scipy.optimize import least_squares
    except ImportError:  # pragma: no cover - handled at runtime with a clear user error.
        _least_squares_import_failed = True
        return None
    _least_squares = least_squares
    return _least_squares


class CalibrationError(ValueError):
    """Raised when calibration data or intensity conversion is invalid."""


class FunctionExpressionError(ValueError):
    """Raised when a user function expression cannot be evaluated safely."""


X_MIN = 67.0
X_MAX = 94.0

EMPIRICAL_POWER_EXP_METHOD = "Empirical power-exp"
TWO_THRESHOLD_POWER_METHOD = "Two threshold power"
TWO_STAGE_SOFTPLUS_SLOPE_METHOD = "Two stage softplus slope"
GENERALIZED_EXPONENTIAL_POWER_METHOD = "Generalized exponential power"
POLYNOMIAL_DEGREE_3_METHOD = "Polynomial degree 3"
EMPIRICAL_CALIBRATION_METHODS = [
    EMPIRICAL_POWER_EXP_METHOD,
    TWO_THRESHOLD_POWER_METHOD,
    TWO_STAGE_SOFTPLUS_SLOPE_METHOD,
    GENERALIZED_EXPONENTIAL_POWER_METHOD,
    POLYNOMIAL_DEGREE_3_METHOD,
]
EMPIRICAL_POWER_EXP_I_MIN_MA = X_MIN


def softplus(x, w):
    """Smooth approximation of max(0, x)."""
    x = np.asarray(x, dtype=float)
    return w * np.logaddexp(0.0, x / w)


def empirical_power_exp_calibration(current_mA, L0, A, p, B, k):
    z = np.asarray(current_mA, dtype=float) - EMPIRICAL_POWER_EXP_I_MIN_MA
    z = np.clip(z, 0.0, None)
    return L0 + A * z**p + B * np.expm1(np.clip(k * z, -60.0, 60.0))


def two_threshold_power(current_mA, L0, A1, p1, A2, p2, I1, dI12, w1, w2):
    current_mA = np.asarray(current_mA, dtype=float)
    I2 = I1 + dI12
    S1 = softplus(current_mA - I1, w1)
    S2 = softplus(current_mA - I2, w2)
    return L0 + A1 * S1**p1 + A2 * S2**p2


def two_stage_softplus_slope(current_mA, L0, s0, ds1, ds2, I1, dI12, w1, w2):
    current_mA = np.asarray(current_mA, dtype=float)
    z = current_mA - X_MIN
    I2 = I1 + dI12
    S1 = softplus(current_mA - I1, w1)
    S2 = softplus(current_mA - I2, w2)
    return L0 + s0 * z + ds1 * S1 + ds2 * S2


def generalized_exponential_power(current_mA, L0, A, k, p, I0):
    current_mA = np.asarray(current_mA, dtype=float)
    u = np.expm1(np.clip(k * (current_mA - I0), -60.0, 60.0))
    u = np.clip(u, 0.0, None)
    return L0 + A * u**p


def polynomial_degree_3(current_mA, a0, a1, a2, a3):
    current_mA = np.asarray(current_mA, dtype=float)
    z = current_mA - X_MIN
    return a0 + a1 * z + a2 * z**2 + a3 * z**3


_ALLOWED_AST_NODES = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Num,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Call,
    ast.Attribute,
}

_ALLOWED_FUNCTIONS: Dict[str, object] = {
    "np": np,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "arcsin": np.arcsin,
    "arccos": np.arccos,
    "arctan": np.arctan,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sqrt": np.sqrt,
    "abs": np.abs,
    "minimum": np.minimum,
    "maximum": np.maximum,
    "clip": np.clip,
    "pi": np.pi,
    "e": np.e,
}


def _validate_expression_ast(expr: str) -> None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise FunctionExpressionError(f"Invalid f(x) syntax: {exc}") from exc

    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_AST_NODES:
            raise FunctionExpressionError(
                f"Unsupported expression element: {type(node).__name__}."
            )
        if isinstance(node, ast.Name):
            if node.id != "x" and node.id not in _ALLOWED_FUNCTIONS:
                raise FunctionExpressionError(
                    f"Unsupported name '{node.id}'. Use x, numbers, and functions such as sin, cos, exp, sqrt, log, pi."
                )
        if isinstance(node, ast.Attribute):
            if not isinstance(node.value, ast.Name) or node.value.id != "np":
                raise FunctionExpressionError("Only np.<function> attributes are allowed.")


def evaluate_user_function(expr: str, x_values: Iterable[float]) -> np.ndarray:
    """Evaluate f(x) for normalized x values from 0 to 1.

    Supports expressions such as:
    - 50*x
    - 10 + 40*x
    - 50 + 20*sin(2*pi*x)
    - np.clip(100*x, 0, 80)
    """
    expr = (expr or "").strip().replace("^", "**")
    if not expr:
        raise FunctionExpressionError("f(x) is empty.")
    _validate_expression_ast(expr)

    x = np.asarray(list(x_values), dtype=float)
    namespace = dict(_ALLOWED_FUNCTIONS)
    namespace["x"] = x

    try:
        result = eval(compile(ast.parse(expr, mode="eval"), "<user f(x)>", "eval"), {"__builtins__": {}}, namespace)
    except Exception as exc:
        raise FunctionExpressionError(f"Could not evaluate f(x): {exc}") from exc

    y = np.asarray(result, dtype=float)
    if y.ndim == 0:
        y = np.full_like(x, float(y), dtype=float)
    if y.shape != x.shape:
        try:
            y = np.broadcast_to(y, x.shape).astype(float)
        except ValueError as exc:
            raise FunctionExpressionError("f(x) did not return a scalar or an array matching x.") from exc
    if not np.all(np.isfinite(y)):
        raise FunctionExpressionError("f(x) produced NaN or infinite values.")
    return y


def load_intensity_csv(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load calibration data from CSV as current_mA, intensity_mW."""
    rows = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if row and any(cell.strip() for cell in row):
                rows.append([cell.strip() for cell in row])

    if not rows:
        raise CalibrationError("Calibration CSV is empty.")

    # Try header-based parsing first.
    header = [h.lower().replace(" ", "_") for h in rows[0]]
    current_idx = None
    intensity_idx = None
    for i, h in enumerate(header):
        if current_idx is None and ("current" in h or h in {"ma", "current_ma", "i_ma"}):
            current_idx = i
        if intensity_idx is None and ("intensity" in h or "power" in h or h in {"mw", "intensity_mw", "power_mw"}):
            intensity_idx = i

    data_rows = rows[1:] if current_idx is not None and intensity_idx is not None else rows

    currents = []
    intensities = []
    if current_idx is not None and intensity_idx is not None:
        for row in data_rows:
            if max(current_idx, intensity_idx) >= len(row):
                continue
            try:
                currents.append(float(row[current_idx]))
                intensities.append(float(row[intensity_idx]))
            except ValueError:
                continue
    else:
        # Fallback: take first two numeric columns in each row.
        for row in data_rows:
            nums = []
            for cell in row:
                try:
                    nums.append(float(cell))
                except ValueError:
                    pass
            if len(nums) >= 2:
                currents.append(nums[0])
                intensities.append(nums[1])

    current = np.asarray(currents, dtype=float)
    intensity = np.asarray(intensities, dtype=float)

    mask = np.isfinite(current) & np.isfinite(intensity)
    current = current[mask]
    intensity = intensity[mask]

    if len(current) < 2:
        raise CalibrationError("Calibration CSV needs at least two numeric current-intensity points.")

    order = np.argsort(current)
    current = current[order]
    intensity = intensity[order]

    # Merge duplicate current points by averaging intensity.
    unique_currents = []
    unique_intensities = []
    for c in np.unique(current):
        idx = current == c
        unique_currents.append(c)
        unique_intensities.append(float(np.mean(intensity[idx])))

    return np.asarray(unique_currents), np.asarray(unique_intensities)


@dataclass
class CalibrationStats:
    r2: float
    rmse_mw: float
    mae_mw: float
    max_error_mw: float
    current_min_ma: float
    current_max_ma: float
    intensity_min_mw: float
    intensity_max_mw: float

    def as_text(self) -> str:
        return (
            f"R² = {self.r2:.6g}\n"
            f"RMSE = {self.rmse_mw:.6g} mW\n"
            f"MAE = {self.mae_mw:.6g} mW\n"
            f"Max error = {self.max_error_mw:.6g} mW\n"
            f"Current range = {self.current_min_ma:.6g} to {self.current_max_ma:.6g} mA\n"
            f"Intensity range = {self.intensity_min_mw:.6g} to {self.intensity_max_mw:.6g} mW"
        )


def _empirical_model_spec(method: str, intensity_mW: np.ndarray):
    y = np.asarray(intensity_mW, dtype=float)
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    y_span = max(y_max - y_min, 1e-6)
    method_key = method.lower()

    if method_key == EMPIRICAL_POWER_EXP_METHOD.lower():
        z_max = max(X_MAX - X_MIN, 1e-6)
        starts = [
            [max(y_min, 0.0), 0.65 * y_span / max(z_max**1.2, 1e-9), 1.2, 0.10 * y_span, 0.05],
            [max(y_min, 0.0), 0.80 * y_span / max(z_max, 1e-9), 1.0, 0.05 * y_span, 0.08],
            [max(y_min, 0.0), 0.45 * y_span / max(z_max**1.8, 1e-9), 1.8, 0.15 * y_span, 0.06],
            [max(y_min * 0.8, 0.0), 0.25 * y_span / max(z_max**2.2, 1e-9), 2.2, 0.20 * y_span, 0.04],
            [max(y_min, 0.0), 0.90 * y_span / max(z_max**0.8, 1e-9), 0.8, 0.03 * y_span, 0.10],
            [max(y_min, 0.0), 0.10 * y_span / max(z_max**2.8, 1e-9), 2.8, 0.30 * y_span, 0.03],
        ]
        return {
            "function": empirical_power_exp_calibration,
            "param_names": ["L0", "A", "p", "B", "k"],
            "starts": starts,
            "lower": [0.0, 0.0, 0.05, 0.0, 0.0],
            "upper": [max(y_max * 2.0, 1.0), max(y_span * 10.0, 1.0), 6.0, max(y_span * 10.0, 1.0), 0.6],
            "x_scale": [max(y_max, 1.0), 0.05, 1.0, 0.05, 0.05],
        }

    if method_key == TWO_THRESHOLD_POWER_METHOD.lower():
        return {
            "function": two_threshold_power,
            "param_names": ["L0", "A1", "p1", "A2", "p2", "I1", "dI12", "w1", "w2"],
            "starts": [[y_min, 0.02, 1.5, 0.01, 2.0, 70.0, 16.0, 1.0, 1.0]],
            "lower": [y_min - 0.5, 0.0, 0.3, 0.0, 0.3, 67.0, 1.0, 0.05, 0.05],
            "upper": [y_max + 1.0, 5.0, 6.0, 5.0, 6.0, 88.0, 25.0, 8.0, 8.0],
            "x_scale": [max(y_max, 1.0), 0.05, 1.0, 0.05, 1.0, 5.0, 5.0, 1.0, 1.0],
        }

    if method_key == TWO_STAGE_SOFTPLUS_SLOPE_METHOD.lower():
        return {
            "function": two_stage_softplus_slope,
            "param_names": ["L0", "s0", "ds1", "ds2", "I1", "dI12", "w1", "w2"],
            "starts": [[y_min, 0.005, 0.08, 0.12, 72.0, 15.0, 1.5, 1.5]],
            "lower": [y_min - 0.5, 0.0, 0.0, 0.0, 67.0, 1.0, 0.05, 0.05],
            "upper": [y_max + 1.0, 0.5, 1.0, 1.0, 88.0, 25.0, 8.0, 8.0],
            "x_scale": [max(y_max, 1.0), 0.01, 0.1, 0.1, 5.0, 5.0, 1.0, 1.0],
        }

    if method_key == GENERALIZED_EXPONENTIAL_POWER_METHOD.lower():
        return {
            "function": generalized_exponential_power,
            "param_names": ["L0", "A", "k", "p", "I0"],
            "starts": [[y_min, 0.05, 0.06, 1.5, 66.5]],
            "lower": [y_min - 0.5, 0.0, 0.001, 0.3, 60.0],
            "upper": [y_max + 1.0, 50.0, 0.5, 6.0, 70.0],
            "x_scale": [max(y_max, 1.0), 0.1, 0.05, 1.0, 5.0],
        }

    if method_key == POLYNOMIAL_DEGREE_3_METHOD.lower():
        return {
            "function": polynomial_degree_3,
            "param_names": ["a0", "a1", "a2", "a3"],
            "starts": [[y_min, 0.02, 0.005, 0.0001]],
            "lower": [y_min - 1.0, -10.0, -10.0, -10.0],
            "upper": [y_max + 1.0, 10.0, 10.0, 10.0],
            "x_scale": [max(y_max, 1.0), 0.05, 0.005, 0.0001],
        }

    return None


class LaserCalibrationModel:
    """Intensity-current calibration model.

    method may be:
    - 'Interpolation'
    - 'Linear'
    - 'Quadratic'
    - 'Cubic'
    - 'Empirical power-exp'
    - 'Two threshold power'
    - 'Two stage softplus slope'
    - 'Generalized exponential power'
    - 'Polynomial degree 3'
    """

    def __init__(
        self,
        current_mA: np.ndarray,
        intensity_mW: np.ndarray,
        method: str = "Interpolation",
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.current_mA = np.asarray(current_mA, dtype=float)
        self.intensity_mW = np.asarray(intensity_mW, dtype=float)
        self.method = method
        self.progress_callback = progress_callback
        self.coeffs = None
        self.empirical_params = None
        self.empirical_function = None
        self.empirical_param_names = []
        self._fit()

    @classmethod
    def from_csv(
        cls,
        path: str,
        method: str = "Interpolation",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> "LaserCalibrationModel":
        current, intensity = load_intensity_csv(path)
        return cls(current, intensity, method=method, progress_callback=progress_callback)

    def _progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _fit(self) -> None:
        method = self.method.lower()
        if method == "interpolation":
            self.coeffs = None
            return
        if self.method in EMPIRICAL_CALIBRATION_METHODS:
            self._fit_empirical_model()
            return
        degrees = {"linear": 1, "quadratic": 2, "cubic": 3}
        if method not in degrees:
            raise CalibrationError(f"Unknown fit method: {self.method}")
        degree = degrees[method]
        if len(self.current_mA) < degree + 1:
            raise CalibrationError(f"{self.method} fit needs at least {degree + 1} data points.")
        self.coeffs = np.polyfit(self.current_mA, self.intensity_mW, degree)

    def _fit_empirical_model(self) -> None:
        least_squares = get_least_squares()
        if least_squares is None:
            raise CalibrationError(f"{self.method} fit requires scipy. Install scipy in this Python environment.")
        if len(self.current_mA) < 5:
            raise CalibrationError(f"{self.method} fit needs at least five calibration points.")

        current_min = float(np.min(self.current_mA))
        current_max = float(np.max(self.current_mA))
        if current_min < X_MIN or current_max > X_MAX:
            raise CalibrationError(
                f"{self.method} should be fit only within {X_MIN:.6g} to {X_MAX:.6g} mA."
            )

        y = self.intensity_mW
        y_span = max(float(np.max(y)) - float(np.min(y)), 1e-6)
        spec = _empirical_model_spec(self.method, y)
        if spec is None:
            raise CalibrationError(f"Unknown empirical fit method: {self.method}")

        self._progress(
            f"{self.method} fit: {len(self.current_mA)} points from {current_min:.6g} to {current_max:.6g} mA."
        )

        starts = spec["starts"]
        lower = np.asarray(spec["lower"], dtype=float)
        upper = np.asarray(spec["upper"], dtype=float)
        model_function = spec["function"]

        best_result = None
        for idx, start in enumerate(starts, start=1):
            x0 = np.clip(np.asarray(start, dtype=float), lower + 1e-12, upper - 1e-12)
            self._progress(f"{self.method} fit trial {idx}/{len(starts)} started.")
            eval_count = [0]
            last_progress_time = [time.monotonic()]

            def residual_with_progress(params):
                pred = model_function(self.current_mA, *params)
                scaled_residual = (pred - y) / y_span
                eval_count[0] += 1
                now = time.monotonic()
                if now - last_progress_time[0] >= 1.0:
                    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
                    self._progress(
                        f"{self.method} fit trial {idx}/{len(starts)} running: "
                        f"{eval_count[0]} evaluations, RMSE {rmse:.6g} mW."
                    )
                    last_progress_time[0] = now
                return scaled_residual

            result = least_squares(
                residual_with_progress,
                x0,
                bounds=(lower, upper),
                x_scale=spec["x_scale"],
                loss="soft_l1",
                f_scale=0.1,
                max_nfev=30000,
            )
            rmse = float(np.sqrt(np.mean((model_function(self.current_mA, *result.x) - y) ** 2)))
            self._progress(f"{self.method} fit trial {idx}/{len(starts)} complete: RMSE {rmse:.6g} mW.")
            if best_result is None or result.cost < best_result.cost:
                best_result = result

        if best_result is None or not np.all(np.isfinite(best_result.x)):
            raise CalibrationError(f"{self.method} fit failed.")

        self.empirical_params = np.asarray(best_result.x, dtype=float)
        self.empirical_function = model_function
        self.empirical_param_names = spec["param_names"]
        self.coeffs = None
        params_text = ", ".join(
            f"{name}={value:.6g}" for name, value in zip(self.empirical_param_names, self.empirical_params)
        )
        self._progress(f"{self.method} fit selected: {params_text}.")

    def predict_intensity(self, current_mA: Iterable[float]) -> np.ndarray:
        current = np.asarray(current_mA, dtype=float)
        if self.empirical_params is not None:
            return self.empirical_function(current, *self.empirical_params)
        if self.coeffs is None:
            return np.interp(current, self.current_mA, self.intensity_mW)
        return np.polyval(self.coeffs, current)

    def stats(self) -> CalibrationStats:
        pred = self.predict_intensity(self.current_mA)
        err = pred - self.intensity_mW
        ss_res = float(np.sum(err ** 2))
        centered = self.intensity_mW - float(np.mean(self.intensity_mW))
        ss_tot = float(np.sum(centered ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        return CalibrationStats(
            r2=r2,
            rmse_mw=float(np.sqrt(np.mean(err ** 2))),
            mae_mw=float(np.mean(np.abs(err))),
            max_error_mw=float(np.max(np.abs(err))),
            current_min_ma=float(np.min(self.current_mA)),
            current_max_ma=float(np.max(self.current_mA)),
            intensity_min_mw=float(np.min(self.intensity_mW)),
            intensity_max_mw=float(np.max(self.intensity_mW)),
        )

    def current_for_intensity(self, target_intensity_mW: Iterable[float]) -> np.ndarray:
        """Invert calibration to obtain source current for target intensity.

        Requires target intensity to lie within calibration intensity range.
        For polynomial fits, inversion is performed by dense-grid interpolation.
        """
        target = np.asarray(target_intensity_mW, dtype=float)
        if not np.all(np.isfinite(target)):
            raise CalibrationError("Target intensity contains NaN or infinite values.")

        i_min = float(np.min(self.intensity_mW))
        i_max = float(np.max(self.intensity_mW))
        if np.any(target < min(i_min, i_max)) or np.any(target > max(i_min, i_max)):
            raise CalibrationError(
                f"Target intensity is outside the calibrated range: {min(i_min, i_max):.6g} to {max(i_min, i_max):.6g} mW."
            )

        if self.empirical_params is not None:
            grid_current = np.linspace(float(np.min(self.current_mA)), float(np.max(self.current_mA)), 5000)
            grid_intensity = self.predict_intensity(grid_current)
            diffs = np.diff(grid_intensity)
            if not (np.all(diffs >= -1e-10) or np.all(diffs <= 1e-10)):
                raise CalibrationError(f"{self.method} fit is not monotonic enough to invert safely.")
            if np.all(diffs <= 1e-10):
                grid_current = grid_current[::-1]
                grid_intensity = grid_intensity[::-1]
            unique_intensity, unique_idx = np.unique(grid_intensity, return_index=True)
            unique_current = grid_current[unique_idx]
            if len(unique_intensity) < 2:
                raise CalibrationError(f"{self.method} fitted curve cannot be inverted.")
            if np.any(target < unique_intensity[0]) or np.any(target > unique_intensity[-1]):
                raise CalibrationError(f"Target intensity is outside the {self.method} fitted range.")
            return np.interp(target, unique_intensity, unique_current)

        if self.coeffs is None:
            # Need intensity monotonic for direct inverse interpolation.
            diffs = np.diff(self.intensity_mW)
            if np.all(diffs >= 0):
                return np.interp(target, self.intensity_mW, self.current_mA)
            if np.all(diffs <= 0):
                return np.interp(target, self.intensity_mW[::-1], self.current_mA[::-1])
            raise CalibrationError(
                "Interpolation inverse requires monotonic intensity vs current data. Check calibration CSV."
            )

        # Dense-grid inverse for polynomial fit. The predicted curve must be monotonic.
        grid_current = np.linspace(float(np.min(self.current_mA)), float(np.max(self.current_mA)), 5000)
        grid_intensity = self.predict_intensity(grid_current)
        order = np.argsort(grid_intensity)
        sorted_intensity = grid_intensity[order]
        sorted_current = grid_current[order]

        # Remove duplicate intensity values to keep np.interp stable.
        unique_intensity, unique_idx = np.unique(sorted_intensity, return_index=True)
        unique_current = sorted_current[unique_idx]
        if len(unique_intensity) < 2:
            raise CalibrationError("Fitted intensity-current curve cannot be inverted.")
        if np.any(target < unique_intensity[0]) or np.any(target > unique_intensity[-1]):
            raise CalibrationError("Target intensity is outside the fitted invertible range.")
        return np.interp(target, unique_intensity, unique_current)

    def curve_for_plot(self, n: int = 400) -> Tuple[np.ndarray, np.ndarray]:
        current = np.linspace(float(np.min(self.current_mA)), float(np.max(self.current_mA)), n)
        intensity = self.predict_intensity(current)
        return current, intensity
