"""Select platform shim for Home Assistant loader."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .platforms.select import async_setup_entry as _async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Forward select platform setup to implementation module."""
    await _async_setup_entry(hass, entry, async_add_entities)
