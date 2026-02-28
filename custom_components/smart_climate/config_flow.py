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
    CONF_COOL_CATEGORY2_DIFF,
    CONF_COOL_CATEGORY3_DIFF,
    CONF_COOL_MEDIUM,
    CONF_COOL_SMALL,
    CONF_GLOBAL_TARGET,
    CONF_GLOBAL_TOLERANCE,
    CONF_HEAT_BIG,
    CONF_HEAT_CATEGORY2_DIFF,
    CONF_HEAT_CATEGORY3_DIFF,
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
    DEFAULT_AC_MISSING_OUTDOOR_POLICY,
    DEFAULT_AFTER_REACH_DUMB,
    DEFAULT_AFTER_REACH_SMART,
    DEFAULT_AGGREGATION,
    DEFAULT_COOL_BIG,
    DEFAULT_COOL_CATEGORY2_DIFF,
    DEFAULT_COOL_CATEGORY3_DIFF,
    DEFAULT_COOL_MEDIUM,
    DEFAULT_COOL_SMALL,
    DEFAULT_GLOBAL_TARGET,
    DEFAULT_GLOBAL_TOLERANCE,
    DEFAULT_HEAT_BIG,
    DEFAULT_HEAT_CATEGORY2_DIFF,
    DEFAULT_HEAT_CATEGORY3_DIFF,
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
    OUTDOOR_POLICY_ALLOW,
    OUTDOOR_POLICY_BLOCK,
    OUTDOOR_SOURCE_NONE,
    OUTDOOR_SOURCE_SENSOR,
    OUTDOOR_SOURCE_WEATHER,
)
from .dumb import parse_dumb_devices_json


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
                        options=[
                            {"value": OUTDOOR_SOURCE_NONE, "label": "No source"},
                            {"value": OUTDOOR_SOURCE_WEATHER, "label": "Weather entity"},
                            {"value": OUTDOOR_SOURCE_SENSOR, "label": "Temperature sensor"},
                        ],
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
                    SelectSelectorConfig(
                        options=[
                            {"value": OUTDOOR_POLICY_BLOCK, "label": "Block weather-sensitive devices"},
                            {"value": OUTDOOR_POLICY_ALLOW, "label": "Allow weather-sensitive devices"},
                        ],
                        mode="dropdown",
                    )
                ),
                vol.Required(CONF_AGGREGATION, default=DEFAULT_AGGREGATION): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "average", "label": "Average"},
                            {"value": "min", "label": "Minimum"},
                            {"value": "max", "label": "Maximum"},
                            {"value": "median", "label": "Median"},
                            {"value": "first", "label": "First sensor"},
                        ],
                        mode="dropdown",
                    )
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
                dumb_devices = parse_dumb_devices_json(user_input.get("dumb_devices_json", ""))
                room = {
                    CONF_ROOM_ID: room_id,
                    CONF_ROOM_NAME: user_input[CONF_ROOM_NAME],
                    CONF_ROOM_TEMP_SENSORS: user_input.get(CONF_ROOM_TEMP_SENSORS, []),
                    CONF_ROOM_HEAT_CATEGORY_1: user_input.get(CONF_ROOM_HEAT_CATEGORY_1, []),
                    CONF_ROOM_HEAT_CATEGORY_2: user_input.get(CONF_ROOM_HEAT_CATEGORY_2, []),
                    CONF_ROOM_HEAT_CATEGORY_3: user_input.get(CONF_ROOM_HEAT_CATEGORY_3, []),
                    CONF_ROOM_COOL_CATEGORY_1: user_input.get(CONF_ROOM_COOL_CATEGORY_1, []),
                    CONF_ROOM_COOL_CATEGORY_2: user_input.get(CONF_ROOM_COOL_CATEGORY_2, []),
                    CONF_ROOM_COOL_CATEGORY_3: user_input.get(CONF_ROOM_COOL_CATEGORY_3, []),
                    CONF_ROOM_WEATHER_SENSITIVE_CLIMATES: user_input.get(
                        CONF_ROOM_WEATHER_SENSITIVE_CLIMATES, []
                    ),
                    CONF_ROOM_SHARED_CLIMATES: user_input.get(CONF_ROOM_SHARED_CLIMATES, []),
                    CONF_ROOM_DUMB_DEVICES: dumb_devices,
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
                vol.Optional(CONF_ROOM_HEAT_CATEGORY_1, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_HEAT_CATEGORY_2, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_HEAT_CATEGORY_3, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_COOL_CATEGORY_1, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_COOL_CATEGORY_2, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_COOL_CATEGORY_3, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_WEATHER_SENSITIVE_CLIMATES, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_SHARED_CLIMATES, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional("dumb_devices_json", default=""): TextSelector(TextSelectorConfig(multiline=True)),
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
        self._selected_room_id: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        rooms = self._current_rooms()
        menu_options = ["settings", "add_room"]
        if rooms:
            menu_options.extend(["edit_room_select", "delete_room_select"])
        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            options = dict(self._entry.options)
            options.update(
                {
                    CONF_TOLERANCE: user_input[CONF_TOLERANCE],
                    CONF_T_TIME: int(user_input[CONF_T_TIME]),
                    CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL]),
                    CONF_MAX_OFFSET: user_input[CONF_MAX_OFFSET],
                    CONF_STEP_OFFSET: user_input[CONF_STEP_OFFSET],
                    CONF_MIN_ACTION_INTERVAL: int(user_input[CONF_MIN_ACTION_INTERVAL]),
                    CONF_HEAT_SMALL: user_input[CONF_HEAT_SMALL],
                    CONF_HEAT_MEDIUM: user_input[CONF_HEAT_MEDIUM],
                    CONF_HEAT_BIG: user_input[CONF_HEAT_BIG],
                    CONF_HEAT_CATEGORY2_DIFF: user_input[CONF_HEAT_CATEGORY2_DIFF],
                    CONF_HEAT_CATEGORY3_DIFF: user_input[CONF_HEAT_CATEGORY3_DIFF],
                    CONF_COOL_SMALL: user_input[CONF_COOL_SMALL],
                    CONF_COOL_MEDIUM: user_input[CONF_COOL_MEDIUM],
                    CONF_COOL_BIG: user_input[CONF_COOL_BIG],
                    CONF_COOL_CATEGORY2_DIFF: user_input[CONF_COOL_CATEGORY2_DIFF],
                    CONF_COOL_CATEGORY3_DIFF: user_input[CONF_COOL_CATEGORY3_DIFF],
                    CONF_MIN_OUTDOOR_FOR_HEATPUMP: user_input[CONF_MIN_OUTDOOR_FOR_HEATPUMP],
                    CONF_MAX_OUTDOOR_FOR_COOL: user_input[CONF_MAX_OUTDOOR_FOR_COOL],
                    CONF_AFTER_REACH_SMART: user_input[CONF_AFTER_REACH_SMART],
                    CONF_AFTER_REACH_DUMB: user_input[CONF_AFTER_REACH_DUMB],
                    CONF_SHARED_ARBITRATION: user_input[CONF_SHARED_ARBITRATION],
                    CONF_PRIORITY_ROOM: user_input.get(CONF_PRIORITY_ROOM, ""),
                }
            )
            self._sanitize_room_dependent_options(options, set(self._room_ids()))
            return self.async_create_entry(title="", data=options)

        options = self._entry.options
        schema = vol.Schema(
            {
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
                vol.Required(
                    CONF_HEAT_CATEGORY2_DIFF,
                    default=options.get(CONF_HEAT_CATEGORY2_DIFF, DEFAULT_HEAT_CATEGORY2_DIFF),
                ): NumberSelector(NumberSelectorConfig(min=0.1, max=15, step=0.1, mode=NumberSelectorMode.BOX)),
                vol.Required(
                    CONF_HEAT_CATEGORY3_DIFF,
                    default=options.get(CONF_HEAT_CATEGORY3_DIFF, DEFAULT_HEAT_CATEGORY3_DIFF),
                ): NumberSelector(NumberSelectorConfig(min=0.1, max=20, step=0.1, mode=NumberSelectorMode.BOX)),
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
                    CONF_COOL_CATEGORY2_DIFF,
                    default=options.get(CONF_COOL_CATEGORY2_DIFF, DEFAULT_COOL_CATEGORY2_DIFF),
                ): NumberSelector(NumberSelectorConfig(min=0.1, max=15, step=0.1, mode=NumberSelectorMode.BOX)),
                vol.Required(
                    CONF_COOL_CATEGORY3_DIFF,
                    default=options.get(CONF_COOL_CATEGORY3_DIFF, DEFAULT_COOL_CATEGORY3_DIFF),
                ): NumberSelector(NumberSelectorConfig(min=0.1, max=20, step=0.1, mode=NumberSelectorMode.BOX)),
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
                    SelectSelectorConfig(
                        options=[
                            {"value": "keep_on", "label": "Keep on"},
                            {"value": "set_target", "label": "Set target"},
                            {"value": "turn_off", "label": "Turn off"},
                        ],
                        mode="dropdown",
                    )
                ),
                vol.Required(
                    CONF_AFTER_REACH_DUMB,
                    default=options.get(CONF_AFTER_REACH_DUMB, DEFAULT_AFTER_REACH_DUMB),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "keep_on", "label": "Keep on"},
                            {"value": "set_target", "label": "Set target"},
                            {"value": "turn_off", "label": "Turn off"},
                        ],
                        mode="dropdown",
                    )
                ),
                vol.Required(CONF_SHARED_ARBITRATION, default=options.get(CONF_SHARED_ARBITRATION, "max_demand")): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": "max_demand", "label": "Max demand wins"},
                            {"value": "priority_room", "label": "Priority room"},
                            {"value": "average_request", "label": "Average request"},
                        ],
                        mode="dropdown",
                    )
                ),
                vol.Optional(CONF_PRIORITY_ROOM, default=options.get(CONF_PRIORITY_ROOM, "")): TextSelector(
                    TextSelectorConfig()
                ),
            }
        )

        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_add_room(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        rooms = self._current_rooms()
        if user_input is not None:
            try:
                room_id = slugify(user_input[CONF_ROOM_NAME])
                if any(existing[CONF_ROOM_ID] == room_id for existing in rooms):
                    errors[CONF_ROOM_NAME] = "duplicate_room"
                else:
                    room = self._build_room_payload(user_input, room_id=room_id)
                    rooms.append(room)
                    return self._create_entry_with_rooms(rooms)
            except Exception:
                errors["base"] = "invalid_room_json"

        return self.async_show_form(
            step_id="add_room",
            data_schema=self._room_schema(),
            errors=errors,
        )

    async def async_step_edit_room_select(self, user_input: dict[str, Any] | None = None):
        rooms = self._current_rooms()
        if not rooms:
            return self.async_abort(reason="no_rooms")

        room_ids = {room[CONF_ROOM_ID] for room in rooms}
        if user_input is not None:
            selected = user_input["room_id"]
            if selected in room_ids:
                self._selected_room_id = selected
                return await self.async_step_edit_room()

        schema = vol.Schema(
            {
                vol.Required("room_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": room[CONF_ROOM_ID], "label": room[CONF_ROOM_NAME]} for room in rooms],
                        mode="dropdown",
                    )
                )
            }
        )
        return self.async_show_form(step_id="edit_room_select", data_schema=schema)

    async def async_step_edit_room(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        rooms = self._current_rooms()
        selected = self._selected_room_id
        room = next((item for item in rooms if item[CONF_ROOM_ID] == selected), None)
        if room is None:
            return self.async_abort(reason="room_not_found")

        if user_input is not None:
            try:
                updated = self._build_room_payload(user_input, room_id=room[CONF_ROOM_ID])
                updated_rooms = [
                    updated if item[CONF_ROOM_ID] == room[CONF_ROOM_ID] else item
                    for item in rooms
                ]
                return self._create_entry_with_rooms(updated_rooms)
            except Exception:
                errors["base"] = "invalid_room_json"

        return self.async_show_form(
            step_id="edit_room",
            data_schema=self._room_schema(room),
            errors=errors,
        )

    async def async_step_delete_room_select(self, user_input: dict[str, Any] | None = None):
        rooms = self._current_rooms()
        if not rooms:
            return self.async_abort(reason="no_rooms")

        room_ids = {room[CONF_ROOM_ID] for room in rooms}
        if user_input is not None:
            selected = user_input["room_id"]
            if selected in room_ids:
                self._selected_room_id = selected
                return await self.async_step_delete_room_confirm()

        schema = vol.Schema(
            {
                vol.Required("room_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": room[CONF_ROOM_ID], "label": room[CONF_ROOM_NAME]} for room in rooms],
                        mode="dropdown",
                    )
                )
            }
        )
        return self.async_show_form(step_id="delete_room_select", data_schema=schema)

    async def async_step_delete_room_confirm(self, user_input: dict[str, Any] | None = None):
        rooms = self._current_rooms()
        selected = self._selected_room_id
        room = next((item for item in rooms if item[CONF_ROOM_ID] == selected), None)
        if room is None:
            return self.async_abort(reason="room_not_found")

        if user_input is not None:
            if user_input.get("confirm_delete", False):
                updated_rooms = [item for item in rooms if item[CONF_ROOM_ID] != room[CONF_ROOM_ID]]
                return self._create_entry_with_rooms(updated_rooms)
            return self.async_abort(reason="delete_cancelled")

        schema = vol.Schema(
            {
                vol.Required("confirm_delete", default=False): bool,
            }
        )
        return self.async_show_form(step_id="delete_room_confirm", data_schema=schema)

    def _create_entry_with_rooms(self, rooms: list[dict[str, Any]]) -> config_entries.ConfigFlowResult:
        options = dict(self._entry.options)
        options[CONF_ROOMS] = rooms
        self._sanitize_room_dependent_options(options, {room[CONF_ROOM_ID] for room in rooms})
        return self.async_create_entry(title="", data=options)

    def _room_ids(self) -> list[str]:
        return [room[CONF_ROOM_ID] for room in self._current_rooms()]

    def _current_rooms(self) -> list[dict[str, Any]]:
        merged = {**self._entry.data, **self._entry.options}
        rooms_data = merged.get(CONF_ROOMS, [])
        return [dict(room) for room in rooms_data]

    @staticmethod
    def _build_room_payload(user_input: dict[str, Any], room_id: str) -> dict[str, Any]:
        dumb_devices = parse_dumb_devices_json(user_input.get("dumb_devices_json", ""))
        return {
            CONF_ROOM_ID: room_id,
            CONF_ROOM_NAME: user_input[CONF_ROOM_NAME],
            CONF_ROOM_TEMP_SENSORS: user_input.get(CONF_ROOM_TEMP_SENSORS, []),
            CONF_ROOM_HEAT_CATEGORY_1: user_input.get(CONF_ROOM_HEAT_CATEGORY_1, []),
            CONF_ROOM_HEAT_CATEGORY_2: user_input.get(CONF_ROOM_HEAT_CATEGORY_2, []),
            CONF_ROOM_HEAT_CATEGORY_3: user_input.get(CONF_ROOM_HEAT_CATEGORY_3, []),
            CONF_ROOM_COOL_CATEGORY_1: user_input.get(CONF_ROOM_COOL_CATEGORY_1, []),
            CONF_ROOM_COOL_CATEGORY_2: user_input.get(CONF_ROOM_COOL_CATEGORY_2, []),
            CONF_ROOM_COOL_CATEGORY_3: user_input.get(CONF_ROOM_COOL_CATEGORY_3, []),
            CONF_ROOM_WEATHER_SENSITIVE_CLIMATES: user_input.get(CONF_ROOM_WEATHER_SENSITIVE_CLIMATES, []),
            CONF_ROOM_SHARED_CLIMATES: user_input.get(CONF_ROOM_SHARED_CLIMATES, []),
            CONF_ROOM_DUMB_DEVICES: dumb_devices,
        }

    @staticmethod
    def _room_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
        room = defaults or {}
        return vol.Schema(
            {
                vol.Required(CONF_ROOM_NAME, default=room.get(CONF_ROOM_NAME, "")): TextSelector(TextSelectorConfig()),
                vol.Required(
                    CONF_ROOM_TEMP_SENSORS,
                    default=room.get(CONF_ROOM_TEMP_SENSORS, []),
                ): EntitySelector(EntitySelectorConfig(domain="sensor", multiple=True)),
                vol.Optional(CONF_ROOM_HEAT_CATEGORY_1, default=room.get(CONF_ROOM_HEAT_CATEGORY_1, [])): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_HEAT_CATEGORY_2, default=room.get(CONF_ROOM_HEAT_CATEGORY_2, [])): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_HEAT_CATEGORY_3, default=room.get(CONF_ROOM_HEAT_CATEGORY_3, [])): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_COOL_CATEGORY_1, default=room.get(CONF_ROOM_COOL_CATEGORY_1, [])): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_COOL_CATEGORY_2, default=room.get(CONF_ROOM_COOL_CATEGORY_2, [])): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_ROOM_COOL_CATEGORY_3, default=room.get(CONF_ROOM_COOL_CATEGORY_3, [])): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(
                    CONF_ROOM_WEATHER_SENSITIVE_CLIMATES,
                    default=room.get(CONF_ROOM_WEATHER_SENSITIVE_CLIMATES, []),
                ): EntitySelector(EntitySelectorConfig(domain="climate", multiple=True)),
                vol.Optional(CONF_ROOM_SHARED_CLIMATES, default=room.get(CONF_ROOM_SHARED_CLIMATES, [])): EntitySelector(
                    EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(
                    "dumb_devices_json",
                    default=json.dumps(room.get(CONF_ROOM_DUMB_DEVICES, []), ensure_ascii=False),
                ): TextSelector(TextSelectorConfig(multiline=True)),
            }
        )

    @staticmethod
    def _sanitize_room_dependent_options(options: dict[str, Any], room_ids: set[str]) -> None:
        for key in (CONF_PER_ROOM_TARGETS, CONF_PER_ROOM_TOLERANCES, CONF_ROOM_ENABLED):
            value = options.get(key)
            if not isinstance(value, dict):
                options[key] = {}
                continue
            options[key] = {room_id: item for room_id, item in value.items() if room_id in room_ids}

        priority = options.get(CONF_PRIORITY_ROOM, "")
        if priority and priority not in room_ids:
            options[CONF_PRIORITY_ROOM] = ""

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
