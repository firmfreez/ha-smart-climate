"""Coordinator and control loop for Smart Climate."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AC_MISSING_OUTDOOR_POLICY,
    CONF_AGGREGATION,
    CONF_COOL_BIG,
    CONF_COOL_CATEGORY2_DIFF,
    CONF_COOL_CATEGORY3_DIFF,
    CONF_COOL_MEDIUM,
    CONF_DELTA,
    CONF_GLOBAL_TARGET,
    CONF_GLOBAL_TOLERANCE,
    CONF_HEAT_BIG,
    CONF_HEAT_CATEGORY2_DIFF,
    CONF_HEAT_CATEGORY3_DIFF,
    CONF_HEAT_MEDIUM,
    CONF_MAX_OFFSET,
    CONF_MAX_OUTDOOR_FOR_COOL,
    CONF_MIN_ACTION_INTERVAL,
    CONF_MIN_OUTDOOR_FOR_HEATPUMP,
    CONF_MODE,
    CONF_OUTDOOR_SENSOR,
    CONF_OUTDOOR_SOURCE_TYPE,
    CONF_OUTDOOR_WEATHER,
    CONF_PER_ROOM_TARGETS,
    CONF_PER_ROOM_TOLERANCES,
    CONF_PRIORITY_ROOM,
    CONF_ROOM_COOL_CATEGORY_1,
    CONF_ROOM_COOL_CATEGORY_2,
    CONF_ROOM_COOL_CATEGORY_3,
    CONF_ROOM_DUMB_DEVICES,
    CONF_ROOM_ENABLED,
    CONF_ROOM_HEAT_CATEGORY_1,
    CONF_ROOM_HEAT_CATEGORY_2,
    CONF_ROOM_HEAT_CATEGORY_3,
    CONF_ROOM_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_SHARED_CLIMATES,
    CONF_ROOM_TEMP_SENSORS,
    CONF_ROOM_WEATHER_SENSITIVE_CLIMATES,
    CONF_ROOMS,
    CONF_SHARED_ARBITRATION,
    CONF_STEP_OFFSET,
    CONF_T_TIME,
    CONF_TOLERANCE,
    CONF_TYPE,
    CONF_UPDATE_INTERVAL,
    COORDINATOR_DEBOUNCE_SECONDS,
    DEFAULT_UPDATE_INTERVAL,
    DUMB_DEFAULT_CATEGORY,
    DUMB_PARTICIPATION_OFF,
    DUMB_PARTICIPATION_UNTIL_TARGET,
    MODE_GLOBAL,
    MODE_OFF,
    OPTIONS_DEFAULTS,
    OUTDOOR_POLICY_BLOCK,
    OUTDOOR_SOURCE_SENSOR,
    OUTDOOR_SOURCE_WEATHER,
    PHASE_BOOST,
    PHASE_HOLD,
    PHASE_IDLE,
    UPDATE_FAILED_WARNING,
)
from .engine import (
    Thresholds,
    aggregate_temperature,
    compute_setpoint,
    filter_weather_sensitive,
    merge_categories,
    mode_hvac,
    next_phase_and_offset,
    select_category,
    should_activate_dumb_device,
    should_reenter_boost,
    within_target,
)
from .models import DeviceActionState, DumbDeviceConfig, RoomConfig, RoomRuntime

_LOGGER = logging.getLogger(__name__)


class SmartClimateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central coordinator for Smart Climate logic."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="smart_climate",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=COORDINATOR_DEBOUNCE_SECONDS,
                immediate=False,
            ),
        )
        self.config_entry = entry
        self._lock = asyncio.Lock()
        self._unsub_listeners: list[callback] = []

        self._rooms: dict[str, RoomConfig] = {}
        self._runtime: dict[str, RoomRuntime] = {}
        self._device_state: dict[str, DeviceActionState] = defaultdict(DeviceActionState)
        self._shared_map: dict[str, list[str]] = defaultdict(list)
        self._overrides: dict[str, Any] = {
            CONF_PER_ROOM_TARGETS: {},
            CONF_PER_ROOM_TOLERANCES: {},
            CONF_ROOM_ENABLED: {},
        }

    async def async_initialize(self) -> None:
        """Initialize static structures and listeners."""
        self._load_configuration()
        self._setup_listeners()

    async def async_shutdown(self) -> None:
        """Release listeners."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    def _load_configuration(self) -> None:
        merged = {**self.config_entry.data, **self.config_entry.options}
        rooms_data: list[dict[str, Any]] = merged.get(CONF_ROOMS, [])

        self._rooms.clear()
        self._shared_map.clear()

        for room_data in rooms_data:
            legacy_heat_cat1 = room_data.get("primary_climates", [])
            legacy_heat_cat3 = room_data.get("ac_climates", [])
            legacy_heat_cat2: list[str] = []
            legacy_cool_cat2: list[str] = []
            dumb_entries = room_data.get(CONF_ROOM_DUMB_DEVICES, room_data.get("dumb_devices", []))
            dumb_devices: list[DumbDeviceConfig] = []
            for dumb in dumb_entries:
                on_script = dumb.get("on_script")
                off_script = dumb.get("off_script")
                device_type = dumb.get("device_type")
                participation = dumb.get("participation", DUMB_PARTICIPATION_UNTIL_TARGET)
                category = int(dumb.get("category", DUMB_DEFAULT_CATEGORY))
                if not on_script or not off_script:
                    continue
                dumb_devices.append(
                    DumbDeviceConfig(
                        on_script=on_script,
                        off_script=off_script,
                        device_type=device_type,
                        participation=participation,
                        category=category,
                    )
                )
                if device_type == "heat":
                    legacy_heat_cat2.append(on_script)
                elif device_type == "cool":
                    legacy_cool_cat2.append(on_script)
            room = RoomConfig(
                room_id=room_data[CONF_ROOM_ID],
                name=room_data[CONF_ROOM_NAME],
                temp_sensors=room_data.get(CONF_ROOM_TEMP_SENSORS, []),
                heat_category_1=room_data.get(CONF_ROOM_HEAT_CATEGORY_1, legacy_heat_cat1),
                heat_category_2=room_data.get(CONF_ROOM_HEAT_CATEGORY_2, legacy_heat_cat2),
                heat_category_3=room_data.get(CONF_ROOM_HEAT_CATEGORY_3, legacy_heat_cat3),
                cool_category_1=room_data.get(CONF_ROOM_COOL_CATEGORY_1, []),
                cool_category_2=room_data.get(CONF_ROOM_COOL_CATEGORY_2, legacy_cool_cat2),
                cool_category_3=room_data.get(CONF_ROOM_COOL_CATEGORY_3, []),
                weather_sensitive_climates=room_data.get(CONF_ROOM_WEATHER_SENSITIVE_CLIMATES, legacy_heat_cat3),
                dumb_devices=dumb_devices,
                shared_climates=room_data.get(CONF_ROOM_SHARED_CLIMATES, room_data.get("shared_climates", [])),
            )
            self._rooms[room.room_id] = room
            self._runtime.setdefault(room.room_id, RoomRuntime())

            for climate_id in room.shared_climates:
                self._shared_map[climate_id].append(room.room_id)

        self._sync_update_interval()

    def _setup_listeners(self) -> None:
        entities: set[str] = set()
        for room in self._rooms.values():
            entities.update(room.temp_sensors)

        outdoor_type = self._opt(CONF_OUTDOOR_SOURCE_TYPE)
        if outdoor_type == OUTDOOR_SOURCE_WEATHER:
            weather_entity = self._opt(CONF_OUTDOOR_WEATHER)
            if weather_entity:
                entities.add(weather_entity)
        elif outdoor_type == OUTDOOR_SOURCE_SENSOR:
            sensor_entity = self._opt(CONF_OUTDOOR_SENSOR)
            if sensor_entity:
                entities.add(sensor_entity)

        if not entities:
            return

        @callback
        def _async_state_changed(_event: Event) -> None:
            self.async_request_refresh()

        self._unsub_listeners.append(
            async_track_state_change_event(self.hass, list(entities), _async_state_changed)
        )

    def _opt(self, key: str) -> Any:
        if override := self._overrides.get(key):
            return override
        if key in self.config_entry.options:
            return self.config_entry.options[key]
        if key in self.config_entry.data:
            return self.config_entry.data[key]
        return OPTIONS_DEFAULTS.get(key)

    def _room_target(self, room_id: str) -> float:
        mode = self._opt(CONF_MODE)
        per_room = self._overrides[CONF_PER_ROOM_TARGETS]
        if room_id in per_room:
            return float(per_room[room_id])

        per_room_options = self._opt(CONF_PER_ROOM_TARGETS) or {}
        if room_id in per_room_options:
            return float(per_room_options[room_id])

        if mode == MODE_GLOBAL:
            return float(self._opt(CONF_GLOBAL_TARGET))
        return float(self._opt(CONF_GLOBAL_TARGET))

    def _room_tolerance(self, room_id: str) -> float:
        mode = self._opt(CONF_MODE)
        per_room = self._overrides[CONF_PER_ROOM_TOLERANCES]
        if room_id in per_room:
            return float(per_room[room_id])

        per_room_options = self._opt(CONF_PER_ROOM_TOLERANCES) or {}
        if room_id in per_room_options:
            return float(per_room_options[room_id])

        if mode == MODE_GLOBAL:
            return float(self._opt(CONF_GLOBAL_TOLERANCE))
        return float(self._opt(CONF_TOLERANCE))

    def _room_enabled(self, room_id: str) -> bool:
        override = self._overrides[CONF_ROOM_ENABLED]
        if room_id in override:
            return bool(override[room_id])
        stored = self._opt(CONF_ROOM_ENABLED) or {}
        return bool(stored.get(room_id, True))

    def _sync_update_interval(self) -> None:
        self.update_interval = timedelta(seconds=int(self._opt(CONF_UPDATE_INTERVAL)))

    @staticmethod
    def _room_has_capability(room: RoomConfig, is_heating: bool) -> bool:
        if is_heating:
            category_entities = merge_categories(
                room.heat_category_1, room.heat_category_2, room.heat_category_3, 3
            )
        else:
            category_entities = merge_categories(
                room.cool_category_1, room.cool_category_2, room.cool_category_3, 3
            )

        has_room_entities = any(
            not (entity_id.startswith("climate.") and entity_id in room.shared_climates)
            for entity_id in category_entities
        )
        if has_room_entities:
            return True

        target_type = "heat" if is_heating else "cool"
        return any(
            dumb.device_type == target_type and dumb.participation != DUMB_PARTICIPATION_OFF
            for dumb in room.dumb_devices
        )

    def _persist_option(self, key: str, value: Any) -> None:
        options = dict(self.config_entry.options)
        if options.get(key) == value:
            return
        options[key] = value
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

    def _persist_option_map_value(self, key: str, map_key: str, value: Any) -> None:
        options = dict(self.config_entry.options)
        current_raw = options.get(key, {})
        current_map = dict(current_raw) if isinstance(current_raw, dict) else {}
        if current_map.get(map_key) == value:
            return
        current_map[map_key] = value
        options[key] = current_map
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

    async def async_set_mode(self, value: str) -> None:
        self._overrides[CONF_MODE] = value
        self._persist_option(CONF_MODE, value)
        await self.async_request_refresh()

    async def async_set_type(self, value: str) -> None:
        self._overrides[CONF_TYPE] = value
        self._persist_option(CONF_TYPE, value)
        await self.async_request_refresh()

    async def async_set_global_target(self, value: float) -> None:
        self._overrides[CONF_GLOBAL_TARGET] = value
        self._persist_option(CONF_GLOBAL_TARGET, value)
        await self.async_request_refresh()

    async def async_set_global_tolerance(self, value: float) -> None:
        self._overrides[CONF_GLOBAL_TOLERANCE] = value
        self._persist_option(CONF_GLOBAL_TOLERANCE, value)
        await self.async_request_refresh()

    async def async_set_room_enabled(self, room_id: str, value: bool) -> None:
        self._overrides[CONF_ROOM_ENABLED][room_id] = value
        self._persist_option_map_value(CONF_ROOM_ENABLED, room_id, value)
        await self.async_request_refresh()

    async def async_set_room_target(self, room_id: str, value: float) -> None:
        self._overrides[CONF_PER_ROOM_TARGETS][room_id] = value
        self._persist_option_map_value(CONF_PER_ROOM_TARGETS, room_id, value)
        await self.async_request_refresh()

    async def async_set_room_tolerance(self, room_id: str, value: float) -> None:
        self._overrides[CONF_PER_ROOM_TOLERANCES][room_id] = value
        self._persist_option_map_value(CONF_PER_ROOM_TOLERANCES, room_id, value)
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        self._sync_update_interval()
        async with self._lock:
            try:
                return await self._async_run_control_cycle()
            except Exception as err:
                raise UpdateFailed(UPDATE_FAILED_WARNING) from err

    async def _async_run_control_cycle(self) -> dict[str, Any]:
        mode = self._opt(CONF_MODE)
        control_type = self._opt(CONF_TYPE)
        outdoor_temp = self._read_outdoor_temp()
        room_payload: dict[str, Any] = {}
        shared_demands: dict[str, list[tuple[str, str, float]]] = defaultdict(list)

        for room_id, room in self._rooms.items():
            runtime = self._runtime[room_id]
            phase_reason: str | None = None
            demand = "none"
            demand_delta = 0.0
            runtime.enabled = self._room_enabled(room_id)
            runtime.target_temp = self._room_target(room_id)
            runtime.tolerance = self._room_tolerance(room_id)
            runtime.current_temp = self._read_room_temperature(room)
            runtime.active_devices = []
            runtime.active_category_heat = 0
            runtime.active_category_cool = 0

            if runtime.current_temp is None:
                _LOGGER.debug("Room %s has no valid temp sensors", room_id)
                runtime.enabled = False
                runtime.phase = PHASE_IDLE
                phase_reason = "no_temperature"
                room_payload[room_id] = self._room_payload(
                    room,
                    runtime,
                    phase_reason=phase_reason,
                    demand=demand,
                    demand_delta=demand_delta,
                )
                continue

            if mode == MODE_OFF or not runtime.enabled:
                runtime.phase = PHASE_IDLE
                phase_reason = "mode_off" if mode == MODE_OFF else "room_disabled"
                room_payload[room_id] = self._room_payload(
                    room,
                    runtime,
                    phase_reason=phase_reason,
                    demand=demand,
                    demand_delta=demand_delta,
                )
                continue

            target = runtime.target_temp
            tolerance = runtime.tolerance
            diff_heat = target - runtime.current_temp
            diff_cool = runtime.current_temp - target
            heat_needed = diff_heat > tolerance
            cool_needed = diff_cool > tolerance
            reached = within_target(runtime.current_temp, target, tolerance)

            if runtime.phase == PHASE_HOLD and not reached:
                if heat_needed:
                    if should_reenter_boost(
                        runtime.current_temp,
                        target,
                        tolerance,
                        float(self._opt(CONF_DELTA)),
                        is_heating=True,
                    ):
                        runtime.phase = PHASE_BOOST
                elif cool_needed:
                    if should_reenter_boost(
                        runtime.current_temp,
                        target,
                        tolerance,
                        float(self._opt(CONF_DELTA)),
                        is_heating=False,
                    ):
                        runtime.phase = PHASE_BOOST

            if runtime.phase == PHASE_BOOST and runtime.boost_started_at is None:
                runtime.boost_started_at = dt_util.utcnow()

            elapsed = 0.0
            if runtime.boost_started_at is not None:
                elapsed = (dt_util.utcnow() - runtime.boost_started_at).total_seconds()

            runtime.phase, runtime.current_offset = next_phase_and_offset(
                control_type=control_type,
                phase=runtime.phase,
                reached_target=reached,
                current_offset=runtime.current_offset,
                step_offset=float(self._opt(CONF_STEP_OFFSET)),
                max_offset=float(self._opt(CONF_MAX_OFFSET)),
                elapsed_boost_seconds=elapsed,
                t_time=float(self._opt(CONF_T_TIME)),
            )

            if runtime.phase == PHASE_HOLD:
                runtime.last_reach_time = dt_util.utcnow()
                runtime.boost_started_at = None

            if heat_needed:
                demand = "heat"
                demand_delta = diff_heat
                if not self._room_has_capability(room, is_heating=True):
                    phase_reason = "no_heating_devices"
                category = select_category(
                    diff_heat,
                    Thresholds(
                        float(self._opt(CONF_HEAT_CATEGORY2_DIFF) or self._opt(CONF_HEAT_MEDIUM)),
                        float(self._opt(CONF_HEAT_CATEGORY3_DIFF) or self._opt(CONF_HEAT_BIG)),
                    ),
                    True,
                )
                runtime.active_category_heat = category
                runtime.active_devices = await self._async_apply_room_actions(
                    room,
                    runtime,
                    is_heating=True,
                    category=category,
                    control_type=control_type,
                )
                if phase_reason is None and not runtime.active_devices:
                    phase_reason = "no_devices_activated"
                for shared in room.shared_climates:
                    shared_demands[shared].append((room_id, "heat", diff_heat))

            elif cool_needed:
                demand = "cool"
                demand_delta = diff_cool
                if not self._room_has_capability(room, is_heating=False):
                    phase_reason = "no_cooling_devices"
                category = select_category(
                    diff_cool,
                    Thresholds(
                        float(self._opt(CONF_COOL_CATEGORY2_DIFF) or self._opt(CONF_COOL_MEDIUM)),
                        float(self._opt(CONF_COOL_CATEGORY3_DIFF) or self._opt(CONF_COOL_BIG)),
                    ),
                    True,
                )
                runtime.active_category_cool = category
                runtime.active_devices = await self._async_apply_room_actions(
                    room,
                    runtime,
                    is_heating=False,
                    category=category,
                    control_type=control_type,
                )
                if phase_reason is None and not runtime.active_devices:
                    phase_reason = "no_devices_activated"
                for shared in room.shared_climates:
                    shared_demands[shared].append((room_id, "cool", diff_cool))

            elif runtime.phase == PHASE_HOLD:
                await self._async_apply_after_reach(room, runtime)

            room_payload[room_id] = self._room_payload(
                room,
                runtime,
                phase_reason=phase_reason,
                demand=demand,
                demand_delta=demand_delta,
            )

        await self._async_apply_shared(shared_demands)

        return {
            "mode": self._opt(CONF_MODE),
            "type": self._opt(CONF_TYPE),
            "global_target": self._opt(CONF_GLOBAL_TARGET),
            "global_tolerance": self._opt(CONF_GLOBAL_TOLERANCE),
            "outdoor_temp": outdoor_temp,
            "rooms": room_payload,
        }

    def _read_room_temperature(self, room: RoomConfig) -> float | None:
        values: list[float] = []
        for entity_id in room.temp_sensors:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                continue
            try:
                values.append(float(state.state))
            except ValueError:
                continue
        return aggregate_temperature(values, str(self._opt(CONF_AGGREGATION)))

    def _read_outdoor_temp(self) -> float | None:
        source_type = self._opt(CONF_OUTDOOR_SOURCE_TYPE)
        entity_id: str | None = None
        if source_type == OUTDOOR_SOURCE_WEATHER:
            entity_id = self._opt(CONF_OUTDOOR_WEATHER)
        elif source_type == OUTDOOR_SOURCE_SENSOR:
            entity_id = self._opt(CONF_OUTDOOR_SENSOR)

        if not entity_id:
            return None

        state = self.hass.states.get(entity_id)
        if state is None:
            return None

        if source_type == OUTDOOR_SOURCE_WEATHER:
            value = state.attributes.get("temperature")
            if value is None:
                return None
            return float(value)

        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None

        try:
            return float(state.state)
        except ValueError:
            return None

    def _ac_allowed(self, outdoor_temp: float | None, is_heating: bool) -> bool:
        if outdoor_temp is None:
            return self._opt(CONF_AC_MISSING_OUTDOOR_POLICY) != OUTDOOR_POLICY_BLOCK

        if is_heating:
            return outdoor_temp >= float(self._opt(CONF_MIN_OUTDOOR_FOR_HEATPUMP))
        return outdoor_temp <= float(self._opt(CONF_MAX_OUTDOOR_FOR_COOL))

    async def _async_apply_room_actions(
        self,
        room: RoomConfig,
        runtime: RoomRuntime,
        is_heating: bool,
        category: int,
        control_type: str,
    ) -> list[str]:
        active: list[str] = []
        ac_allowed = self._ac_allowed(self._read_outdoor_temp(), is_heating)

        if is_heating:
            category_entities = merge_categories(
                room.heat_category_1, room.heat_category_2, room.heat_category_3, category
            )
        else:
            category_entities = merge_categories(
                room.cool_category_1, room.cool_category_2, room.cool_category_3, category
            )

        for entity_id in filter_weather_sensitive(
            category_entities,
            set(room.weather_sensitive_climates),
            ac_allowed,
        ):
            if entity_id.startswith("climate."):
                if entity_id in room.shared_climates:
                    continue
                if await self._async_set_climate(
                    entity_id,
                    target=float(runtime.target_temp),
                    is_heating=is_heating,
                    control_type=control_type,
                    offset=runtime.current_offset,
                ):
                    active.append(entity_id)
            elif entity_id.startswith("script."):
                if await self._async_call_service_entity(entity_id, "script", "turn_on"):
                    active.append(entity_id)

        for dumb in room.dumb_devices:
            if not should_activate_dumb_device(
                room_category=category,
                device_category=dumb.category,
                room_is_heating=is_heating,
                device_type=dumb.device_type,
                participation=dumb.participation,
            ):
                continue
            if await self._async_call_service_entity(dumb.on_script, "script", "turn_on"):
                active.append(dumb.on_script)

        return active

    async def _async_apply_after_reach(self, room: RoomConfig, _runtime: RoomRuntime) -> None:
        all_climates = {
            entity_id
            for entity_id in merge_categories(
                room.heat_category_1, room.heat_category_2, room.heat_category_3, 3
            )
            + merge_categories(room.cool_category_1, room.cool_category_2, room.cool_category_3, 3)
            if entity_id.startswith("climate.")
        }

        for climate_entity in all_climates:
            if climate_entity in room.shared_climates:
                continue
            await self._async_call_service_entity(climate_entity, "climate", "turn_off")

        for dumb in room.dumb_devices:
            if dumb.participation == DUMB_PARTICIPATION_OFF:
                continue
            await self._async_call_service_entity(dumb.off_script, "script", "turn_on")

    async def _async_apply_shared(self, demands: dict[str, list[tuple[str, str, float]]]) -> None:
        strategy = self._opt(CONF_SHARED_ARBITRATION)
        priority_room = self._opt(CONF_PRIORITY_ROOM)

        for climate_entity, climate_demands in demands.items():
            involved_rooms = [
                room_id
                for room_id in self._shared_map.get(climate_entity, [])
                if self._room_enabled(room_id)
                and room_id in self._runtime
                and self._runtime[room_id].current_temp is not None
            ]
            if not involved_rooms:
                _LOGGER.debug("Skip shared %s: all rooms disabled", climate_entity)
                continue

            if strategy == "priority_room" and priority_room:
                selected = next((d for d in climate_demands if d[0] == priority_room), None)
                if selected is None:
                    continue
            elif strategy == "average_request":
                heat = [d for d in climate_demands if d[1] == "heat"]
                cool = [d for d in climate_demands if d[1] == "cool"]
                if len(heat) >= len(cool):
                    avg = sum(item[2] for item in heat) / max(len(heat), 1)
                    selected = ("avg", "heat", avg)
                else:
                    avg = sum(item[2] for item in cool) / max(len(cool), 1)
                    selected = ("avg", "cool", avg)
            else:
                selected = max(climate_demands, key=lambda item: item[2])

            is_heating = selected[1] == "heat"
            target = max(self._room_target(room_id) for room_id in involved_rooms)
            if not is_heating:
                target = min(self._room_target(room_id) for room_id in involved_rooms)

            await self._async_set_climate(
                climate_entity,
                target=target,
                is_heating=is_heating,
                control_type=self._opt(CONF_TYPE),
                offset=float(self._opt(CONF_STEP_OFFSET)),
            )

    async def _async_set_climate(
        self,
        entity_id: str,
        target: float,
        is_heating: bool,
        control_type: str,
        offset: float,
        skip_hvac: bool = False,
    ) -> bool:
        if not self._can_act(entity_id):
            return False

        state = self.hass.states.get(entity_id)
        if state is None:
            return False

        action_sent = False
        hvac_modes = state.attributes.get("hvac_modes", [])
        hvac_mode = mode_hvac(is_heating)
        if not skip_hvac and hvac_mode in hvac_modes and state.state != hvac_mode:
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {ATTR_ENTITY_ID: entity_id, "hvac_mode": hvac_mode},
                blocking=False,
            )
            action_sent = True

        climate_min = state.attributes.get("min_temp")
        climate_max = state.attributes.get("max_temp")
        setpoint = compute_setpoint(
            target=target,
            is_heating=is_heating,
            control_type=control_type,
            offset=offset,
            climate_min_temp=float(climate_min) if climate_min is not None else None,
            climate_max_temp=float(climate_max) if climate_max is not None else None,
        )
        current_setpoint = state.attributes.get("temperature")
        if current_setpoint is None:
            should_set_temp = True
        else:
            try:
                should_set_temp = abs(float(current_setpoint) - setpoint) > 0.05
            except (TypeError, ValueError):
                should_set_temp = True
        if should_set_temp:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: entity_id, "temperature": setpoint},
                blocking=False,
            )
            action_sent = True

        if action_sent:
            self._device_state[entity_id].last_action_time = dt_util.utcnow()
        return action_sent

    async def _async_call_service_entity(self, entity_id: str, domain: str, service: str) -> bool:
        if not self._can_act(entity_id):
            return False

        state = self.hass.states.get(entity_id)
        if domain == "climate" and service == "turn_off" and state is not None and state.state == "off":
            return False

        await self.hass.services.async_call(
            domain,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=False,
        )
        self._device_state[entity_id].last_action_time = dt_util.utcnow()
        return True

    def _can_act(self, entity_id: str) -> bool:
        state = self._device_state[entity_id]
        min_action = int(self._opt(CONF_MIN_ACTION_INTERVAL))
        if state.last_action_time is None:
            return True
        return (dt_util.utcnow() - state.last_action_time) >= timedelta(seconds=min_action)

    def _room_payload(
        self,
        room: RoomConfig,
        runtime: RoomRuntime,
        *,
        phase_reason: str | None = None,
        demand: str = "none",
        demand_delta: float = 0.0,
    ) -> dict[str, Any]:
        return {
            "name": room.name,
            "enabled": runtime.enabled,
            "current_temp": runtime.current_temp,
            "target_temp": runtime.target_temp,
            "tolerance": runtime.tolerance,
            "phase": runtime.phase,
            "phase_reason": phase_reason,
            "demand": demand,
            "demand_delta": demand_delta,
            "offset": runtime.current_offset,
            "active_category_heat": runtime.active_category_heat,
            "active_category_cool": runtime.active_category_cool,
            "active_devices": runtime.active_devices,
            "heat_category_1": room.heat_category_1,
            "heat_category_2": room.heat_category_2,
            "heat_category_3": room.heat_category_3,
            "cool_category_1": room.cool_category_1,
            "cool_category_2": room.cool_category_2,
            "cool_category_3": room.cool_category_3,
            "weather_sensitive_climates": room.weather_sensitive_climates,
            "dumb_devices": [
                {
                    "on_script": dumb.on_script,
                    "off_script": dumb.off_script,
                    "device_type": dumb.device_type,
                    "participation": dumb.participation,
                    "category": dumb.category,
                }
                for dumb in room.dumb_devices
            ],
            "shared_climates": room.shared_climates,
        }

    @property
    def room_ids(self) -> list[str]:
        """Expose room ids for entity platforms."""
        return list(self._rooms.keys())

    def room_name(self, room_id: str) -> str:
        """Return room display name."""
        room = self._rooms.get(room_id)
        return room.name if room else room_id
