"""Regression checks for integration-level pitfalls."""

from __future__ import annotations

import ast
from pathlib import Path

from custom_components.smart_climate.const import DEFAULT_MODE, MODE_OFF

ROOT = Path(__file__).resolve().parents[1]
NUMBER_PLATFORM = ROOT / "custom_components" / "smart_climate" / "platforms" / "number.py"
SELECT_PLATFORM = ROOT / "custom_components" / "smart_climate" / "platforms" / "select.py"


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


def test_select_platform_does_not_restore_mode_or_type_from_last_state() -> None:
    source = SELECT_PLATFORM.read_text(encoding="utf-8")
    assert "async_get_last_state" not in source
    assert "async_set_mode(last_state.state)" not in source
    assert "async_set_type(last_state.state)" not in source
