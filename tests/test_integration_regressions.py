"""Regression checks for integration-level pitfalls."""

from __future__ import annotations

import ast
from pathlib import Path

from custom_components.smart_climate.const import DEFAULT_MODE, MODE_OFF

ROOT = Path(__file__).resolve().parents[1]
NUMBER_PLATFORM = ROOT / "custom_components" / "smart_climate" / "platforms" / "number.py"
SELECT_PLATFORM = ROOT / "custom_components" / "smart_climate" / "platforms" / "select.py"
SENSOR_PLATFORM = ROOT / "custom_components" / "smart_climate" / "platforms" / "sensor.py"
SWITCH_PLATFORM = ROOT / "custom_components" / "smart_climate" / "platforms" / "switch.py"
COORDINATOR = ROOT / "custom_components" / "smart_climate" / "coordinator.py"


def _class_def(module: ast.Module, class_name: str) -> ast.ClassDef:
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise AssertionError(f"class {class_name} not found")


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def test_default_mode_is_off() -> None:
    assert DEFAULT_MODE == MODE_OFF


def test_number_base_does_not_mix_number_and_restore_number() -> None:
    module = ast.parse(NUMBER_PLATFORM.read_text(encoding="utf-8"))
    class_node = _class_def(module, "BaseSmartClimateNumber")
    bases = {_base_name(base) for base in class_node.bases}
    # Mixing NumberEntity + RestoreNumber can break MRO on HA/Python updates.
    assert not {"NumberEntity", "RestoreNumber"}.issubset(bases)
    assert "RestoreNumber" not in bases


def test_select_platform_does_not_restore_mode_or_type_from_last_state() -> None:
    source = SELECT_PLATFORM.read_text(encoding="utf-8")
    assert "async_get_last_state" not in source
    assert "async_set_mode(last_state.state)" not in source
    assert "async_set_type(last_state.state)" not in source


def test_runtime_entity_changes_are_persisted_to_entry_options() -> None:
    source = COORDINATOR.read_text(encoding="utf-8")
    assert "async_update_entry(self.config_entry, options=options)" in source
    assert "self._persist_option(CONF_MODE, value)" in source
    assert "self._persist_option(CONF_TYPE, value)" in source
    assert "self._persist_option(CONF_GLOBAL_TARGET, value)" in source
    assert "self._persist_option(CONF_GLOBAL_TOLERANCE, value)" in source
    assert "self._persist_option_map_value(CONF_ROOM_ENABLED, room_id, value)" in source
    assert "self._persist_option_map_value(CONF_PER_ROOM_TARGETS, room_id, value)" in source
    assert "self._persist_option_map_value(CONF_PER_ROOM_TOLERANCES, room_id, value)" in source


def test_after_reach_always_turns_devices_off() -> None:
    source = COORDINATOR.read_text(encoding="utf-8")
    assert 'await self._async_call_service_entity(climate_entity, "climate", "turn_off")' in source
    assert 'await self._async_call_service_entity(dumb.off_script, "script", "turn_on")' in source
    assert "smart_behavior =" not in source
    assert "dumb_behavior =" not in source


def test_room_phase_payload_contains_diagnostic_reason() -> None:
    source = COORDINATOR.read_text(encoding="utf-8")
    assert '"phase_reason": phase_reason' in source
    assert '"demand": demand' in source
    assert '"demand_delta": demand_delta' in source


def test_climate_commands_are_not_sent_when_state_already_matches() -> None:
    source = COORDINATOR.read_text(encoding="utf-8")
    assert 'domain == "climate" and service == "turn_off"' in source
    assert "state.state == \"off\"" in source
    assert "state.state != selected_hvac_mode" in source
    assert "abs(float(current_setpoint) - setpoint) > 0.05" in source
    assert 'elif "auto" in hvac_modes' in source
    assert '"climate",\n                    "turn_on"' in source
    assert "result[\"active\"] = True" in source


def test_room_phase_sensor_uses_phase_reason_as_primary_state() -> None:
    source = SENSOR_PLATFORM.read_text(encoding="utf-8")
    assert "phase_reason = room.get(\"phase_reason\")" in source
    assert "return phase_reason" in source
    assert "\"decision_summary\": room.get(\"decision_summary\")" in source
    assert "\"action_log\": room.get(\"action_log\", [])" in source


def test_number_platform_does_not_restore_last_number_state() -> None:
    source = NUMBER_PLATFORM.read_text(encoding="utf-8")
    assert "async_get_last_number_data" not in source


def test_switch_platform_does_not_restore_last_switch_state() -> None:
    source = SWITCH_PLATFORM.read_text(encoding="utf-8")
    assert "RestoreEntity" not in source
    assert "async_get_last_state" not in source


def test_room_with_no_temperature_is_excluded_from_control_and_shared() -> None:
    source = COORDINATOR.read_text(encoding="utf-8")
    assert "runtime.enabled = False" in source
    assert "self._runtime[room_id].current_temp is not None" in source


def test_opposite_mode_turn_off_skips_devices_present_in_both_modes() -> None:
    source = COORDINATOR.read_text(encoding="utf-8")
    assert "async def _async_deactivate_non_active_entities" in source
    assert "all_room_climates - active_current_climates - set(room.shared_climates)" in source
    assert "if dumb.on_script in active_current_dumb_on" in source
