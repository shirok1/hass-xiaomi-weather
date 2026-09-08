"""Validate city metadata and the three actual lookup request shapes."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientSession, web
from aiohttp.pytest_plugin import AiohttpServer

from custom_components.xiaomi_weather.api import (
    Location,
    XiaomiLocationClient,
    XiaomiWeatherError,
)

CITY = {
    "locationKey": "weathercn:101010100",
    "name": "北京市",
    "affiliation": "中国",
    "latitude": "39.904",
    "longitude": "116.408",
    "status": 0,
}


@pytest.mark.parametrize(
    "endpoint,query",
    [
        ("info", {"locationKey": "weathercn:101010100", "locale": "zh_cn"}),
        ("geo", {"latitude": "39.9", "longitude": "116.4", "locale": "zh_cn"}),
        ("search", {"name": "北京", "locale": "zh_cn"}),
    ],
)
async def test_lookup_http(
    endpoint: str,
    query: dict[str, str],
    aiohttp_server: AiohttpServer,
    socket_enabled: None,
) -> None:
    async def handler(request: web.Request) -> web.Response:
        assert dict(request.query) == query
        return web.json_response([CITY, CITY])

    app = web.Application()
    app.router.add_get(f"/{endpoint}", handler)
    server = await aiohttp_server(app)
    with patch(
        "custom_components.xiaomi_weather.api.LOCATION_URL",
        str(server.make_url("/")).rstrip("/"),
    ):
        async with ClientSession() as session:
            client = XiaomiLocationClient(session)
            if endpoint == "info":
                result = await client.async_city("101010100")
            elif endpoint == "geo":
                result = await client.async_locate(39.9, 116.4)
            else:
                result = await client.async_search("北京")
    assert result == [Location("101010100", "北京市", "中国", 39.904, 116.408)]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        [None],
        [{}],
        [{**CITY, "latitude": "NaN"}],
        [{**CITY, "longitude": "190"}],
        [{**CITY, "name": ""}],
        [{**CITY, "locationKey": "weathercn:bad"}],
        [{**CITY, "affiliation": None}],
    ],
)
async def test_bad_location(payload: Any) -> None:
    with (
        patch(
            "custom_components.xiaomi_weather.api._async_get_json", return_value=payload
        ),
        pytest.raises(XiaomiWeatherError),
    ):
        await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_search("北京")


async def test_unsupported_and_failed_locations() -> None:
    with patch(
        "custom_components.xiaomi_weather.api._async_get_json",
        return_value=[{**CITY, "locationKey": "accu:123"}, {**CITY, "status": 1}],
    ):
        assert (
            await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_search(
                "北京"
            )
            == []
        )


async def test_wrong_city_match() -> None:
    with patch(
        "custom_components.xiaomi_weather.api._async_get_json", return_value=[CITY]
    ):
        assert (
            await XiaomiLocationClient(AsyncMock(spec=ClientSession)).async_city(
                "101020100"
            )
            == []
        )
