"""Public calibration-model API.

This module is a stable import surface for future code. The implementation
currently lives in `intensity_profile_tools` to preserve existing behavior.
"""

from ca_app.core.intensity_profile_tools import (
    EMPIRICAL_CALIBRATION_METHODS,
    EMPIRICAL_POWER_EXP_METHOD,
    GENERALIZED_EXPONENTIAL_POWER_METHOD,
    POLYNOMIAL_DEGREE_3_METHOD,
    TWO_STAGE_SOFTPLUS_SLOPE_METHOD,
    TWO_THRESHOLD_POWER_METHOD,
    X_MAX,
    X_MIN,
    CalibrationError,
    LaserCalibrationModel,
    empirical_power_exp_calibration,
    generalized_exponential_power,
    polynomial_degree_3,
    softplus,
    two_stage_softplus_slope,
    two_threshold_power,
)

__all__ = [
    "CalibrationError",
    "EMPIRICAL_CALIBRATION_METHODS",
    "EMPIRICAL_POWER_EXP_METHOD",
    "GENERALIZED_EXPONENTIAL_POWER_METHOD",
    "LaserCalibrationModel",
    "POLYNOMIAL_DEGREE_3_METHOD",
    "TWO_STAGE_SOFTPLUS_SLOPE_METHOD",
    "TWO_THRESHOLD_POWER_METHOD",
    "X_MAX",
    "X_MIN",
    "empirical_power_exp_calibration",
    "generalized_exponential_power",
    "polynomial_degree_3",
    "softplus",
    "two_stage_softplus_slope",
    "two_threshold_power",
]
