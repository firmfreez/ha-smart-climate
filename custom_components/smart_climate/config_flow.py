"""Config flow for Smart Climate."""

from __future__ import annotations

import json
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.util import slugify

from .const import (
    CONF_AC_MISSING_OUTDOOR_POLICY,
    CONF_AFTER_REACH_DUMB,
    CONF_AFTER_REACH_SMART,
    CONF_AGGREGATION,
    CONF_COOL_BIG,
    CONF_COOL_MEDIUM,
    CONF_COOL_SMALL,
    CONF_GLOBAL_TARGET,
    CONF_GLOBAL_TOLERANCE,
    CONF_HEAT_BIG,
    CONF_HEAT_MEDIUM,
    CONF_HEAT_SMALL,
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
    CONF_ROOM_DUMB_DEVICES,
    CONF_ROOM_ENABLED,
    CONF_ROOM_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_SENSORS,
    CONF_ROOMS,
    CONF_SHARED_ARBITRATION,
    CONF_STEP_OFFSET,
    CONF_T_TIME,
    CONF_TOLERANCE,
    CONF_TYPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AC_MISSING_OUTDOOR_POLICY,
    DEFAULT_AFTER_REACH_DUMB,
    DEFAULT_AFTER_REACH_SMART,
    DEFAULT_AGGREGATION,
    DEFAULT_COOL_BIG,
    DEFAULT_COOL_MEDIUM,
    DEFAULT_COOL_SMALL,
    DEFAULT_GLOBAL_TARGET,
    DEFAULT_GLOBAL_TOLERANCE,
    DEFAULT_HEAT_BIG,
    DEFAULT_HEAT_MEDIUM,
    DEFAULT_HEAT_SMALL,
    DEFAULT_MAX_OFFSET,
    DEFAULT_MAX_OUTDOOR_FOR_COOL,
    DEFAULT_MIN_ACTION_INTERVAL,
    DEFAULT_MIN_OUTDOOR_FOR_HEATPUMP,
    DEFAULT_MODE,
    DEFAULT_STEP_OFFSET,
    DEFAULT_T_TIME,
    DEFAULT_TOLERANCE,
    DEFAULT_TYPE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MODE_GLOBAL,
    MODE_OFF,
    MODE_PER_ROOM,
    OUTDOOR_POLICY_ALLOW,
    OUTDOOR_POLICY_BLOCK,
    OUTDOOR_SOURCE_NONE,
    OUTDOOR_SOURCE_SENSOR,
    OUTDOOR_SOURCE_WEATHER,
    TYPE_EXTREME,
    TYPE_FAST,
    TYPE_NORMAL,
)
from .coordinator import SmartClimateCoordinator


class SmartClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Climate."""

    VERSION = 1

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._rooms: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Initial step with global configuration."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            self._config = {
                CONF_OUTDOOR_SOURCE_TYPE: user_input[CONF_OUTDOOR_SOURCE_TYPE],
                CONF_OUTDOOR_WEATHER: user_input.get(CONF_OUTDOOR_WEATHER),
                CONF_OUTDOOR_SENSOR: user_input.get(CONF_OUTDOOR_SENSOR),
                CONF_AC_MISSING_OUTDOOR_POLICY: user_input[CONF_AC_MISSING_OUTDOOR_POLICY],
                CONF_AGGREGATION: user_input[CONF_AGGREGATION],
            }
            return await self.async_step_room()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_OUTDOOR_SOURCE_TYPE, default=OUTDOOR_SOURCE_NONE): SelectSelector(
                    SelectSelectorConfig(
                        options=[OUTDOOR_SOURCE_NONE, OUTDOOR_SOURCE_WEATHER, OUTDOOR_SOURCE_SENSOR],
                        mode="dropdown",
                    )
                ),
                vol.Optional(CONF_OUTDOOR_WEATHER): EntitySelector(
                    EntitySelectorConfig(domain="weather", multiple=False)
                ),
                vol.Optional(CONF_OUTDOOR_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor", multiple=False)
                ),
                vol.Required(
                    CONF_AC_MISSING_OUTDOOR_POLICY,
                    default=DEFAULT_AC_MISSING_OUTDOOR_POLICY,
                ): SelectSelector(
                    SelectSelectorConfig(options=[OUTDOOR_POLICY_BLOCK, OUTDOOR_POLICY_ALLOW], mode="dropdown")
                ),
                vol.Required(CONF_AGGREGATION, default=DEFAULT_AGGREGATION): SelectSelector(
                    SelectSelectorConfig(options=["average", "min", "max", "median", "first"], mode="dropdown")
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_room(self, user_input: dict[str, Any] | None = None):
        """Add rooms one by one."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                room_id = slugify(user_input[CONF_ROOM_NAME])
                dumb = SmartClimateCoordinator.parse_dumb_devices(user_input.get("dumb_devices_json", ""))
                room = {
                    CONF_ROOM_ID: room_id,
                    CONF_ROOM_NAME: user_input[CONF_ROOM_NAME],
                    CONF_ROOM_TEMP_SENSORS: user_input.get(CONF_ROOM_TEMP_SENSORS, []),
                    "primary_climates": user_input.get("primary_climates", []),
                    "ac_climates": user_input.get("ac_climates", []),
                    "shared_climates": user_input.get("shared_climates", []),
                    CONF_ROOM_DUMB_DEVICES: dumb,
                }
                if any(existing[CONF_ROOM_ID] == room_id for existing in self._rooms):
                    errors[CONF_ROOM_NAME] = "duplicate_room"
                else:
                    self._rooms.append(room)
                    if user_input.get("add_another_room", False):
                        return await self.async_step_room()

                    data = {
                        **self._config,
                        CONF_ROOMS: self._rooms,
                        CONF_MODE: DEFAULT_MODE,
                        CONF_TYPE: DEFAULT_TYPE,
                        CONF_GLOBAL_TARGET: DEFAULT_GLOBAL_TARGET,
                        CONF_GLOBAL_TOLERANCE: DEFAULT_GLOBAL_TOLERANCE,
                    }
                    return self.async_create_entry(title="Умный климат", data=data)
            except Exception:
                errors["base"] = "invalid_room_json"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ROOM_NAME): TextSelector(TextSelectorConfig()),
                vol.Required(CONF_ROOM_TEMP_SENSORS): EntitySelector(
                    EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Optional("primary_climates", default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional("ac_climates", default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional("shared_climates", default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional("dumb_devices_json", default=""): TextSelector(
                    TextSelectorConfig(multiline=True)
                ),
                vol.Required("add_another_room", default=False): bool,
            }
        )
        return self.async_show_form(step_id="room", data_schema=data_schema, errors=errors)

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SmartClimateOptionsFlow(config_entry)


class SmartClimateOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Smart Climate."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                per_room_targets = self._parse_json_map(user_input.get("per_room_targets_json", "{}"), float)
                per_room_tolerances = self._parse_json_map(user_input.get("per_room_tolerances_json", "{}"), float)
                room_enabled = self._parse_json_map(user_input.get("room_enabled_json", "{}"), bool)

                options = {
                    CONF_MODE: user_input[CONF_MODE],
                    CONF_TYPE: user_input[CONF_TYPE],
                    CONF_GLOBAL_TARGET: user_input[CONF_GLOBAL_TARGET],
                    CONF_GLOBAL_TOLERANCE: user_input[CONF_GLOBAL_TOLERANCE],
                    CONF_TOLERANCE: user_input[CONF_TOLERANCE],
                    CONF_T_TIME: int(user_input[CONF_T_TIME]),
                    CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL]),
                    CONF_MAX_OFFSET: user_input[CONF_MAX_OFFSET],
                    CONF_STEP_OFFSET: user_input[CONF_STEP_OFFSET],
                    CONF_MIN_ACTION_INTERVAL: int(user_input[CONF_MIN_ACTION_INTERVAL]),
                    CONF_HEAT_SMALL: user_input[CONF_HEAT_SMALL],
                    CONF_HEAT_MEDIUM: user_input[CONF_HEAT_MEDIUM],
                    CONF_HEAT_BIG: user_input[CONF_HEAT_BIG],
                    CONF_COOL_SMALL: user_input[CONF_COOL_SMALL],
                    CONF_COOL_MEDIUM: user_input[CONF_COOL_MEDIUM],
                    CONF_COOL_BIG: user_input[CONF_COOL_BIG],
                    CONF_MIN_OUTDOOR_FOR_HEATPUMP: user_input[CONF_MIN_OUTDOOR_FOR_HEATPUMP],
                    CONF_MAX_OUTDOOR_FOR_COOL: user_input[CONF_MAX_OUTDOOR_FOR_COOL],
                    CONF_AFTER_REACH_SMART: user_input[CONF_AFTER_REACH_SMART],
                    CONF_AFTER_REACH_DUMB: user_input[CONF_AFTER_REACH_DUMB],
                    CONF_SHARED_ARBITRATION: user_input[CONF_SHARED_ARBITRATION],
                    CONF_PRIORITY_ROOM: user_input.get(CONF_PRIORITY_ROOM, ""),
                    CONF_PER_ROOM_TARGETS: per_room_targets,
                    CONF_PER_ROOM_TOLERANCES: per_room_tolerances,
                    CONF_ROOM_ENABLED: room_enabled,
                }
                return self.async_create_entry(title="", data=options)
            except ValueError:
                errors["base"] = "invalid_json"

        options = self._entry.options
        schema = vol.Schema(
            {
                vol.Required(CONF_MODE, default=options.get(CONF_MODE, DEFAULT_MODE)): SelectSelector(
                    SelectSelectorConfig(options=[MODE_OFF, MODE_PER_ROOM, MODE_GLOBAL], mode="dropdown")
                ),
                vol.Required(CONF_TYPE, default=options.get(CONF_TYPE, DEFAULT_TYPE)): SelectSelector(
                    SelectSelectorConfig(options=[TYPE_NORMAL, TYPE_FAST, TYPE_EXTREME], mode="dropdown")
                ),
                vol.Required(
                    CONF_GLOBAL_TARGET, default=options.get(CONF_GLOBAL_TARGET, DEFAULT_GLOBAL_TARGET)
                ): NumberSelector(NumberSelectorConfig(min=5, max=35, step=0.1, mode=NumberSelectorMode.BOX)),
                vol.Required(
                    CONF_GLOBAL_TOLERANCE,
                    default=options.get(CONF_GLOBAL_TOLERANCE, DEFAULT_GLOBAL_TOLERANCE),
                ): NumberSelector(NumberSelectorConfig(min=0.1, max=5, step=0.1, mode=NumberSelectorMode.BOX)),
                vol.Required(CONF_TOLERANCE, default=options.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=5, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_T_TIME, default=options.get(CONF_T_TIME, DEFAULT_T_TIME)): NumberSelector(
                    NumberSelectorConfig(min=30, max=3600, step=10, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_UPDATE_INTERVAL, default=options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                ): NumberSelector(NumberSelectorConfig(min=10, max=600, step=5, mode=NumberSelectorMode.BOX)),
                vol.Required(CONF_MAX_OFFSET, default=options.get(CONF_MAX_OFFSET, DEFAULT_MAX_OFFSET)): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_STEP_OFFSET, default=options.get(CONF_STEP_OFFSET, DEFAULT_STEP_OFFSET)): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=5, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_MIN_ACTION_INTERVAL,
                    default=options.get(CONF_MIN_ACTION_INTERVAL, DEFAULT_MIN_ACTION_INTERVAL),
                ): NumberSelector(NumberSelectorConfig(min=5, max=600, step=5, mode=NumberSelectorMode.BOX)),
                vol.Required(CONF_HEAT_SMALL, default=options.get(CONF_HEAT_SMALL, DEFAULT_HEAT_SMALL)): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_HEAT_MEDIUM, default=options.get(CONF_HEAT_MEDIUM, DEFAULT_HEAT_MEDIUM)
                ): NumberSelector(NumberSelectorConfig(min=0.1, max=15, step=0.1, mode=NumberSelectorMode.BOX)),
                vol.Required(CONF_HEAT_BIG, default=options.get(CONF_HEAT_BIG, DEFAULT_HEAT_BIG)): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=20, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_COOL_SMALL, default=options.get(CONF_COOL_SMALL, DEFAULT_COOL_SMALL)): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_COOL_MEDIUM, default=options.get(CONF_COOL_MEDIUM, DEFAULT_COOL_MEDIUM)
                ): NumberSelector(NumberSelectorConfig(min=0.1, max=15, step=0.1, mode=NumberSelectorMode.BOX)),
                vol.Required(CONF_COOL_BIG, default=options.get(CONF_COOL_BIG, DEFAULT_COOL_BIG)): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=20, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(
                    CONF_MIN_OUTDOOR_FOR_HEATPUMP,
                    default=options.get(CONF_MIN_OUTDOOR_FOR_HEATPUMP, DEFAULT_MIN_OUTDOOR_FOR_HEATPUMP),
                ): NumberSelector(NumberSelectorConfig(min=-40, max=30, step=0.5, mode=NumberSelectorMode.BOX)),
                vol.Required(
                    CONF_MAX_OUTDOOR_FOR_COOL,
                    default=options.get(CONF_MAX_OUTDOOR_FOR_COOL, DEFAULT_MAX_OUTDOOR_FOR_COOL),
                ): NumberSelector(NumberSelectorConfig(min=10, max=60, step=0.5, mode=NumberSelectorMode.BOX)),
                vol.Required(
                    CONF_AFTER_REACH_SMART,
                    default=options.get(CONF_AFTER_REACH_SMART, DEFAULT_AFTER_REACH_SMART),
                ): SelectSelector(
                    SelectSelectorConfig(options=["keep_on", "set_target", "turn_off"], mode="dropdown")
                ),
                vol.Required(
                    CONF_AFTER_REACH_DUMB,
                    default=options.get(CONF_AFTER_REACH_DUMB, DEFAULT_AFTER_REACH_DUMB),
                ): SelectSelector(
                    SelectSelectorConfig(options=["keep_on", "set_target", "turn_off"], mode="dropdown")
                ),
                vol.Required(CONF_SHARED_ARBITRATION, default=options.get(CONF_SHARED_ARBITRATION, "max_demand")): SelectSelector(
                    SelectSelectorConfig(options=["max_demand", "priority_room", "average_request"], mode="dropdown")
                ),
                vol.Optional(CONF_PRIORITY_ROOM, default=options.get(CONF_PRIORITY_ROOM, "")): TextSelector(
                    TextSelectorConfig()
                ),
                vol.Optional(
                    "per_room_targets_json",
                    default=json.dumps(options.get(CONF_PER_ROOM_TARGETS, {}), ensure_ascii=False),
                ): TextSelector(TextSelectorConfig(multiline=True)),
                vol.Optional(
                    "per_room_tolerances_json",
                    default=json.dumps(options.get(CONF_PER_ROOM_TOLERANCES, {}), ensure_ascii=False),
                ): TextSelector(TextSelectorConfig(multiline=True)),
                vol.Optional(
                    "room_enabled_json",
                    default=json.dumps(options.get(CONF_ROOM_ENABLED, {}), ensure_ascii=False),
                ): TextSelector(TextSelectorConfig(multiline=True)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    @staticmethod
    def _parse_json_map(raw: str, cast: type) -> dict[str, Any]:
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            raise ValueError("json map expected")
        result: dict[str, Any] = {}
        for key, value in data.items():
            if cast is bool:
                if isinstance(value, bool):
                    result[str(key)] = value
                elif isinstance(value, str):
                    result[str(key)] = value.strip().lower() in ("1", "true", "on", "yes")
                else:
                    result[str(key)] = bool(value)
            else:
                result[str(key)] = cast(value)
        return result
