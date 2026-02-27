"""Base entity for Smart Climate."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartClimateCoordinator


class SmartClimateEntity(CoordinatorEntity[SmartClimateCoordinator]):
    """Common base for Smart Climate entities."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name="Умный климат",
            manufacturer="Custom",
            model="Smart Climate Controller",
        )
