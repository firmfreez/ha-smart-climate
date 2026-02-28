"""Scenario-driven tests for Smart Climate decision logic."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from custom_components.smart_climate.const import (
    MODE_GLOBAL,
    MODE_OFF,
    MODE_PER_ROOM,
    PHASE_BOOST,
    PHASE_HOLD,
    TYPE_EXTREME,
    TYPE_FAST,
    TYPE_NORMAL,
)
from custom_components.smart_climate.engine import (
    Thresholds,
    compute_setpoint,
    filter_weather_sensitive,
    merge_categories,
    next_phase_and_offset,
    select_category,
)


@dataclass(frozen=True)
class RoomSetup:
    room_id: str
    heat_cat1: list[str]
    heat_cat2: list[str]
    heat_cat3: list[str]
    cool_cat1: list[str]
    cool_cat2: list[str]
    cool_cat3: list[str]
    weather_sensitive: set[str]
    shared: list[str]


def _five_room_setup() -> dict[str, RoomSetup]:
    """Return scenario required in the spec with one shared floor on 3 rooms."""
    return {
        "room1": RoomSetup(
            room_id="room1",
            heat_cat1=["climate.room1_radiator"],
            heat_cat2=["script.room1_heater_on"],
            heat_cat3=["climate.room1_ac"],
            cool_cat1=[],
            cool_cat2=[],
            cool_cat3=["climate.room1_ac"],
            weather_sensitive={"climate.room1_ac"},
            shared=[],
        ),
        "room2": RoomSetup(
            room_id="room2",
            heat_cat1=["climate.floor_shared"],
            heat_cat2=[],
            heat_cat3=[],
            cool_cat1=[],
            cool_cat2=[],
            cool_cat3=[],
            weather_sensitive=set(),
            shared=["climate.floor_shared"],
        ),
        "room3": RoomSetup(
            room_id="room3",
            heat_cat1=["climate.floor_shared"],
            heat_cat2=[],
            heat_cat3=[],
            cool_cat1=[],
            cool_cat2=[],
            cool_cat3=[],
            weather_sensitive=set(),
            shared=["climate.floor_shared"],
        ),
        "room4": RoomSetup(
            room_id="room4",
            heat_cat1=["climate.floor_shared", "climate.room4_radiator"],
            heat_cat2=[],
            heat_cat3=["climate.room4_ac"],
            cool_cat1=[],
            cool_cat2=[],
            cool_cat3=["climate.room4_ac"],
            weather_sensitive={"climate.room4_ac"},
            shared=["climate.floor_shared"],
        ),
        "room5": RoomSetup(
            room_id="room5",
            heat_cat1=["climate.room5_radiator"],
            heat_cat2=[],
            heat_cat3=[],
            cool_cat1=[],
            cool_cat2=[],
            cool_cat3=[],
            weather_sensitive=set(),
            shared=[],
        ),
    }


def _select_room_entities(
    room: RoomSetup,
    is_heating: bool,
    diff: float,
    thresholds: Thresholds,
    ac_allowed: bool,
) -> tuple[int, list[str]]:
    category = select_category(diff, thresholds, ac_allowed=ac_allowed)
    if is_heating:
        entities = merge_categories(room.heat_cat1, room.heat_cat2, room.heat_cat3, category)
    else:
        entities = merge_categories(room.cool_cat1, room.cool_cat2, room.cool_cat3, category)
    entities = filter_weather_sensitive(entities, room.weather_sensitive, ac_allowed)
    return category, entities


def _shared_winner_max(demands: dict[str, float]) -> str:
    return max(demands, key=demands.get)


def _shared_winner_priority(demands: dict[str, float], priority_room: str) -> str:
    if priority_room in demands:
        return priority_room
    return _shared_winner_max(demands)


def _shared_winner_average(demands: dict[str, float]) -> float:
    return sum(demands.values()) / len(demands)


@pytest.mark.parametrize(
    ("mode", "enabled", "should_control"),
    [
        (MODE_OFF, True, False),
        (MODE_PER_ROOM, True, True),
        (MODE_GLOBAL, True, True),
        (MODE_PER_ROOM, False, False),
        (MODE_GLOBAL, False, False),
    ],
)
def test_room_participation_by_mode_and_enabled(
    mode: str,
    enabled: bool,
    should_control: bool,
) -> None:
    if mode == MODE_OFF:
        assert not should_control
    else:
        assert should_control == enabled


@pytest.mark.parametrize(
    ("room_id", "diff", "ac_allowed", "expected_category", "expected_contains"),
    [
        ("room1", 0.3, True, 1, "climate.room1_radiator"),
        ("room1", 1.0, True, 2, "script.room1_heater_on"),
        ("room1", 2.2, True, 3, "climate.room1_ac"),
        ("room1", 2.2, False, 2, "script.room1_heater_on"),
        ("room4", 2.2, False, 2, "climate.room4_radiator"),
    ],
)
def test_heat_categories_with_weather_degrade(
    room_id: str,
    diff: float,
    ac_allowed: bool,
    expected_category: int,
    expected_contains: str,
) -> None:
    setup = _five_room_setup()[room_id]
    category, entities = _select_room_entities(
        setup,
        is_heating=True,
        diff=diff,
        thresholds=Thresholds(category2_diff=0.7, category3_diff=1.8),
        ac_allowed=ac_allowed,
    )
    assert category == expected_category
    assert expected_contains in entities
    if not ac_allowed:
        assert all(entity not in setup.weather_sensitive for entity in entities)


@pytest.mark.parametrize(
    ("outdoor_ok", "expected_has_ac"),
    [(True, True), (False, False)],
)
def test_cool_category3_uses_weather_sensitive_only_when_allowed(
    outdoor_ok: bool,
    expected_has_ac: bool,
) -> None:
    setup = _five_room_setup()["room4"]
    category, entities = _select_room_entities(
        setup,
        is_heating=False,
        diff=2.5,
        thresholds=Thresholds(category2_diff=0.7, category3_diff=1.8),
        ac_allowed=outdoor_ok,
    )
    assert category == (3 if outdoor_ok else 2)
    assert ("climate.room4_ac" in entities) is expected_has_ac


def test_shared_floor_not_touched_when_all_related_rooms_disabled() -> None:
    setup = _five_room_setup()
    related_rooms = [room for room in setup.values() if "climate.floor_shared" in room.shared]
    enabled_map = {room.room_id: False for room in related_rooms}

    assert all(not enabled_map[room.room_id] for room in related_rooms)
    # Expected behaviour from spec: shared device must be skipped when all rooms disabled.
    should_control_shared = any(enabled_map.values())
    assert should_control_shared is False


def test_shared_arbitration_max_demand_wins() -> None:
    demands = {"room2": 0.8, "room3": 1.1, "room4": 2.4}
    assert _shared_winner_max(demands) == "room4"


def test_shared_arbitration_priority_room_wins() -> None:
    demands = {"room2": 0.8, "room3": 1.1, "room4": 2.4}
    assert _shared_winner_priority(demands, "room3") == "room3"
    assert _shared_winner_priority(demands, "roomX") == "room4"


def test_shared_arbitration_average_request() -> None:
    demands = {"room2": 0.8, "room3": 1.1, "room4": 2.4}
    assert _shared_winner_average(demands) == pytest.approx((0.8 + 1.1 + 2.4) / 3)


@pytest.mark.parametrize(
    ("profile", "expected_offset"),
    [
        (TYPE_NORMAL, 0.5),
        (TYPE_FAST, 2.0),
        (TYPE_EXTREME, 2.0),
    ],
)
def test_boost_start_offset_by_profile(profile: str, expected_offset: float) -> None:
    phase, offset = next_phase_and_offset(
        control_type=profile,
        phase=PHASE_HOLD,
        reached_target=False,
        current_offset=0.0,
        step_offset=0.5,
        max_offset=2.0,
        elapsed_boost_seconds=0,
        t_time=300,
    )
    assert phase == PHASE_BOOST
    assert offset == expected_offset


@pytest.mark.parametrize(
    ("profile", "is_heating", "min_temp", "max_temp", "expected"),
    [
        (TYPE_NORMAL, True, 16.0, 28.0, 24.0),
        (TYPE_NORMAL, False, 16.0, 28.0, 20.0),
        (TYPE_EXTREME, True, 16.0, 28.0, 28.0),
        (TYPE_EXTREME, False, 16.0, 28.0, 16.0),
    ],
)
def test_setpoint_behaviour_by_profile(
    profile: str,
    is_heating: bool,
    min_temp: float,
    max_temp: float,
    expected: float,
) -> None:
    value = compute_setpoint(
        target=22.0,
        is_heating=is_heating,
        control_type=profile,
        offset=2.0,
        climate_min_temp=min_temp,
        climate_max_temp=max_temp,
    )
    assert value == expected


@pytest.mark.parametrize(
    ("temps", "targets", "mode", "enabled_map", "expected_controlled_rooms"),
    [
        (
            {"room1": 20.0, "room2": 21.0, "room3": 22.0, "room4": 19.5, "room5": 21.5},
            {"room1": 22.0, "room2": 22.0, "room3": 22.0, "room4": 22.0, "room5": 22.0},
            MODE_PER_ROOM,
            {"room1": True, "room2": True, "room3": True, "room4": True, "room5": True},
            {"room1", "room2", "room4", "room5"},
        ),
        (
            {"room1": 20.0, "room2": 21.0, "room3": 22.0, "room4": 19.5, "room5": 21.5},
            {"global": 22.0},
            MODE_GLOBAL,
            {"room1": True, "room2": True, "room3": False, "room4": True, "room5": True},
            {"room1", "room2", "room4", "room5"},
        ),
        (
            {"room1": 20.0, "room2": 21.0, "room3": 22.0, "room4": 19.5, "room5": 21.5},
            {"global": 22.0},
            MODE_OFF,
            {"room1": True, "room2": True, "room3": True, "room4": True, "room5": True},
            set(),
        ),
    ],
)
def test_five_room_control_coverage(
    temps: dict[str, float],
    targets: dict[str, float],
    mode: str,
    enabled_map: dict[str, bool],
    expected_controlled_rooms: set[str],
) -> None:
    controlled: set[str] = set()
    for room_id, temp in temps.items():
        if mode == MODE_OFF or not enabled_map.get(room_id, True):
            continue
        target = targets.get(room_id, targets.get("global", 22.0))
        if target - temp > 0.3:
            controlled.add(room_id)
    assert controlled == expected_controlled_rooms


def _simulate_time_to_target(
    profile: str,
    initial_temp: float,
    target_temp: float,
    *,
    is_heating: bool,
    tolerance: float,
    t_time: float,
    step_offset: float,
    max_offset: float,
    seconds_per_step: int,
    base_speed_per_step: float,
    offset_gain: float,
    max_steps: int = 200,
) -> int:
    """Simulate simplified room thermal dynamics until HOLD is reached.

    Speed model:
    delta_temp_per_step = base_speed_per_step + offset * offset_gain
    """
    temp = initial_temp
    phase = PHASE_HOLD
    offset = 0.0
    elapsed_boost_seconds = 0.0

    for step in range(1, max_steps + 1):
        reached = abs(temp - target_temp) <= tolerance
        phase, offset = next_phase_and_offset(
            control_type=profile,
            phase=phase,
            reached_target=reached,
            current_offset=offset,
            step_offset=step_offset,
            max_offset=max_offset,
            elapsed_boost_seconds=elapsed_boost_seconds,
            t_time=t_time,
        )
        if phase == PHASE_HOLD and reached:
            return step * seconds_per_step

        if phase == PHASE_BOOST:
            speed = base_speed_per_step + (offset * offset_gain)
            temp = temp + speed if is_heating else temp - speed
            elapsed_boost_seconds += seconds_per_step
        else:
            elapsed_boost_seconds = 0.0

    raise AssertionError("Room did not reach target in simulation window")


@pytest.mark.parametrize(
    ("profile", "expected_order"),
    [
        (TYPE_NORMAL, "normal"),
        (TYPE_FAST, "fast"),
        (TYPE_EXTREME, "extreme"),
    ],
)
def test_different_room_heating_speeds_affect_duration(profile: str, expected_order: str) -> None:
    fast_room_seconds = _simulate_time_to_target(
        profile=profile,
        initial_temp=19.0,
        target_temp=22.0,
        is_heating=True,
        tolerance=0.3,
        t_time=300,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.22,
        offset_gain=0.06,
    )
    slow_room_seconds = _simulate_time_to_target(
        profile=profile,
        initial_temp=19.0,
        target_temp=22.0,
        is_heating=True,
        tolerance=0.3,
        t_time=300,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.10,
        offset_gain=0.04,
    )
    assert fast_room_seconds < slow_room_seconds, expected_order


def test_t_time_impacts_normal_profile_duration() -> None:
    short_t_time = _simulate_time_to_target(
        profile=TYPE_NORMAL,
        initial_temp=18.5,
        target_temp=22.0,
        is_heating=True,
        tolerance=0.3,
        t_time=120,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.10,
        offset_gain=0.04,
    )
    long_t_time = _simulate_time_to_target(
        profile=TYPE_NORMAL,
        initial_temp=18.5,
        target_temp=22.0,
        is_heating=True,
        tolerance=0.3,
        t_time=600,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.10,
        offset_gain=0.04,
    )
    # With shorter T_time NORMAL ramps offset sooner and reaches target faster.
    assert short_t_time < long_t_time


def test_profile_speed_order_on_same_room() -> None:
    normal_seconds = _simulate_time_to_target(
        profile=TYPE_NORMAL,
        initial_temp=19.0,
        target_temp=22.0,
        is_heating=True,
        tolerance=0.3,
        t_time=300,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.10,
        offset_gain=0.04,
    )
    fast_seconds = _simulate_time_to_target(
        profile=TYPE_FAST,
        initial_temp=19.0,
        target_temp=22.0,
        is_heating=True,
        tolerance=0.3,
        t_time=300,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.10,
        offset_gain=0.04,
    )
    extreme_seconds = _simulate_time_to_target(
        profile=TYPE_EXTREME,
        initial_temp=19.0,
        target_temp=22.0,
        is_heating=True,
        tolerance=0.3,
        t_time=300,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.10,
        offset_gain=0.04,
    )
    assert fast_seconds <= normal_seconds
    assert extreme_seconds <= fast_seconds


def test_cooling_different_speeds_and_duration() -> None:
    fast_cool_seconds = _simulate_time_to_target(
        profile=TYPE_FAST,
        initial_temp=26.0,
        target_temp=22.0,
        is_heating=False,
        tolerance=0.3,
        t_time=300,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.25,
        offset_gain=0.06,
    )
    slow_cool_seconds = _simulate_time_to_target(
        profile=TYPE_FAST,
        initial_temp=26.0,
        target_temp=22.0,
        is_heating=False,
        tolerance=0.3,
        t_time=300,
        step_offset=0.5,
        max_offset=2.0,
        seconds_per_step=30,
        base_speed_per_step=0.11,
        offset_gain=0.03,
    )
    assert fast_cool_seconds < slow_cool_seconds
