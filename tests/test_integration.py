"""Integration lifecycle, weather service and recovery tests."""

from dataclasses import replace
from typing import cast
from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiaomi_weather.api import XiaomiWeatherError
from custom_components.xiaomi_weather.coordinator import XiaomiWeatherConfigEntry
from custom_components.xiaomi_weather.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_setup_forecast_unload(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("weather.beijing")
    assert state is not None
    assert state.state == "partlycloudy"
    assert state.attributes["temperature"] == 20
    assert state.attributes["humidity"] == 71
    for forecast_type, count in [("daily", 15), ("hourly", 23), ("twice_daily", 30)]:
        result = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": "weather.beijing", "type": forecast_type},
            blocking=True,
            return_response=True,
        )
        assert result is not None
        assert len(result["weather.beijing"]["forecast"]) == count
        forecast = result["weather.beijing"]["forecast"][0]
        if forecast_type == "hourly":
            assert forecast["wind_speed"] == 4.6
            assert forecast["wind_bearing"] == 37.05
        else:
            assert forecast["wind_speed"] == 6
            assert forecast["wind_bearing"] == 27
        if forecast_type == "daily":
            assert forecast["precipitation_probability"] == 0
        if forecast_type == "twice_daily":
            assert forecast["is_daytime"] is True
            assert result["weather.beijing"]["forecast"][1]["is_daytime"] is False
    client.assert_awaited_once()
    entities = er.async_get(hass).entities
    assert (
        len([e for e in entities.values() if e.config_entry_id == entry.entry_id]) == 31
    )
    diagnostics = await async_get_config_entry_diagnostics(
        hass, cast(XiaomiWeatherConfigEntry, entry)
    )
    assert diagnostics == {
        "last_update_success": True,
        "daily_forecast_count": 15,
        "hourly_forecast_count": 23,
    }
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    client.side_effect = XiaomiWeatherError
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_and_recovery(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = cast(XiaomiWeatherConfigEntry, entry).runtime_data
    client.side_effect = XiaomiWeatherError
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None and state.state == "unavailable"
    client.side_effect = None
    client.return_value = replace(client.return_value, temperature=22, pm25=None)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None and state.attributes["temperature"] == 22
    registry = er.async_get(hass)
    pm25_id = registry.async_get_entity_id("sensor", "xiaomi_weather", "101010100_pm25")
    assert pm25_id is not None
    state = hass.states.get(pm25_id)
    assert state is not None and state.state == "unknown"


async def test_poll_and_unload(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """One scheduled request serves all entities; unloading cancels the next one."""
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client.assert_awaited_once()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=16))
    await hass.async_block_till_done()
    assert client.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=32))
    await hass.async_block_till_done()
    assert client.await_count == 2


async def test_forecast_subscription(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """Subscribers receive changed forecasts, with no extra network fetch."""
    from unittest.mock import Mock

    from homeassistant.components.weather.const import DATA_COMPONENT

    from custom_components.xiaomi_weather.weather import XiaomiWeather

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity = hass.data[DATA_COMPONENT].get_entity("weather.beijing")
    assert isinstance(entity, XiaomiWeather)
    listener = Mock()
    unsubscribe = entity.async_subscribe_forecast("daily", listener)
    data = client.return_value
    client.return_value = replace(
        data, daily=(replace(data.daily[0], temperature=30), *data.daily[1:])
    )
    await cast(XiaomiWeatherConfigEntry, entry).runtime_data.async_refresh()
    await hass.async_block_till_done()
    listener.assert_called_once()
    assert listener.call_args.args[0][0]["temperature"] == 30
    assert client.await_count == 2
    unsubscribe()


async def test_independent_locations(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """Unloading one location leaves the other location operational."""
    other = MockConfigEntry(
        domain="xiaomi_weather",
        title="Shanghai",
        unique_id="101020100",
        data={
            "name": "Shanghai",
            "city_id": "101020100",
            "latitude": 31.2,
            "longitude": 121.5,
        },
    )
    for config_entry in (entry, other):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert client.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    state = hass.states.get("weather.shanghai")
    assert state is not None and state.state == "partlycloudy"


async def test_unknown_forecast_condition(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """Unknown condition and absent low temperature remain omitted in forecasts."""
    data = client.return_value
    client.return_value = replace(
        data, daily=(replace(data.daily[0], condition=None, low=None),)
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.beijing", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    forecast = result["weather.beijing"]["forecast"][0]
    assert "condition" not in forecast
    assert "templow" not in forecast
