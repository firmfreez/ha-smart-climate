"""Dataclasses for smart climate runtime state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .const import PHASE_IDLE


@dataclass
class DumbDeviceConfig:
    """Configuration for a script-controlled device."""

    on_script: str
    off_script: str
    device_type: str
    participation: str


@dataclass
class RoomConfig:
    """Room static configuration."""

    room_id: str
    name: str
    temp_sensors: list[str] = field(default_factory=list)
    primary_climates: list[str] = field(default_factory=list)
    ac_climates: list[str] = field(default_factory=list)
    dumb_devices: list[DumbDeviceConfig] = field(default_factory=list)
    shared_climates: list[str] = field(default_factory=list)


@dataclass
class RoomRuntime:
    """Room mutable runtime state."""

    enabled: bool = True
    current_temp: float | None = None
    target_temp: float | None = None
    tolerance: float = 0.3
    phase: str = PHASE_IDLE
    current_offset: float = 0.0
    boost_started_at: datetime | None = None
    last_reach_time: datetime | None = None
    last_temp_sample: float | None = None
    active_category_heat: int = 0
    active_category_cool: int = 0
    active_devices: list[str] = field(default_factory=list)


@dataclass
class DeviceActionState:
    """Per-device anti-flapping state."""

    last_action_time: datetime | None = None
