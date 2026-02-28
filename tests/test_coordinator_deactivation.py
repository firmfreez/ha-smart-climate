"""Behavior tests for room device deactivation logic."""

from __future__ import annotations

import asyncio
import sys
import types
from types import MethodType

if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    sys.modules["homeassistant.config_entries"] = config_entries

    const = types.ModuleType("homeassistant.const")
    const.ATTR_ENTITY_ID = "entity_id"
    const.STATE_UNAVAILABLE = "unavailable"
    const.STATE_UNKNOWN = "unknown"
    sys.modules["homeassistant.const"] = const

    core = types.ModuleType("homeassistant.core")
    core.Event = object
    core.HomeAssistant = object
    core.callback = lambda f: f
    sys.modules["homeassistant.core"] = core

    helpers = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers
    helpers_cv = types.ModuleType("homeassistant.helpers.config_validation")
    helpers_cv.config_entry_only_config_schema = lambda _domain: {}
    sys.modules["homeassistant.helpers.config_validation"] = helpers_cv

    helpers_debounce = types.ModuleType("homeassistant.helpers.debounce")
    helpers_debounce.Debouncer = object
    sys.modules["homeassistant.helpers.debounce"] = helpers_debounce

    helpers_event = types.ModuleType("homeassistant.helpers.event")
    helpers_event.async_track_state_change_event = lambda *_args, **_kwargs: (lambda: None)
    sys.modules["homeassistant.helpers.event"] = helpers_event

    helpers_update = types.ModuleType("homeassistant.helpers.update_coordinator")
    helpers_update.UpdateFailed = Exception

    class _DataUpdateCoordinator:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __class_getitem__(cls, _item):
            return cls

    helpers_update.DataUpdateCoordinator = _DataUpdateCoordinator
    sys.modules["homeassistant.helpers.update_coordinator"] = helpers_update

    util = types.ModuleType("homeassistant.util")
    sys.modules["homeassistant.util"] = util

    util_dt = types.ModuleType("homeassistant.util.dt")
    import datetime as _dt

    util_dt.utcnow = _dt.datetime.utcnow
    sys.modules["homeassistant.util.dt"] = util_dt

from custom_components.smart_climate.coordinator import SmartClimateCoordinator
from custom_components.smart_climate.models import DumbDeviceConfig, RoomConfig, RoomRuntime


def _make_coordinator_with_call_log(call_log: list[tuple[str, str, str]]) -> SmartClimateCoordinator:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)

    async def _fake_call(self, entity_id: str, domain: str, service: str) -> bool:
        call_log.append((entity_id, domain, service))
        return True

    coordinator._async_call_service_entity = MethodType(_fake_call, coordinator)  # type: ignore[attr-defined]
    return coordinator


def test_deactivate_non_active_turns_off_cross_mode_and_category_mismatch() -> None:
    calls: list[tuple[str, str, str]] = []
    coordinator = _make_coordinator_with_call_log(calls)
    room = RoomConfig(
        room_id="room",
        name="Room",
        temp_sensors=["sensor.room"],
        heat_category_1=["climate.heat1"],
        heat_category_2=["climate.dual"],
        cool_category_1=["climate.cool1"],
        cool_category_2=["climate.dual"],
        shared_climates=[],
    )

    asyncio.run(
        coordinator._async_deactivate_non_active_entities(
            room=room,
            runtime=RoomRuntime(),
            is_heating=True,
            category=1,
            ac_allowed=True,
        )
    )

    # Current active set on heating/category1 is only climate.heat1.
    assert ("climate.cool1", "climate", "turn_off") in calls
    # dual exists in both modes, but category2 is not active, so must also be turned off.
    assert ("climate.dual", "climate", "turn_off") in calls
    assert ("climate.heat1", "climate", "turn_off") not in calls


def test_deactivate_non_active_does_not_turn_off_shared_and_active_dumb() -> None:
    calls: list[tuple[str, str, str]] = []
    coordinator = _make_coordinator_with_call_log(calls)
    room = RoomConfig(
        room_id="room",
        name="Room",
        temp_sensors=["sensor.room"],
        heat_category_1=["climate.local_heat", "climate.shared_unit"],
        cool_category_1=["climate.local_cool", "climate.shared_unit"],
        shared_climates=["climate.shared_unit"],
        dumb_devices=[
            DumbDeviceConfig(
                on_script="script.dual_on",
                off_script="script.dual_off",
                device_type="heat",
                participation="until_reach_target",
                category=1,
            ),
            DumbDeviceConfig(
                on_script="script.dual_on",
                off_script="script.dual_off",
                device_type="cool",
                participation="until_reach_target",
                category=1,
            ),
            DumbDeviceConfig(
                on_script="script.cool_only_on",
                off_script="script.cool_only_off",
                device_type="cool",
                participation="until_reach_target",
                category=1,
            ),
        ],
    )

    asyncio.run(
        coordinator._async_deactivate_non_active_entities(
            room=room,
            runtime=RoomRuntime(),
            is_heating=True,
            category=1,
            ac_allowed=True,
        )
    )

    # Shared unit is excluded from forced turn_off in room-local logic.
    assert ("climate.shared_unit", "climate", "turn_off") not in calls
    # Opposite local climate must be turned off.
    assert ("climate.local_cool", "climate", "turn_off") in calls
    # dual dumb on_script is active in current mode, so off must not be called.
    assert ("script.dual_off", "script", "turn_on") not in calls
    # cool-only dumb device must be turned off.
    assert ("script.cool_only_off", "script", "turn_on") in calls
