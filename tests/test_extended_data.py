"""Full response, independent time axes and HA action contracts.

Nonempty alerts, typhoons, rain and moon phase below are synthetic cases;
the full fixture itself is an unchanged public-city API response.
"""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.weather.const import WeatherEntityStateAttribute
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiaomi_weather.api import XiaomiWeatherError, parse_weather
from custom_components.xiaomi_weather.coordinator import XiaomiWeatherConfigEntry
from custom_components.xiaomi_weather.sensor import XiaomiSensor


async def test_standard_weather_state_and_units(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    full_payload: dict[str, Any],
) -> None:
    """Rich source data stays separate; HA converts native weather measurements."""
    current = full_payload["current"]
    current["temperature"]["value"] = "20"
    current["feelsLike"]["value"] = "10"
    current["visibility"]["value"] = "16.09344"
    current["wind"]["speed"]["value"] = "16.09344"
    current["pressure"]["value"] = "1015.9166"
    full_payload["alerts"] = [{"title": "模拟预警"}]
    client.return_value = parse_weather(full_payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None
    allowed = set(WeatherEntityStateAttribute) | {
        "attribution",
        "friendly_name",
        "supported_features",
    }
    assert state.attributes.keys() <= allowed
    assert state.attributes["temperature"] == 20
    assert state.attributes["apparent_temperature"] == 10
    assert state.attributes["temperature_unit"] == "°C"
    assert not {"ozone", "cloud_coverage", "dew_point", "wind_gust_speed"} & (
        state.attributes.keys()
    )

    er.async_get(hass).async_update_entity_options(
        "weather.beijing",
        "weather",
        {
            "temperature_unit": "°F",
            "pressure_unit": "inHg",
            "wind_speed_unit": "mph",
            "visibility_unit": "mi",
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None
    assert state.attributes.keys() <= allowed
    for key, expected in {
        "temperature": 68,
        "apparent_temperature": 50,
        "pressure": 30,
        "wind_speed": 10,
        "visibility": 10,
    }.items():
        assert state.attributes[key] == pytest.approx(expected)
    assert state.attributes["temperature_unit"] == "°F"
    client.assert_awaited_once()


def test_complete_live_response(full_payload: dict[str, Any]) -> None:
    data = parse_weather(full_payload)
    assert data.raw == full_payload
    expected = {
        "o3": 66,
        "no2": 17,
        "so2": 2,
        "co": 0.3,
        "alerts": 0,
        "typhoons": 0,
        "indices": 6,
        "car_wash": "0",
        "sports": "0",
        "yesterday_high": 25,
        "yesterday_low": 13,
        "yesterday_aqi": 18,
        "daily_aqi": 24,
        "hourly_aqi": 38,
        "previous_hour": 21,
    }
    for key, value in expected.items():
        assert data.sensors[key].value == value
    assert data.visibility is None
    assert data.sensors["moon_phase"].value is None
    assert len(data.twice_daily) == 30
    assert data.sensors["aqi_observed_at"].value == datetime(
        2026, 9, 10, 14, tzinfo=UTC
    )
    assert data.sensors["observed_at"].value == datetime(
        2026, 9, 10, 14, 35, 8, tzinfo=UTC
    )
    assert data.sensors["sunrise"].value == datetime(2026, 9, 9, 21, 50, tzinfo=UTC)
    assert data.sensors["sunset"].value == datetime(2026, 9, 10, 10, 33, tzinfo=UTC)
    assert data.sensors["provider_updated_at"].value is not None
    assert len(data.sensors["daily_aqi"].attributes["forecast"]) == 15
    assert len(data.sensors["hourly_aqi"].attributes["forecast"]) == 23
    nowcast = data.sensors["nowcast"]
    assert nowcast.value == full_payload["minutely"]["precipitation"]["description"]
    assert nowcast.attributes["precipitation"]["isShow"] is False
    assert nowcast.attributes["precipitation"]["value"] == [0] * 120
    assert nowcast.attributes["precipitation"]["probability"] == [0] * 4
    assert data.sensors["yesterday"].attributes == full_payload["yesterday"]
    assert (
        data.sensors["previous_hour"].attributes["observations"]
        == full_payload["preHour"]
    )
    full_payload["minutely"]["precipitation"]["value"][0] = 999
    assert data.raw["minutely"]["precipitation"]["value"][0] == 0
    assert nowcast.attributes["precipitation"]["value"][0] == 0


def test_forecast_time_alignment_and_nights(payload: dict[str, Any]) -> None:
    payload["forecastDaily"]["precipitationProbability"]["value"][:3] = [1, 80, -999]
    payload["forecastDaily"]["moonPhase"] = {"value": ["新月"]}
    payload["forecastDaily"]["weather"]["value"][0] = {"from": "0", "to": "0"}
    winds = payload["forecastHourly"]["wind"]["value"]
    first = winds.pop(0)
    winds.reverse()
    winds.append(first)
    payload["forecastHourly"]["aqi"] = {
        "pubTime": "2026-09-08T15:00:00+08:00",
        "value": [10, -999, 30],
    }
    payload["current"]["visibility"] = {"unit": "km", "value": "12"}
    data = parse_weather(payload)
    assert data.visibility == 12
    assert data.sensors["moon_phase"].value == "新月"
    assert data.daily[0].precipitation_probability == 1
    assert data.daily[1].precipitation_probability == 80
    assert data.daily[2].precipitation_probability is None
    assert data.daily[0].wind_speed == 6
    assert data.hourly[0].wind_speed == 4.6
    assert data.hourly[0].wind_bearing == 37.05
    day, night = data.twice_daily[:2]
    assert day.is_daytime is True and day.condition == "sunny"
    assert night.is_daytime is False and night.condition == "clear-night"
    assert day.temperature == 21 and night.temperature == 16
    assert day.time == datetime(2026, 9, 7, 21, 48, tzinfo=UTC)
    assert night.time == datetime(2026, 9, 8, 10, 36, tzinfo=UTC)
    points = data.sensors["hourly_aqi"].attributes["forecast"]
    assert points == [
        {"datetime": "2026-09-08T07:00:00+00:00", "aqi": 10},
        {"datetime": "2026-09-08T08:00:00+00:00", "aqi": None},
        {"datetime": "2026-09-08T09:00:00+00:00", "aqi": 30},
    ]


def test_nonempty_events_and_provider_fields(full_payload: dict[str, Any]) -> None:
    full_payload["alerts"] = [
        {
            "title": "模拟暴雨预警",
            "level": "橙色",
            "type": "暴雨",
            "detail": "测试",
            "pubTime": "2026-09-10T21:00:00+08:00",
            "futureField": "kept",
        }
    ]
    full_payload["typhoon"] = [
        {
            "typhoonCname": "模拟台风",
            "typhoonCode": "test",
            "lat": 20.0,
            "lon": 120.0,
            "centWindSpeed": 30,
            "track": [{"lat": 19.0}],
        }
    ]
    full_payload["minutely"]["precipitation"].update(
        value=[0, 0.5, 1], probability=[10, 20, 30, 40], isShow=True
    )
    data = parse_weather(full_payload)
    assert data.sensors["alerts"].value == 1
    assert data.sensors["alerts"].attributes["items"] == full_payload["alerts"]
    assert data.sensors["typhoons"].attributes["items"] == full_payload["typhoon"]
    assert data.sensors["nowcast"].attributes == full_payload["minutely"]
    assert data.raw == full_payload


@pytest.mark.parametrize(
    "field",
    ["aqi", "indices", "minutely", "yesterday", "forecastDaily", "forecastHourly"],
)
def test_failed_optional_blocks(full_payload: dict[str, Any], field: str) -> None:
    full_payload[field]["status"] = 1
    data = parse_weather(full_payload)
    assert data.temperature == 19
    keys = {
        "aqi": ("o3", "co", "aqi_observed_at", "air_quality_suggestion"),
        "indices": ("indices", "car_wash", "sports"),
        "minutely": ("nowcast", "rain_distance", "nowcast_observed_at"),
        "yesterday": ("yesterday", "yesterday_high", "yesterday_aqi"),
        "forecastDaily": ("daily_aqi", "sunrise", "sunset", "moon_phase"),
        "forecastHourly": ("hourly_aqi",),
    }
    assert all(data.sensors[key].value is None for key in keys[field])
    assert data.raw[field]["status"] == 1


def test_bad_optional_values_do_not_break_weather(full_payload: dict[str, Any]) -> None:
    full_payload["updateTime"] = 1e30
    full_payload["aqi"].update(co="NaN", o3=-999, pubTime="2026-09-10T22:00:00")
    full_payload["alerts"] = None
    full_payload["typhoon"] = [None]
    full_payload["indices"]["indices"] = [{"type": [], "value": "0"}]
    full_payload["minutely"]["precipitation"]["status"] = 1
    full_payload["forecastHourly"]["aqi"]["pubTime"] = "bad"
    full_payload["forecastHourly"]["wind"]["value"].append(
        {"datetime": "bad", "speed": 1}
    )
    full_payload["forecastDaily"]["wind"]["speed"]["unit"] = "unknown"
    full_payload["forecastHourly"]["wind"]["unit"] = "unknown"
    data = parse_weather(full_payload)
    assert data.temperature == 19
    for key in (
        "provider_updated_at",
        "co",
        "o3",
        "aqi_observed_at",
        "alerts",
        "typhoons",
        "car_wash",
        "nowcast",
        "hourly_aqi",
    ):
        assert data.sensors[key].value is None
    assert data.daily[0].wind_speed is None
    assert data.hourly[0].wind_speed is None


def test_missing_daily_high_retains_night(payload: dict[str, Any]) -> None:
    payload["forecastDaily"]["temperature"]["value"][0]["from"] = None
    data = parse_weather(payload)
    assert len(data.daily) == 14
    assert len(data.twice_daily) == 29
    assert data.twice_daily[0].is_daytime is False
    payload["forecastDaily"]["sunRiseSet"]["value"][0] = {"from": "bad", "to": None}
    payload["current"]["weather"] = "0"
    data = parse_weather(payload)
    assert len(data.twice_daily) == 28
    assert data.condition == "sunny"


async def test_full_data_action_and_sensors(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    full_payload: dict[str, Any],
) -> None:
    full_payload["aqi"]["suggest"] = "建议" * 200
    full_payload["futureBlock"] = {"newField": [1, 2, 3]}
    client.return_value = parse_weather(full_payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)

    diagnostic_keys = {
        "observed_at",
        "aqi_observed_at",
        "provider_updated_at",
        "nowcast_observed_at",
    }
    disabled_keys = {
        "yesterday",
        "yesterday_high",
        "yesterday_low",
        "yesterday_aqi",
        "previous_hour",
        "daily_aqi",
        "hourly_aqi",
    }
    for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
        key = registered.unique_id.removeprefix("101010100_")
        assert registered.entity_category == (
            EntityCategory.DIAGNOSTIC if key in diagnostic_keys else None
        )
        assert registered.disabled_by == (
            er.RegistryEntryDisabler.INTEGRATION if key in disabled_keys else None
        )
        if key in disabled_keys:
            assert hass.states.get(registered.entity_id) is None

    def state(key: str):
        entity_id = registry.async_get_entity_id(
            "sensor", "xiaomi_weather", f"101010100_{key}"
        )
        assert entity_id is not None
        result = hass.states.get(entity_id)
        assert result is not None
        return result

    assert state("co").state == "0.3"
    assert state("co").attributes["unit_of_measurement"] == "mg/m³"
    assert state("o3").attributes["unit_of_measurement"] == "μg/m³"
    assert state("car_wash").state == "0"
    assert state("alerts").state == "0"
    assert state("moon_phase").state == "unknown"
    assert len(state("air_quality_suggestion").state) == 255
    assert state("air_quality_suggestion").attributes["description"] == "建议" * 200
    assert state("pm25").attributes["source"] == "中国环境监测总站"

    result = await hass.services.async_call(
        "xiaomi_weather",
        "get_data",
        {"entity_id": "weather.beijing"},
        blocking=True,
        return_response=True,
    )
    assert result is not None and result["weather.beijing"]["data"] == full_payload
    result["weather.beijing"]["data"]["futureBlock"]["newField"].append(4)
    again = await hass.services.async_call(
        "xiaomi_weather",
        "get_data",
        {"entity_id": "weather.beijing"},
        blocking=True,
        return_response=True,
    )
    assert again is not None and again["weather.beijing"]["data"] == full_payload
    client.assert_awaited_once()

    # Direct entity attributes must also be detached from the shared snapshot.
    from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

    sensor_component = hass.data[SENSOR_DOMAIN]
    entity = sensor_component.get_entity(state("nowcast").entity_id)
    assert isinstance(entity, XiaomiSensor)
    attrs = entity.extra_state_attributes
    attrs["precipitation"]["value"][0] = 123
    assert (
        client.return_value.sensors["nowcast"].attributes["precipitation"]["value"][0]
        == 0
    )

    changed = deepcopy(full_payload)
    changed["alerts"] = [{"title": "synthetic alert"}]
    client.return_value = parse_weather(changed)
    await cast(XiaomiWeatherConfigEntry, entry).runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert state("alerts").state == "1"
    assert state("alerts").attributes["items"] == changed["alerts"]
    client.side_effect = XiaomiWeatherError
    await cast(XiaomiWeatherConfigEntry, entry).runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert state("alerts").state == "unavailable"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "xiaomi_weather",
            "get_data",
            {"entity_id": "weather.beijing"},
            blocking=True,
            return_response=True,
        )
    client.side_effect = None
    changed["aqi"] = None
    client.return_value = parse_weather(changed)
    await cast(XiaomiWeatherConfigEntry, entry).runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert state("alerts").state == "1"
    assert state("pm25").state == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "xiaomi_weather",
            "get_data",
            {"entity_id": "weather.beijing"},
            blocking=True,
            return_response=True,
        )


async def test_full_data_multiple_cities(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    full_payload: dict[str, Any],
) -> None:
    """The same action selects cities without mixing their caches or polling."""
    entry.add_to_hass(hass)
    client.return_value = parse_weather(full_payload)
    assert await hass.config_entries.async_setup(entry.entry_id)
    other = MockConfigEntry(
        domain="xiaomi_weather",
        title="Shanghai",
        unique_id="101020100",
        data={"city_id": "101020100", "latitude": 31.2, "longitude": 121.5},
    )
    other.add_to_hass(hass)
    second = deepcopy(full_payload)
    second["current"]["temperature"]["value"] = "30"
    client.return_value = parse_weather(second)
    assert await hass.config_entries.async_setup(other.entry_id)
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        "xiaomi_weather",
        "get_data",
        {"entity_id": ["weather.beijing", "weather.shanghai"]},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    assert result["weather.beijing"]["data"] == full_payload
    assert result["weather.shanghai"]["data"] == second
    assert client.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    result = await hass.services.async_call(
        "xiaomi_weather",
        "get_data",
        {"entity_id": "weather.shanghai"},
        blocking=True,
        return_response=True,
    )
    assert result is not None and result["weather.shanghai"]["data"] == second
    assert client.await_count == 2
