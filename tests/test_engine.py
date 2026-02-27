"""Unit tests for decision engine."""

from custom_components.smart_climate.const import PHASE_BOOST, PHASE_HOLD, TYPE_EXTREME, TYPE_FAST, TYPE_NORMAL
from custom_components.smart_climate.engine import (
    Thresholds,
    next_phase_and_offset,
    select_category,
)


def test_select_category_small_medium_big() -> None:
    thresholds = Thresholds(small=0.5, medium=1.5, big=3.0)

    assert select_category(0.2, thresholds, ac_allowed=True) == 1
    assert select_category(0.9, thresholds, ac_allowed=True) == 2
    assert select_category(2.1, thresholds, ac_allowed=True) == 3


def test_select_category_degrades_when_ac_forbidden() -> None:
    thresholds = Thresholds(small=0.5, medium=1.5, big=3.0)

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
