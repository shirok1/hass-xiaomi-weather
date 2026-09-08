"""Client transport and parsing contract tests."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import ClientConnectionError, ClientSession, web
from aiohttp.pytest_plugin import AiohttpServer

from custom_components.xiaomi_weather.api import (
    XiaomiWeatherClient,
    XiaomiWeatherError,
    number,
    parse_weather,
)


def test_live_fixture(payload: dict[str, Any]) -> None:
    """Check actual units, array alignment and timezone conversion."""
    data = parse_weather(payload)
    assert data.temperature == 20
    assert data.humidity == 71
    assert data.pressure == 1014
    assert data.wind_speed == 6
    assert data.aqi == 13
    assert len(data.daily) == 15
    assert len(data.hourly) == 23
    assert data.daily[0].temperature == 21
    assert data.daily[0].low == 16
    assert data.daily[0].time == datetime(2026, 9, 7, 16, tzinfo=UTC)
    assert data.hourly[0].time == datetime(2026, 9, 8, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    "value", [None, "", "NaN", "inf", "-inf", -999, True, {}, "bad"]
)
def test_invalid_numbers(value: object) -> None:
    assert number(value) is None


@pytest.mark.parametrize("value", [0, "0", 0.0])
def test_zero(value: object) -> None:
    assert number(value) == 0


@pytest.mark.parametrize("bad", [None, {}, [], {"current": {}}, {"current": None}])
def test_invalid_payload(bad: object) -> None:
    with pytest.raises(XiaomiWeatherError):
        parse_weather(bad)


def test_optional_data(payload: dict[str, Any]) -> None:
    data = parse_weather({"current": payload["current"]})
    assert data.daily == ()
    assert data.hourly == ()
    assert data.aqi is None


def test_unknown_condition(payload: dict[str, Any]) -> None:
    payload["current"]["weather"] = "9999"
    assert parse_weather(payload).condition is None


@pytest.mark.parametrize(
    "time,expected",
    [
        ("2026-09-08T05:47:00+08:00", "clear-night"),
        ("2026-09-08T05:48:00+08:00", "sunny"),
        ("2026-09-08T18:36:00+08:00", "clear-night"),
    ],
)
def test_day_night(payload: dict[str, Any], time: str, expected: str) -> None:
    payload["current"].update(weather="0", pubTime=time)
    assert parse_weather(payload).condition == expected


def test_array_gaps(payload: dict[str, Any]) -> None:
    payload["forecastDaily"]["temperature"]["value"][0]["from"] = ""
    payload["forecastDaily"]["weather"]["value"] = []
    payload["forecastHourly"]["temperature"]["value"][0] = None
    payload["forecastHourly"]["weather"]["value"] = []
    data = parse_weather(payload)
    assert len(data.daily) == 14
    assert data.daily[0].condition is None
    assert len(data.hourly) == 22
    assert data.hourly[0].time.hour == 6


@pytest.mark.parametrize("section", ["forecastDaily", "forecastHourly"])
def test_wrong_units(payload: dict[str, Any], section: str) -> None:
    payload[section]["temperature"]["unit"] = "F"
    with pytest.raises(XiaomiWeatherError):
        parse_weather(payload)


def test_naive_timestamp(payload: dict[str, Any]) -> None:
    payload["current"]["pubTime"] = "2026-09-08T12:00:00"
    with pytest.raises(XiaomiWeatherError):
        parse_weather(payload)


def test_provider_status(payload: dict[str, Any]) -> None:
    for section in ["forecastDaily", "forecastHourly", "aqi"]:
        payload[section]["status"] = 1
    data = parse_weather(payload)
    assert not data.daily and not data.hourly and data.aqi is None


async def test_http_success(
    payload: dict[str, Any], aiohttp_server: AiohttpServer, socket_enabled: None
) -> None:
    async def handler(request: web.Request) -> web.Response:
        assert request.query["locationKey"] == "weathercn:101010100"
        assert request.query["latitude"] == "39.9"
        return web.json_response(payload)

    app = web.Application()
    app.router.add_get("/weather", handler)
    server = await aiohttp_server(app)
    with patch(
        "custom_components.xiaomi_weather.api.URL", str(server.make_url("/weather"))
    ):
        async with ClientSession() as session:
            result = await XiaomiWeatherClient(
                session, "101010100", 39.9, 116.4
            ).async_get_weather()
    assert result.temperature == 20


@pytest.mark.parametrize(
    "status,body", [(429, "limited"), (500, "error"), (200, "not-json")]
)
async def test_http_failure(
    status: int, body: str, aiohttp_server: AiohttpServer, socket_enabled: None
) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=status, text=body, content_type="application/json")

    app = web.Application()
    app.router.add_get("/weather", handler)
    server = await aiohttp_server(app)
    with patch(
        "custom_components.xiaomi_weather.api.URL", str(server.make_url("/weather"))
    ):
        async with ClientSession() as session:
            with pytest.raises(XiaomiWeatherError):
                await XiaomiWeatherClient(
                    session, "101010100", 39.9, 116.4
                ).async_get_weather()


@pytest.mark.parametrize("failure", [TimeoutError(), ClientConnectionError()])
async def test_transport_failure(failure: Exception) -> None:
    session = MagicMock(spec=ClientSession)
    session.get.side_effect = failure
    with pytest.raises(XiaomiWeatherError):
        await XiaomiWeatherClient(session, "101010100", 39.9, 116.4).async_get_weather()


@pytest.mark.parametrize(
    "section,key",
    [
        ("forecastDaily", "temperature"),
        ("forecastDaily", "weather"),
        ("forecastDaily", "sunRiseSet"),
        ("forecastHourly", "temperature"),
        ("forecastHourly", "weather"),
    ],
)
def test_failed_subseries(payload: dict[str, Any], section: str, key: str) -> None:
    payload[section][key]["status"] = 1
    data = parse_weather(payload)
    result = data.daily if section == "forecastDaily" else data.hourly
    if key == "weather":
        assert all(item.condition is None for item in result)
    else:
        assert result == ()


def test_misaligned_hourly_weather(payload: dict[str, Any]) -> None:
    payload["forecastHourly"]["weather"]["pubTime"] = "2026-09-08T14:00:00+08:00"
    assert all(item.condition is None for item in parse_weather(payload).hourly)


def test_invalid_series(payload: dict[str, Any]) -> None:
    payload["forecastDaily"]["temperature"]["value"] = None
    with pytest.raises(XiaomiWeatherError):
        parse_weather(payload)


def test_clear_without_sun_times(payload: dict[str, Any]) -> None:
    payload["current"]["weather"] = "0"
    payload["current"]["pubTime"] = "2026-09-07T12:00:00+08:00"
    assert parse_weather(payload).condition == "sunny"
