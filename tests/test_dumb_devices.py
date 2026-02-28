"""Tests for dumb-device configuration and category activation."""

from custom_components.smart_climate.dumb import parse_dumb_devices_json
from custom_components.smart_climate.engine import should_activate_dumb_device


def test_parse_dumb_devices_requires_on_and_off_scripts() -> None:
    payload = """
    [
      {
        "on_script": "script.heater_on",
        "off_script": "script.heater_off",
        "device_type": "heat",
        "participation": "until_reach_target",
        "category": 2
      }
    ]
    """
    parsed = parse_dumb_devices_json(payload)
    assert parsed[0]["on_script"] == "script.heater_on"
    assert parsed[0]["off_script"] == "script.heater_off"
    assert parsed[0]["category"] == 2


def test_parse_dumb_devices_rejects_missing_off_script() -> None:
    payload = """
    [
      {
        "on_script": "script.heater_on",
        "device_type": "heat",
        "participation": "until_reach_target",
        "category": 2
      }
    ]
    """
    try:
        parse_dumb_devices_json(payload)
        raise AssertionError("expected ValueError")
    except ValueError as err:
        assert "on_script and off_script" in str(err)


def test_parse_dumb_devices_rejects_invalid_category() -> None:
    payload = """
    [
      {
        "on_script": "script.heater_on",
        "off_script": "script.heater_off",
        "device_type": "heat",
        "participation": "until_reach_target",
        "category": 4
      }
    ]
    """
    try:
        parse_dumb_devices_json(payload)
        raise AssertionError("expected ValueError")
    except ValueError as err:
        assert "category must be 1, 2 or 3" in str(err)


def test_should_activate_dumb_device_by_category_and_type() -> None:
    assert should_activate_dumb_device(
        room_category=1,
        device_category=1,
        room_is_heating=True,
        device_type="heat",
        participation="until_reach_target",
    )
    assert should_activate_dumb_device(
        room_category=2,
        device_category=2,
        room_is_heating=True,
        device_type="heat",
        participation="always_on",
    )
    assert not should_activate_dumb_device(
        room_category=1,
        device_category=2,
        room_is_heating=True,
        device_type="heat",
        participation="always_on",
    )
    assert not should_activate_dumb_device(
        room_category=3,
        device_category=1,
        room_is_heating=False,
        device_type="heat",
        participation="always_on",
    )
    assert not should_activate_dumb_device(
        room_category=3,
        device_category=1,
        room_is_heating=True,
        device_type="heat",
        participation="off",
    )
