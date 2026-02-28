"""Utilities for script-based (dumb) devices."""

from __future__ import annotations

import json
from typing import Any

from .const import (
    DUMB_DEFAULT_CATEGORY,
    DUMB_DEVICE_COOL,
    DUMB_DEVICE_HEAT,
    DUMB_PARTICIPATION_ALWAYS,
    DUMB_PARTICIPATION_OFF,
    DUMB_PARTICIPATION_UNTIL_TARGET,
)


def parse_dumb_devices_json(raw: str) -> list[dict[str, Any]]:
    """Parse and validate dumb devices JSON from config flow."""
    if not raw.strip():
        return []

    value = json.loads(raw)
    if not isinstance(value, list):
        raise ValueError("dumb devices must be a list")

    parsed: list[dict[str, Any]] = []
    allowed_types = {DUMB_DEVICE_HEAT, DUMB_DEVICE_COOL}
    allowed_participation = {
        DUMB_PARTICIPATION_OFF,
        DUMB_PARTICIPATION_ALWAYS,
        DUMB_PARTICIPATION_UNTIL_TARGET,
    }
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("dumb device entry must be an object")
        on_script = item.get("on_script")
        off_script = item.get("off_script")
        device_type = item.get("device_type")
        participation = item.get("participation")
        category = item.get("category", DUMB_DEFAULT_CATEGORY)
        if not on_script or not off_script:
            raise ValueError("dumb device requires on_script and off_script")
        if not str(on_script).startswith("script.") or not str(off_script).startswith("script."):
            raise ValueError("dumb scripts must be script.* entities")
        if device_type not in allowed_types:
            raise ValueError("dumb device_type must be heat or cool")
        if participation not in allowed_participation:
            raise ValueError("invalid dumb participation")
        if not isinstance(category, int) or category not in (1, 2, 3):
            raise ValueError("dumb category must be 1, 2 or 3")
        parsed.append(
            {
                "on_script": str(on_script),
                "off_script": str(off_script),
                "device_type": str(device_type),
                "participation": str(participation),
                "category": category,
            }
        )
    return parsed
