"""Unit tests for decision engine."""

from custom_components.smart_climate.const import (
    PHASE_BOOST,
    PHASE_HOLD,
    TYPE_EXTREME,
    TYPE_FAST,
    TYPE_NORMAL,
)
from custom_components.smart_climate.engine import (
    Thresholds,
    aggregate_temperature,
    compute_setpoint,
    filter_weather_sensitive,
    merge_categories,
    mode_hvac,
    next_phase_and_offset,
    select_category,
    should_reenter_boost,
)


def test_aggregate_temperature_methods() -> None:
    values = [20.0, 22.0, 18.0]

    assert aggregate_temperature(values, "average") == 20.0
    assert aggregate_temperature(values, "min") == 18.0
    assert aggregate_temperature(values, "max") == 22.0
    assert aggregate_temperature(values, "median") == 20.0
    assert aggregate_temperature(values, "first") == 20.0
    assert aggregate_temperature([], "average") is None


def test_select_category_by_thresholds() -> None:
    thresholds = Thresholds(category2_diff=0.5, category3_diff=1.5)

    assert select_category(0.2, thresholds, ac_allowed=True) == 1
    assert select_category(0.9, thresholds, ac_allowed=True) == 2
    assert select_category(2.1, thresholds, ac_allowed=True) == 3


def test_select_category_degrades_when_ac_forbidden() -> None:
    thresholds = Thresholds(category2_diff=0.5, category3_diff=1.5)

    assert select_category(2.1, thresholds, ac_allowed=False) == 2


def test_normal_profile_boost_step_and_hold_transition() -> None:
    phase, offset = next_phase_and_offset(
        control_type=TYPE_NORMAL,
        phase=PHASE_HOLD,
        reached_target=False,
        current_offset=0.0,
        step_offset=0.5,
        max_offset=2.0,
        elapsed_boost_seconds=0,
        t_time=300,
    )
    assert phase == PHASE_BOOST
    assert offset == 0.5

    phase, offset = next_phase_and_offset(
        control_type=TYPE_NORMAL,
        phase=PHASE_BOOST,
        reached_target=False,
        current_offset=0.5,
        step_offset=0.5,
        max_offset=2.0,
        elapsed_boost_seconds=300,
        t_time=300,
    )
    assert phase == PHASE_BOOST
    assert offset == 1.0

    phase, offset = next_phase_and_offset(
        control_type=TYPE_NORMAL,
        phase=PHASE_BOOST,
        reached_target=True,
        current_offset=1.0,
        step_offset=0.5,
        max_offset=2.0,
        elapsed_boost_seconds=0,
        t_time=300,
    )
    assert phase == PHASE_HOLD
    assert offset == 0.0


def test_fast_profile_sets_max_offset_immediately() -> None:
    phase, offset = next_phase_and_offset(
        control_type=TYPE_FAST,
        phase=PHASE_HOLD,
        reached_target=False,
        current_offset=0.0,
        step_offset=0.5,
        max_offset=2.0,
        elapsed_boost_seconds=0,
        t_time=300,
    )
    assert phase == PHASE_BOOST
    assert offset == 2.0


def test_extreme_profile_behaves_as_max_boost_profile() -> None:
    phase, offset = next_phase_and_offset(
        control_type=TYPE_EXTREME,
        phase=PHASE_HOLD,
        reached_target=False,
        current_offset=0.0,
        step_offset=0.5,
        max_offset=3.0,
        elapsed_boost_seconds=0,
        t_time=300,
    )
    assert phase == PHASE_BOOST
    assert offset == 3.0


def test_reenter_boost_logic_for_heat_and_cool() -> None:
    assert should_reenter_boost(20.0, 22.0, 0.3, 0.5, is_heating=True)
    assert not should_reenter_boost(21.5, 22.0, 0.3, 0.5, is_heating=True)

    assert should_reenter_boost(25.0, 22.0, 0.3, 0.5, is_heating=False)
    assert not should_reenter_boost(22.6, 22.0, 0.3, 0.5, is_heating=False)


def test_compute_setpoint_clamp_and_extreme() -> None:
    assert compute_setpoint(22.0, True, TYPE_NORMAL, 1.5, 16.0, 24.0) == 23.5
    assert compute_setpoint(22.0, True, TYPE_NORMAL, 4.0, 16.0, 24.0) == 24.0
    assert compute_setpoint(22.0, False, TYPE_NORMAL, 4.0, 18.0, 30.0) == 18.0

    assert compute_setpoint(22.0, True, TYPE_EXTREME, 0.0, 16.0, 28.0) == 28.0
    assert compute_setpoint(22.0, False, TYPE_EXTREME, 0.0, 17.0, 30.0) == 17.0


def test_merge_categories_is_cumulative_and_deduplicated() -> None:
    cat1 = ["climate.rad", "script.h1"]
    cat2 = ["script.h1", "script.h2"]
    cat3 = ["climate.hp"]

    assert merge_categories(cat1, cat2, cat3, 1) == ["climate.rad", "script.h1"]
    assert merge_categories(cat1, cat2, cat3, 2) == ["climate.rad", "script.h1", "script.h2"]
    assert merge_categories(cat1, cat2, cat3, 3) == [
        "climate.rad",
        "script.h1",
        "script.h2",
        "climate.hp",
    ]


def test_filter_weather_sensitive_climates() -> None:
    entities = ["climate.rad", "climate.hp", "script.heater"]
    sensitive = {"climate.hp"}

    assert filter_weather_sensitive(entities, sensitive, is_outdoor_allowed=True) == entities
    assert filter_weather_sensitive(entities, sensitive, is_outdoor_allowed=False) == [
        "climate.rad",
        "script.heater",
    ]


def test_mode_hvac() -> None:
    assert mode_hvac(True) == "heat"
    assert mode_hvac(False) == "cool"
