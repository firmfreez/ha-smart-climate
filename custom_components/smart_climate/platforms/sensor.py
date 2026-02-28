"""Sensor entities for Smart Climate."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    entities: list[SensorEntity] = [OutdoorTempSensor(coordinator)]

    for room_id in coordinator.room_ids:
        entities.append(RoomCurrentTempSensor(coordinator, room_id))
        entities.append(RoomPhaseSensor(coordinator, room_id))

    async_add_entities(entities)


class RoomCurrentTempSensor(SmartClimateEntity, SensorEntity):
    """Current aggregated room temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:home-thermometer-outline"

    def __init__(self, coordinator: SmartClimateCoordinator, room_id: str) -> None:
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_name = f"{coordinator.room_name(room_id)} Current Temp"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{room_id}_current_temp"

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        room = self.coordinator.data.get("rooms", {}).get(self._room_id, {})
        value = room.get("current_temp")
        return float(value) if value is not None else None


class RoomPhaseSensor(SmartClimateEntity, SensorEntity):
    """Room control phase sensor."""

    _attr_translation_key = "room_phase"
    _attr_icon = "mdi:state-machine"

    def __init__(self, coordinator: SmartClimateCoordinator, room_id: str) -> None:
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_name = f"{coordinator.room_name(room_id)} Phase"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{room_id}_phase"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        room = self.coordinator.data.get("rooms", {}).get(self._room_id, {})
        if not room.get("enabled", True):
            return "disabled"
        return room.get("phase")

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        if not self.coordinator.data:
            return {}
        room = self.coordinator.data.get("rooms", {}).get(self._room_id, {})
        active_devices = room.get("active_devices", [])
        return {
            "phase_reason": room.get("phase_reason"),
            "demand": room.get("demand"),
            "demand_delta": room.get("demand_delta"),
            "current_temp": room.get("current_temp"),
            "target_temp": room.get("target_temp"),
            "tolerance": room.get("tolerance"),
            "active_devices_count": len(active_devices) if isinstance(active_devices, list) else 0,
            "active_devices": active_devices,
        }


class OutdoorTempSensor(SmartClimateEntity, SensorEntity):
    """Outdoor temperature from selected source."""

    _attr_name = "Outdoor Temp"
    _attr_icon = "mdi:thermometer-chevron-down"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SmartClimateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_outdoor_temp"

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get("outdoor_temp")
        return float(value) if value is not None else None
