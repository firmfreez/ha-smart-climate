"""Number entities for Smart Climate."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DEFAULT_GLOBAL_TARGET, DEFAULT_GLOBAL_TOLERANCE, DOMAIN
from ..coordinator import SmartClimateCoordinator
from ..entity import SmartClimateEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SmartClimateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [
        GlobalTargetNumber(coordinator),
        GlobalToleranceNumber(coordinator),
    ]
    for room_id in coordinator.room_ids:
        entities.append(RoomTargetNumber(coordinator, room_id))
        entities.append(RoomToleranceNumber(coordinator, room_id))

    async_add_entities(entities)


class BaseSmartClimateNumber(SmartClimateEntity, NumberEntity):
    """Base number entity with restore support."""

    _attr_native_min_value = 5.0
    _attr_native_max_value = 35.0
    _attr_native_step = 0.1


class GlobalTargetNumber(BaseSmartClimateNumber):
    """Global target temperature."""

    _attr_name = "Global Target"
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator: SmartClimateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_global_target"

    @property
    def native_value(self) -> float:
        if self.coordinator.data:
            return float(self.coordinator.data.get("global_target", DEFAULT_GLOBAL_TARGET))
        return DEFAULT_GLOBAL_TARGET

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_global_target(value)


class GlobalToleranceNumber(BaseSmartClimateNumber):
    """Global tolerance."""

    _attr_name = "Global Tolerance"
    _attr_icon = "mdi:tune"
    _attr_native_min_value = 0.1
    _attr_native_max_value = 5.0

    def __init__(self, coordinator: SmartClimateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_global_tolerance"

    @property
    def native_value(self) -> float:
        if self.coordinator.data:
            return float(self.coordinator.data.get("global_tolerance", DEFAULT_GLOBAL_TOLERANCE))
        return DEFAULT_GLOBAL_TOLERANCE

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_global_tolerance(value)


class RoomTargetNumber(BaseSmartClimateNumber):
    """Per-room target temperature."""

    _attr_icon = "mdi:home-thermometer"

    def __init__(self, coordinator: SmartClimateCoordinator, room_id: str) -> None:
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_name = f"{coordinator.room_name(room_id)} Target"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{room_id}_target"

    @property
    def native_value(self) -> float:
        if self.coordinator.data:
            room_data = self.coordinator.data.get("rooms", {}).get(self._room_id, {})
            return float(room_data.get("target_temp", DEFAULT_GLOBAL_TARGET))
        return DEFAULT_GLOBAL_TARGET

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_target(self._room_id, value)


class RoomToleranceNumber(BaseSmartClimateNumber):
    """Per-room tolerance."""

    _attr_icon = "mdi:tune-variant"
    _attr_native_min_value = 0.1
    _attr_native_max_value = 5.0

    def __init__(self, coordinator: SmartClimateCoordinator, room_id: str) -> None:
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_name = f"{coordinator.room_name(room_id)} Tolerance"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{room_id}_tolerance"

    @property
    def native_value(self) -> float:
        if self.coordinator.data:
            room_data = self.coordinator.data.get("rooms", {}).get(self._room_id, {})
            return float(room_data.get("tolerance", DEFAULT_GLOBAL_TOLERANCE))
        return DEFAULT_GLOBAL_TOLERANCE

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_tolerance(self._room_id, value)
