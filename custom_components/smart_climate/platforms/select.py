"""Select entities for Smart Climate."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from ..const import (
    DOMAIN,
    MODE_GLOBAL,
    MODE_OFF,
    MODE_PER_ROOM,
    TYPE_EXTREME,
    TYPE_FAST,
    TYPE_NORMAL,
)
from ..coordinator import SmartClimateCoordinator
from ..entity import SmartClimateEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SmartClimateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SmartClimateModeSelect(coordinator),
            SmartClimateTypeSelect(coordinator),
        ]
    )


class SmartClimateModeSelect(SmartClimateEntity, SelectEntity, RestoreEntity):
    """Mode selector."""

    _attr_name = "Mode"
    _attr_icon = "mdi:hvac"
    _attr_options = [MODE_OFF, MODE_PER_ROOM, MODE_GLOBAL]

    def __init__(self, coordinator: SmartClimateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_mode"

    @property
    def current_option(self) -> str:
        return self.coordinator.data.get("mode", MODE_PER_ROOM) if self.coordinator.data else MODE_PER_ROOM

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_mode(option)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self.options:
            await self.coordinator.async_set_mode(last_state.state)


class SmartClimateTypeSelect(SmartClimateEntity, SelectEntity, RestoreEntity):
    """Type selector."""

    _attr_name = "Type"
    _attr_icon = "mdi:rocket-launch"
    _attr_options = [TYPE_NORMAL, TYPE_FAST, TYPE_EXTREME]

    def __init__(self, coordinator: SmartClimateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_type"

    @property
    def current_option(self) -> str:
        return self.coordinator.data.get("type", TYPE_NORMAL) if self.coordinator.data else TYPE_NORMAL

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_type(option)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self.options:
            await self.coordinator.async_set_type(last_state.state)
