"""Switch entities for Smart Climate."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..coordinator import SmartClimateCoordinator
from ..entity import SmartClimateEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SmartClimateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RoomEnabledSwitch(coordinator, room_id) for room_id in coordinator.room_ids])


class RoomEnabledSwitch(SmartClimateEntity, SwitchEntity):
    """Enable/disable automation in a room."""

    _attr_icon = "mdi:toggle-switch"

    def __init__(self, coordinator: SmartClimateCoordinator, room_id: str) -> None:
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_name = f"{coordinator.room_name(room_id)} Enabled"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{room_id}_enabled"

    @property
    def is_on(self) -> bool:
        if self.coordinator.data:
            return bool(self.coordinator.data.get("rooms", {}).get(self._room_id, {}).get("enabled", True))
        return True

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_room_enabled(self._room_id, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_room_enabled(self._room_id, False)
