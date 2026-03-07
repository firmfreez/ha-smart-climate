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

from custom_components.smart_climate.const import (
    CONF_AC_MISSING_OUTDOOR_POLICY,
    CONF_COOL_OUTDOOR_TARGET_DELTA,
    CONF_GLOBAL_TARGET,
    CONF_GLOBAL_TOLERANCE,
    CONF_HOLD_OFFSET_DECAY_STEP,
    CONF_HEAT_OUTDOOR_TARGET_DELTA,
    CONF_MAX_OFFSET,
    CONF_MODE,
    CONF_TYPE,
    CONF_OUTDOOR_MAX_FOR_WEATHER_SENSITIVE,
    CONF_OUTDOOR_MIN_FOR_WEATHER_SENSITIVE,
    CONF_PRIORITY_ROOM,
    CONF_STEP_OFFSET,
    CONF_T_TIME,
    MODE_OFF,
    MODE_PER_ROOM,
    PHASE_HOLD,
    OUTDOOR_POLICY_ALLOW,
    TYPE_EXTREME,
    TYPE_FAST,
    TYPE_NORMAL,
)
from custom_components.smart_climate.coordinator import SmartClimateCoordinator
from custom_components.smart_climate.models import DumbDeviceConfig, RoomConfig, RoomRuntime


def _make_coordinator_with_call_log(call_log: list[tuple[str, str, str]]) -> SmartClimateCoordinator:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)
    coordinator._managed_dumb_on_scripts = set()  # type: ignore[attr-defined]

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
    coordinator._managed_dumb_on_scripts = {  # type: ignore[attr-defined]
        "script.cool_only_on",
        "script.fireplace_on",
    }
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
            DumbDeviceConfig(
                on_script="script.fireplace_on",
                off_script="script.fireplace_off",
                device_type="heat",
                participation="until_reach_target",
                category=2,
                manage_off_script=False,
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
    # manually-managed off script must never be called by integration.
    assert ("script.fireplace_off", "script", "turn_on") not in calls


def test_deactivate_non_active_does_not_turn_off_unmanaged_dumb_devices() -> None:
    calls: list[tuple[str, str, str]] = []
    coordinator = _make_coordinator_with_call_log(calls)
    room = RoomConfig(
        room_id="room",
        name="Room",
        temp_sensors=["sensor.room"],
        dumb_devices=[
            DumbDeviceConfig(
                on_script="script.fireplace_on",
                off_script="script.fireplace_off",
                device_type="heat",
                participation="until_reach_target",
                category=1,
            ),
        ],
    )

    asyncio.run(
        coordinator._async_deactivate_non_active_entities(
            room=room,
            runtime=RoomRuntime(),
            is_heating=False,
            category=1,
            ac_allowed=True,
        )
    )

    # fireplace_on was never activated by Smart Climate, so off_script must not be called.
    assert ("script.fireplace_off", "script", "turn_on") not in calls


def test_shared_priority_room_reduces_setpoint_to_target_when_no_demand() -> None:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)
    room_id = "kitchen"
    climate_id = "climate.floor_shared"
    calls: list[dict[str, object]] = []

    coordinator._shared_map = {climate_id: [room_id]}  # type: ignore[attr-defined]
    coordinator._rooms = {room_id: RoomConfig(room_id=room_id, name="Kitchen")}  # type: ignore[attr-defined]
    coordinator._runtime = {  # type: ignore[attr-defined]
        room_id: RoomRuntime(
            enabled=True,
            current_temp=25.0,
            target_temp=25.0,
            tolerance=0.3,
            current_offset=2.0,
        )
    }

    coordinator._room_enabled = MethodType(lambda self, rid: rid == room_id, coordinator)  # type: ignore[attr-defined]
    coordinator._room_target = MethodType(lambda self, rid: 25.0, coordinator)  # type: ignore[attr-defined]
    coordinator._room_tolerance = MethodType(lambda self, rid: 0.3, coordinator)  # type: ignore[attr-defined]
    coordinator._opt = MethodType(  # type: ignore[attr-defined]
        lambda self, key: {"shared_arbitration": "priority_room", "priority_room": room_id, "type": "normal"}.get(key),
        coordinator,
    )

    async def _fake_set_climate(
        self,
        entity_id: str,
        target: float,
        is_heating: bool,
        control_type: str,
        offset: float,
        skip_hvac: bool = False,
        force_heat_mode: bool = False,
    ) -> dict[str, object]:
        calls.append(
            {
                "entity_id": entity_id,
                "target": target,
                "is_heating": is_heating,
                "control_type": control_type,
                "offset": offset,
                "skip_hvac": skip_hvac,
                "force_heat_mode": force_heat_mode,
            }
        )
        return {"sent": True, "active": True}

    coordinator._async_set_climate = MethodType(_fake_set_climate, coordinator)  # type: ignore[attr-defined]

    winners = asyncio.run(coordinator._async_apply_shared({}))

    assert calls
    call = calls[0]
    assert call["entity_id"] == climate_id
    assert call["target"] == 25.0
    # Within tolerance: should drop to target without extra offset and avoid hvac mode flip.
    assert call["offset"] == 0.0
    assert call["skip_hvac"] is True
    assert winners == {climate_id: room_id}


def test_apply_room_actions_forces_heat_mode_for_heat_only_climate() -> None:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)
    room = RoomConfig(
        room_id="room",
        name="Room",
        temp_sensors=["sensor.room"],
        cool_category_1=["climate.floor"],
        heat_only_climates=["climate.floor"],
    )
    runtime = RoomRuntime(target_temp=22.0, current_offset=0.5)
    calls: list[dict[str, object]] = []

    async def _fake_deactivate(self, *args, **kwargs) -> None:
        return None

    async def _fake_set_climate(
        self,
        entity_id: str,
        target: float,
        is_heating: bool,
        control_type: str,
        offset: float,
        skip_hvac: bool = False,
        force_heat_mode: bool = False,
    ) -> dict[str, object]:
        calls.append({"entity_id": entity_id, "force_heat_mode": force_heat_mode, "skip_hvac": skip_hvac})
        return {"sent": False, "active": True, "hvac_mode": "heat", "setpoint": target}

    coordinator._async_deactivate_non_active_entities = MethodType(_fake_deactivate, coordinator)  # type: ignore[attr-defined]
    coordinator._async_set_climate = MethodType(_fake_set_climate, coordinator)  # type: ignore[attr-defined]

    active = asyncio.run(
        coordinator._async_apply_room_actions(
            room=room,
            runtime=runtime,
            is_heating=False,
            category=1,
            control_type="normal",
            weather_sensitive_allowed=True,
        )
    )

    assert active == ["climate.floor"]
    assert calls and calls[0]["force_heat_mode"] is True


def test_shared_heat_only_climate_forces_heat_mode() -> None:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)
    room_id = "bedroom"
    climate_id = "climate.floor_shared"
    calls: list[dict[str, object]] = []

    coordinator._shared_map = {climate_id: [room_id]}  # type: ignore[attr-defined]
    coordinator._rooms = {  # type: ignore[attr-defined]
        room_id: RoomConfig(
            room_id=room_id,
            name="Bedroom",
            temp_sensors=["sensor.room"],
            shared_climates=[climate_id],
            heat_only_climates=[climate_id],
        )
    }
    coordinator._runtime = {  # type: ignore[attr-defined]
        room_id: RoomRuntime(enabled=True, current_temp=25.0, target_temp=22.0, tolerance=0.3),
    }
    coordinator._room_enabled = MethodType(lambda self, rid: rid == room_id, coordinator)  # type: ignore[attr-defined]
    coordinator._room_target = MethodType(lambda self, rid: 22.0, coordinator)  # type: ignore[attr-defined]
    coordinator._opt = MethodType(  # type: ignore[attr-defined]
        lambda self, key: {"shared_arbitration": "max_demand", "type": "normal", "step_offset": 0.5}.get(key, ""),
        coordinator,
    )

    async def _fake_set_climate(
        self,
        entity_id: str,
        target: float,
        is_heating: bool,
        control_type: str,
        offset: float,
        skip_hvac: bool = False,
        force_heat_mode: bool = False,
    ) -> dict[str, object]:
        calls.append({"entity_id": entity_id, "force_heat_mode": force_heat_mode})
        return {"sent": True, "active": True}

    coordinator._async_set_climate = MethodType(_fake_set_climate, coordinator)  # type: ignore[attr-defined]

    winners = asyncio.run(coordinator._async_apply_shared({climate_id: [(room_id, "cool", 2.0)]}))

    assert winners == {climate_id: room_id}
    assert calls and calls[0]["force_heat_mode"] is True


def test_weather_sensitive_allowed_uses_global_window_and_normal_heuristics() -> None:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)
    opts = {
        CONF_AC_MISSING_OUTDOOR_POLICY: OUTDOOR_POLICY_ALLOW,
        CONF_OUTDOOR_MIN_FOR_WEATHER_SENSITIVE: 0.0,
        CONF_OUTDOOR_MAX_FOR_WEATHER_SENSITIVE: 35.0,
        CONF_COOL_OUTDOOR_TARGET_DELTA: 2.0,
        CONF_HEAT_OUTDOOR_TARGET_DELTA: 2.0,
    }
    coordinator._opt = MethodType(lambda self, key: opts[key], coordinator)  # type: ignore[attr-defined]

    assert not coordinator._weather_sensitive_allowed(
        outdoor_temp=25.0,
        target=22.0,
        is_heating=True,
        control_type=TYPE_NORMAL,
    )
    assert coordinator._weather_sensitive_allowed(
        outdoor_temp=25.0,
        target=22.0,
        is_heating=True,
        control_type=TYPE_FAST,
    )
    assert coordinator._weather_sensitive_allowed(
        outdoor_temp=25.0,
        target=22.0,
        is_heating=True,
        control_type=TYPE_EXTREME,
    )

    assert not coordinator._weather_sensitive_allowed(
        outdoor_temp=20.0,
        target=22.0,
        is_heating=False,
        control_type=TYPE_NORMAL,
    )
    assert coordinator._weather_sensitive_allowed(
        outdoor_temp=20.0,
        target=22.0,
        is_heating=False,
        control_type=TYPE_FAST,
    )
    assert coordinator._weather_sensitive_allowed(
        outdoor_temp=20.0,
        target=22.0,
        is_heating=False,
        control_type=TYPE_EXTREME,
    )

    # Global outdoor window should block all profiles.
    assert not coordinator._weather_sensitive_allowed(
        outdoor_temp=-5.0,
        target=22.0,
        is_heating=False,
        control_type=TYPE_EXTREME,
    )


def test_resolve_priority_room_accepts_room_name_and_slug() -> None:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)
    coordinator._rooms = {  # type: ignore[attr-defined]
        "kuhnya": RoomConfig(room_id="kuhnya", name="Кухня"),
    }

    assert coordinator._resolve_priority_room_id("kuhnya") == "kuhnya"
    assert coordinator._resolve_priority_room_id("Кухня") == "kuhnya"
    assert coordinator._resolve_priority_room_id("kitchen") is None


def test_mode_off_turns_off_room_and_shared_devices_and_skips_shared_arbitration() -> None:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)
    room_id = "living"
    calls: list[tuple[str, str, str]] = []

    room = RoomConfig(
        room_id=room_id,
        name="Living",
        temp_sensors=["sensor.living"],
        heat_category_1=["climate.radiator", "climate.shared_floor"],
        shared_climates=["climate.shared_floor"],
        dumb_devices=[
            DumbDeviceConfig(
                on_script="script.fireplace_on",
                off_script="script.fireplace_off",
                device_type="heat",
                participation="until_reach_target",
                category=1,
            )
        ],
    )

    coordinator._rooms = {room_id: room}  # type: ignore[attr-defined]
    coordinator._runtime = {room_id: RoomRuntime(enabled=True)}  # type: ignore[attr-defined]
    coordinator._shared_map = {"climate.shared_floor": [room_id]}  # type: ignore[attr-defined]
    coordinator._managed_dumb_on_scripts = {"script.fireplace_on"}  # type: ignore[attr-defined]
    coordinator._opt = MethodType(lambda self, key: MODE_OFF if key == CONF_MODE else "normal", coordinator)  # type: ignore[attr-defined]
    coordinator._room_enabled = MethodType(lambda self, rid: True, coordinator)  # type: ignore[attr-defined]
    coordinator._room_target = MethodType(lambda self, rid: 22.0, coordinator)  # type: ignore[attr-defined]
    coordinator._room_tolerance = MethodType(lambda self, rid: 0.3, coordinator)  # type: ignore[attr-defined]
    coordinator._read_room_temperature = MethodType(lambda self, r: 22.0, coordinator)  # type: ignore[attr-defined]
    coordinator._read_outdoor_temp = MethodType(lambda self: None, coordinator)  # type: ignore[attr-defined]

    async def _fake_call(self, entity_id: str, domain: str, service: str) -> bool:
        calls.append((entity_id, domain, service))
        return True

    async def _fail_shared(self, demands):
        raise AssertionError("shared arbitration must not run in MODE_OFF")

    coordinator._async_call_service_entity = MethodType(_fake_call, coordinator)  # type: ignore[attr-defined]
    coordinator._async_apply_shared = MethodType(_fail_shared, coordinator)  # type: ignore[attr-defined]

    result = asyncio.run(coordinator._async_run_control_cycle())

    assert ("climate.radiator", "climate", "turn_off") in calls
    assert ("climate.shared_floor", "climate", "turn_off") in calls
    assert ("script.fireplace_off", "script", "turn_on") in calls
    assert result["shared_winner_rooms"] == {}


def test_hold_phase_keeps_climate_active_on_target() -> None:
    coordinator = SmartClimateCoordinator.__new__(SmartClimateCoordinator)
    room_id = "living"
    calls: list[dict[str, object]] = []

    room = RoomConfig(
        room_id=room_id,
        name="Living",
        temp_sensors=["sensor.living"],
        heat_category_1=["climate.radiator"],
    )
    coordinator._rooms = {room_id: room}  # type: ignore[attr-defined]
    coordinator._runtime = {  # type: ignore[attr-defined]
        room_id: RoomRuntime(
            enabled=True,
            current_temp=22.0,
            target_temp=22.0,
            tolerance=0.3,
            phase=PHASE_HOLD,
            current_offset=1.5,
            hold_is_heating=True,
        )
    }
    coordinator._shared_map = {}  # type: ignore[attr-defined]
    coordinator._managed_dumb_on_scripts = set()  # type: ignore[attr-defined]
    opts = {
        CONF_MODE: MODE_PER_ROOM,
        CONF_TYPE: TYPE_NORMAL,
        CONF_GLOBAL_TARGET: 22.0,
        CONF_GLOBAL_TOLERANCE: 0.3,
        CONF_HOLD_OFFSET_DECAY_STEP: 0.5,
        CONF_STEP_OFFSET: 0.5,
        CONF_MAX_OFFSET: 2.0,
        CONF_T_TIME: 300,
        CONF_PRIORITY_ROOM: "",
    }
    coordinator._opt = MethodType(lambda self, key: opts.get(key), coordinator)  # type: ignore[attr-defined]
    coordinator._room_enabled = MethodType(lambda self, rid: True, coordinator)  # type: ignore[attr-defined]
    coordinator._room_target = MethodType(lambda self, rid: 22.0, coordinator)  # type: ignore[attr-defined]
    coordinator._room_tolerance = MethodType(lambda self, rid: 0.3, coordinator)  # type: ignore[attr-defined]
    coordinator._read_room_temperature = MethodType(lambda self, r: 22.0, coordinator)  # type: ignore[attr-defined]
    coordinator._read_outdoor_temp = MethodType(lambda self: None, coordinator)  # type: ignore[attr-defined]
    coordinator._weather_sensitive_allowed = MethodType(lambda self, **kwargs: True, coordinator)  # type: ignore[attr-defined]

    async def _fake_apply_room_actions(
        self,
        room: RoomConfig,
        runtime: RoomRuntime,
        is_heating: bool,
        category: int,
        control_type: str,
        weather_sensitive_allowed: bool,
    ) -> list[str]:
        calls.append(
            {
                "is_heating": is_heating,
                "category": category,
                "control_type": control_type,
                "offset": runtime.current_offset,
            }
        )
        return ["climate.radiator"]

    async def _fake_apply_shared(self, demands):
        return {}

    coordinator._async_apply_room_actions = MethodType(_fake_apply_room_actions, coordinator)  # type: ignore[attr-defined]
    coordinator._async_apply_shared = MethodType(_fake_apply_shared, coordinator)  # type: ignore[attr-defined]

    result = asyncio.run(coordinator._async_run_control_cycle())

    assert calls
    assert calls[0]["is_heating"] is True
    assert calls[0]["category"] == 1
    assert calls[0]["offset"] == 1.5
    assert result["rooms"][room_id]["active_devices"] == ["climate.radiator"]
