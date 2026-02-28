"""Smart Climate integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

try:
    from homeassistant.helpers import config_validation as cv

    CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
except ModuleNotFoundError:  # pragma: no cover - local unit tests run without Home Assistant deps
    CONFIG_SCHEMA = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Climate from a config entry."""
    from homeassistant.const import Platform

    from .coordinator import SmartClimateCoordinator

    platforms: list[Platform] = [
        Platform.SELECT,
        Platform.NUMBER,
        Platform.SWITCH,
        Platform.SENSOR,
    ]
    coordinator = SmartClimateCoordinator(hass, entry)
    await coordinator.async_initialize()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    _LOGGER.debug("Smart Climate entry %s initialized", entry.entry_id)
    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Smart Climate entry."""
    from homeassistant.const import Platform

    platforms: list[Platform] = [
        Platform.SELECT,
        Platform.NUMBER,
        Platform.SWITCH,
        Platform.SENSOR,
    ]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        from .coordinator import SmartClimateCoordinator

        coordinator: SmartClimateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok
