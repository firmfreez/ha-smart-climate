"""Decision engine for Smart Climate."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .const import PHASE_BOOST, PHASE_HOLD, PHASE_IDLE, TYPE_EXTREME, TYPE_FAST, TYPE_NORMAL


@dataclass(frozen=True)
class Thresholds:
    """Thresholds for category selection."""

    category2_diff: float
    category3_diff: float


def aggregate_temperature(values: list[float], method: str) -> float | None:
    """Aggregate temperatures using a configured method."""
    if not values:
        return None
    if method == "min":
        return min(values)
    if method == "max":
        return max(values)
    if method == "median":
        return float(median(values))
    if method == "first":
        return values[0]
    return sum(values) / len(values)


def select_category(diff: float, thresholds: Thresholds, ac_allowed: bool) -> int:
    """Return 1..3 category by diff; degrade 3->2 when AC not allowed."""
    if diff < thresholds.category2_diff:
        category = 1
    elif diff < thresholds.category3_diff:
        category = 2
    else:
        category = 3

    if category == 3 and not ac_allowed:
        return 2
    return category


def within_target(current: float, target: float, tolerance: float) -> bool:
    """Whether room temperature is inside target band."""
    return abs(current - target) <= tolerance


def should_reenter_boost(
    current: float,
    target: float,
    tolerance: float,
    delta: float,
    is_heating: bool,
) -> bool:
    """Trigger boost when in hold and temperature drifts by delta from tolerance boundary."""
    if is_heating:
        lower_hold_edge = target - tolerance
        return current <= lower_hold_edge - delta
    upper_hold_edge = target + tolerance
    return current >= upper_hold_edge + delta


def next_phase_and_offset(
    control_type: str,
    phase: str,
    reached_target: bool,
    current_offset: float,
    step_offset: float,
    max_offset: float,
    elapsed_boost_seconds: float,
    t_time: float,
) -> tuple[str, float]:
    """Compute next phase and offset for NORMAL/FAST/EXTREME."""
    if reached_target:
        return PHASE_HOLD, 0.0

    if phase in (PHASE_IDLE, PHASE_HOLD):
        if control_type == TYPE_NORMAL:
            return PHASE_BOOST, min(step_offset, max_offset)
        return PHASE_BOOST, max_offset

    if phase == PHASE_BOOST:
        if control_type == TYPE_NORMAL and elapsed_boost_seconds >= t_time:
            return PHASE_BOOST, min(current_offset + step_offset, max_offset)
        if control_type in (TYPE_FAST, TYPE_EXTREME):
            return PHASE_BOOST, max_offset

    return phase, current_offset


def compute_setpoint(
    target: float,
    is_heating: bool,
    control_type: str,
    offset: float,
    climate_min_temp: float | None,
    climate_max_temp: float | None,
) -> float:
    """Compute setpoint for climate entity by profile."""
    if control_type == TYPE_EXTREME:
        if is_heating and climate_max_temp is not None:
            return climate_max_temp
        if not is_heating and climate_min_temp is not None:
            return climate_min_temp

    raw = target + offset if is_heating else target - offset
    if climate_min_temp is not None:
        raw = max(raw, climate_min_temp)
    if climate_max_temp is not None:
        raw = min(raw, climate_max_temp)
    return raw


def mode_hvac(is_heating: bool) -> str:
    """Return hvac mode name for requested direction."""
    return "heat" if is_heating else "cool"


def merge_categories(
    category_1: list[str],
    category_2: list[str],
    category_3: list[str],
    active_category: int,
) -> list[str]:
    """Return active entities for category selection with cumulative logic."""
    selected: list[str] = []
    lists = [category_1, category_2, category_3]
    for index in range(min(max(active_category, 1), 3)):
        selected.extend(lists[index])
    return list(dict.fromkeys(selected))


def filter_weather_sensitive(
    entity_ids: list[str],
    weather_sensitive_climates: set[str],
    is_outdoor_allowed: bool,
) -> list[str]:
    """Filter out weather-sensitive climate devices when outdoor policy blocks them."""
    if is_outdoor_allowed:
        return entity_ids
    return [
        entity_id
        for entity_id in entity_ids
        if not (entity_id.startswith("climate.") and entity_id in weather_sensitive_climates)
    ]
