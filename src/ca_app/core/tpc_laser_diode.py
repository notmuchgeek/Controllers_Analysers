"""TPC laser-diode selection, limit, and display calculations."""

from __future__ import annotations

from dataclasses import dataclass


RED_LD = "Red"
GREEN_LD = "Green"
RED_CURRENT_LIMIT_MA = 33.0
GREEN_CURRENT_LIMIT_MA = 48.0
DEFAULT_TPC_SETTING_CURRENT_MA = "15"


@dataclass(frozen=True)
class LaserDiodeSelection:
    name: str
    current_limit_mA: float
    used_default_red: bool = False


@dataclass(frozen=True)
class LaserDiodeCurrentRequest:
    requested_mA: float
    command_mA: float
    clamped: bool


def resolve_laser_diode_selection(green_checked: bool, red_checked: bool) -> LaserDiodeSelection:
    """Resolve LD checkboxes using the legacy red-default rule."""
    if red_checked and not green_checked:
        return LaserDiodeSelection(RED_LD, RED_CURRENT_LIMIT_MA)
    if green_checked and not red_checked:
        return LaserDiodeSelection(GREEN_LD, GREEN_CURRENT_LIMIT_MA)
    return LaserDiodeSelection(RED_LD, RED_CURRENT_LIMIT_MA, used_default_red=True)


def parse_requested_current_mA(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Setting current is empty.")
    try:
        current_mA = float(stripped)
    except ValueError as exc:
        raise ValueError("Setting current must be a number.") from exc
    if current_mA <= 0:
        raise ValueError("Setting current must be greater than 0 mA.")
    return current_mA


def clamp_current_to_limit(requested_mA: float, current_limit_mA: float) -> LaserDiodeCurrentRequest:
    command_mA = min(requested_mA, current_limit_mA)
    return LaserDiodeCurrentRequest(
        requested_mA=requested_mA,
        command_mA=command_mA,
        clamped=requested_mA > current_limit_mA,
    )


def optical_power_from_current_mA(ld_name: str, current_mA: float) -> float:
    """Calculate optical output power using the legacy linear formulas."""
    if ld_name == GREEN_LD:
        return 0.3 * current_mA - 4.3
    return 0.5 * current_mA - 4.3
