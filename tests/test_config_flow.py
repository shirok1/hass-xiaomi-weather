"""Exercise source-first setup through HA's public flow manager."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, section
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiaomi_weather.api import Location, XiaomiWeatherError
from custom_components.xiaomi_weather.const import DOMAIN


@pytest.fixture(autouse=True)
def locations() -> Generator[AsyncMock]:
    """Mock only location service calls, not the configuration state machine."""
    with patch(
        "custom_components.xiaomi_weather.config_flow.XiaomiLocationClient"
    ) as factory:
        client = AsyncMock()
        factory.return_value = client
        location = Location("101010100", "北京市", "中国", 39.904, 116.408)
        for method in (client.async_city, client.async_locate, client.async_search):
            method.return_value = [location]
        yield client


async def enter_source(
    hass: HomeAssistant, step: str, entry: MockConfigEntry | None = None
) -> ConfigFlowResult:
    """Choose a route as the frontend would from the native menu."""
    context: dict[str, Any] = {"source": SOURCE_USER}
    if entry:
        entry.add_to_hass(hass)
        context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
    result = await hass.config_entries.flow.async_init(DOMAIN, context=context)
    assert result["type"] is FlowResultType.MENU
    assert tuple(result["menu_options"]) == ("zone", "search", "coordinates")
    result = await configure(hass, result["flow_id"], {"next_step_id": step})
    assert result["step_id"] == step
    return result


async def configure(
    hass: HomeAssistant, flow_id: str, inputs: dict[str, Any]
) -> ConfigFlowResult:
    """Submit an input and explicitly confirm a sole candidate in lifecycle tests."""
    result = await hass.config_entries.flow.async_configure(flow_id, inputs)
    if result.get("step_id") == "city":
        assert result["data_schema"] is not None
        options = result["data_schema"].schema["city_id"].config["options"]
        if len(options) == 1:
            result = await hass.config_entries.flow.async_configure(
                flow_id, {"city_id": options[0]["value"]}
            )
    return result


@pytest.mark.parametrize("step", ["zone", "search", "coordinates"])
async def test_focused_forms(
    hass: HomeAssistant, locations: AsyncMock, step: str
) -> None:
    """Each screen has only its source fields and a collapsed optional section."""
    result = await enter_source(hass, step)
    assert result["data_schema"] is not None
    schema = result["data_schema"].schema
    assert (
        set(schema)
        == {
            "zone": {"zone", "advanced"},
            "search": {"city_id", "coordinates"},
            "coordinates": {"latitude", "longitude", "advanced"},
        }[step]
    )
    nested = schema["coordinates" if step == "search" else "advanced"]
    assert isinstance(nested, section)
    assert nested.options["collapsed"] is True
    if step == "zone":
        key = next(key for key in schema if key == "zone")
        assert key.default() == "zone.home"
    assert not locations.mock_calls


@pytest.mark.parametrize(
    "step,inputs,method,latitude,longitude",
    [
        ("search", {"city_id": "101010100"}, "async_city", 39.904, 116.408),
        ("search", {"city_id": "weathercn:101010100"}, "async_city", 39.904, 116.408),
        ("search", {"city_id": "北京"}, "async_search", 39.904, 116.408),
        (
            "search",
            {"city_id": "北京", "coordinates": {"latitude": 40.0, "longitude": 117.0}},
            "async_search",
            40.0,
            117.0,
        ),
        (
            "coordinates",
            {"latitude": 39.9, "longitude": 116.4},
            "async_locate",
            39.9,
            116.4,
        ),
        ("coordinates", {"latitude": 0.0, "longitude": 0.0}, "async_locate", 0.0, 0.0),
        (
            "coordinates",
            {
                "latitude": 40.0,
                "longitude": 117.0,
                "advanced": {"city_id": "101010100"},
            },
            "async_city",
            40.0,
            117.0,
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    client: AsyncMock,
    locations: AsyncMock,
    step: str,
    inputs: dict[str, Any],
    method: str,
    latitude: float,
    longitude: float,
) -> None:
    result = await enter_source(hass, step)
    result = await configure(hass, result["flow_id"], inputs)
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "city_name": "北京市",
        "city_id": "101010100",
        "latitude": str(latitude),
        "longitude": str(longitude),
    }
    assert not hass.config_entries.async_entries(DOMAIN)
    client.assert_not_awaited()
    getattr(locations, method).assert_awaited_once()
    result = await configure(hass, result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "北京市",
        "city_id": "101010100",
        "latitude": latitude,
        "longitude": longitude,
    }
    assert result["result"].unique_id == "101010100"
    await hass.async_block_till_done()


@pytest.mark.parametrize("city", ["123", "weathercn:bad"])
async def test_invalid_city(
    hass: HomeAssistant, locations: AsyncMock, city: str
) -> None:
    result = await enter_source(hass, "search")
    result = await configure(hass, result["flow_id"], {"city_id": city})
    assert result["step_id"] == "search"
    assert result["errors"] == {"base": "invalid_city_id"}
    assert not locations.mock_calls


async def test_coordinate_pair_error(hass: HomeAssistant, locations: AsyncMock) -> None:
    result = await enter_source(hass, "search")
    inputs = {"city_id": "北京", "coordinates": {"latitude": 40.0}}
    result = await configure(hass, result["flow_id"], inputs)
    assert result["step_id"] == "search"
    assert result["errors"] == {"base": "coordinates_required"}
    assert result["data_schema"] is not None
    nested = result["data_schema"].schema["coordinates"]
    assert not nested.options["collapsed"]
    key = next(key for key in nested.schema.schema if key == "latitude")
    assert key.description["suggested_value"] == 40.0
    assert not locations.mock_calls


@pytest.mark.parametrize("failure", [False, True])
async def test_lookup_error_retry(
    hass: HomeAssistant, locations: AsyncMock, failure: bool
) -> None:
    result = await enter_source(hass, "search")
    resolved = locations.async_city.return_value
    locations.async_city.return_value = []
    if failure:
        locations.async_city.side_effect = XiaomiWeatherError
    result = await configure(hass, result["flow_id"], {"city_id": "101010100"})
    assert result["step_id"] == "search"
    assert result["errors"] == {
        "base": "lookup_failed" if failure else "city_not_found"
    }
    assert result["data_schema"] is not None
    key = next(key for key in result["data_schema"].schema if key == "city_id")
    assert key.description["suggested_value"] == "101010100"
    locations.async_city.side_effect = None
    locations.async_city.return_value = resolved
    result = await configure(hass, result["flow_id"], {"city_id": "101010100"})
    assert result["step_id"] == "confirm"


async def test_candidate_and_weather_retry(
    hass: HomeAssistant, client: AsyncMock, locations: AsyncMock
) -> None:
    """A failed weather request keeps the chosen city and edited name for retry."""
    locations.async_search.return_value = [
        Location("101010100", "北京市", "中国", 39.904, 116.408),
        Location("101010300", "朝阳区", "北京市, 中国", 39.921, 116.486),
    ]
    result = await enter_source(hass, "search")
    result = await configure(hass, result["flow_id"], {"city_id": "北京"})
    assert result["step_id"] == "city"
    result = await configure(hass, result["flow_id"], {"city_id": "101010300"})
    assert result["step_id"] == "confirm"
    summary = result["description_placeholders"]
    client.side_effect = XiaomiWeatherError
    result = await configure(
        hass, result["flow_id"], {"display": {"name": "My weather"}}
    )
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == summary
    locations.async_search.assert_awaited_once()
    assert not hass.config_entries.async_entries(DOMAIN)
    client.side_effect = None
    result = await configure(hass, result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["city_id"] == "101010300"
    assert result["title"] == "My weather"
    await hass.async_block_till_done()


@pytest.mark.parametrize("during_review", [False, True])
async def test_duplicate(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry, during_review: bool
) -> None:
    result = await enter_source(hass, "search")
    if not during_review:
        entry.add_to_hass(hass)
    result = await configure(hass, result["flow_id"], {"city_id": "101010100"})
    if during_review:
        entry.add_to_hass(hass)
        result = await configure(hass, result["flow_id"], {})
    assert result["reason"] == "already_configured"
    client.assert_not_awaited()


@pytest.mark.parametrize("zone_id", ["zone.home", "zone.work"])
async def test_zone(
    hass: HomeAssistant, client: AsyncMock, locations: AsyncMock, zone_id: str
) -> None:
    result = await enter_source(hass, "zone")
    hass.states.async_set(zone_id, "0", {"latitude": 39.9, "longitude": 116.4})
    result = await configure(hass, result["flow_id"], {"zone": zone_id})
    assert result["step_id"] == "confirm"
    locations.async_locate.assert_awaited_once_with(39.9, 116.4)
    result = await configure(hass, result["flow_id"], {})
    assert result["data"]["latitude"] == 39.9
    assert "zone" not in result["data"]
    await hass.async_block_till_done()


async def test_zone_city_override(hass: HomeAssistant, locations: AsyncMock) -> None:
    result = await enter_source(hass, "zone")
    hass.states.async_set("zone.home", "0", {"latitude": 40.0, "longitude": 117.0})
    result = await configure(
        hass,
        result["flow_id"],
        {"zone": "zone.home", "advanced": {"city_id": "101010100"}},
    )
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] is not None
    assert result["description_placeholders"]["latitude"] == "40.0"
    locations.async_city.assert_awaited_once_with("101010100")
    locations.async_locate.assert_not_awaited()


@pytest.mark.parametrize(
    "attributes",
    [
        None,
        {},
        {"latitude": 39.9},
        {"latitude": 100, "longitude": 116.4},
        {"latitude": 39.9, "longitude": float("nan")},
    ],
)
async def test_invalid_zone(
    hass: HomeAssistant, locations: AsyncMock, attributes: dict[str, Any] | None
) -> None:
    result = await enter_source(hass, "zone")
    if attributes is not None:
        hass.states.async_set("zone.test", "0", attributes)
    result = await configure(hass, result["flow_id"], {"zone": "zone.test"})
    assert result["step_id"] == "zone"
    assert result["errors"] == {"zone": "invalid_zone"}
    assert not locations.mock_calls


async def test_edit_location_clears_previous_source(
    hass: HomeAssistant, client: AsyncMock, locations: AsyncMock
) -> None:
    result = await enter_source(hass, "coordinates")
    result = await configure(
        hass, result["flow_id"], {"latitude": 40.0, "longitude": 117.0}
    )
    result = await configure(hass, result["flow_id"], {"edit_location": True})
    assert result["type"] is FlowResultType.MENU
    result = await configure(hass, result["flow_id"], {"next_step_id": "search"})
    result = await configure(hass, result["flow_id"], {"city_id": "101010100"})
    assert result["description_placeholders"] is not None
    assert result["description_placeholders"]["latitude"] == "39.904"
    client.assert_not_awaited()


@pytest.mark.parametrize(
    "step,inputs,latitude",
    [
        ("search", {"city_id": "101010100"}, 39.904),
        ("coordinates", {"latitude": 40.0, "longitude": 117.0}, 40.0),
        ("zone", {"zone": "zone.home"}, 41.0),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    step: str,
    inputs: dict[str, Any],
    latitude: float,
) -> None:
    result = await enter_source(hass, step, entry)
    hass.states.async_set("zone.home", "0", {"latitude": 41.0, "longitude": 116.5})
    result = await configure(hass, result["flow_id"], inputs)
    assert result["step_id"] == "confirm"
    assert entry.data["latitude"] == 39.9042
    result = await configure(hass, result["flow_id"], {})
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["latitude"] == latitude
    assert entry.title == ("home" if step == "zone" else "Beijing")
    await hass.async_block_till_done()


async def test_reconfigure_failure(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    result = await enter_source(hass, "search", entry)
    result = await configure(hass, result["flow_id"], {"city_id": "101010100"})
    client.side_effect = XiaomiWeatherError
    result = await configure(hass, result["flow_id"], {"display": {"name": "Updated"}})
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "confirm"
    assert entry.data["latitude"] == 39.9042
    assert entry.title == "Beijing"


async def test_reconfigure_different_city(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry, locations: AsyncMock
) -> None:
    result = await enter_source(hass, "search", entry)
    locations.async_city.return_value = [
        Location("101020100", "上海市", "中国", 31.2, 121.5)
    ]
    result = await configure(hass, result["flow_id"], {"city_id": "101020100"})
    assert result["step_id"] == "search"
    assert result["errors"] == {"base": "different_city"}
    assert entry.unique_id == "101010100"
    client.assert_not_awaited()


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("source", ["search", "coordinates", "zone"])
async def test_always_review_match_list(
    hass: HomeAssistant,
    client: AsyncMock,
    locations: AsyncMock,
    source: str,
    count: int,
) -> None:
    """Every resolution method requires explicit candidate selection, even one match."""
    matches = [Location("101010100", "北京市", "中国", 39.904, 116.408)]
    if count == 2:
        matches.append(Location("101010300", "朝阳区", "北京市", 39.921, 116.486))
    for method in (locations.async_search, locations.async_locate):
        method.return_value = matches
    result = await enter_source(hass, source)
    hass.states.async_set("zone.home", "0", {"latitude": 39.9, "longitude": 116.4})
    inputs = {
        "search": {"city_id": "北京"},
        "coordinates": {"latitude": 39.9, "longitude": 116.4},
        "zone": {"zone": "zone.home"},
    }[source]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], inputs)
    assert result["step_id"] == "city"
    assert result["data_schema"] is not None
    options = result["data_schema"].schema["city_id"].config["options"]
    assert len(options) == count
    assert options[0] == {"value": "101010100", "label": "北京市 · 中国 (101010100)"}
    client.assert_not_awaited()
    assert not hass.config_entries.async_entries(DOMAIN)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"city_id": "101010100"}
    )
    assert result["step_id"] == "confirm"


@pytest.mark.parametrize("custom_name", [None, "我的天气"])
async def test_zone_name_defaults_and_override(
    hass: HomeAssistant, client: AsyncMock, custom_name: str | None
) -> None:
    """Use the zone's friendly name, while keeping a user-supplied name on retry."""
    result = await enter_source(hass, "zone")
    hass.states.async_set(
        "zone.home",
        "0",
        {"latitude": 39.9, "longitude": 116.4, "friendly_name": "家庭"},
    )
    result = await configure(hass, result["flow_id"], {"zone": "zone.home"})
    assert result["data_schema"] is not None
    display_schema = result["data_schema"].schema["display"].schema.schema
    name_key = next(key for key in display_schema if key == "name")
    assert name_key.default() == "家庭"
    if custom_name:
        client.side_effect = XiaomiWeatherError
        result = await configure(
            hass, result["flow_id"], {"display": {"name": custom_name}}
        )
        assert result["step_id"] == "confirm"
        client.side_effect = None
    result = await configure(hass, result["flow_id"], {})
    assert result["data"]["name"] == (custom_name or "家庭")
    assert result["title"] == (custom_name or "家庭")
    await hass.async_block_till_done()


async def test_zone_name_does_not_leak_to_new_source(
    hass: HomeAssistant, client: AsyncMock
) -> None:
    result = await enter_source(hass, "zone")
    hass.states.async_set(
        "zone.home",
        "0",
        {"latitude": 40.0, "longitude": 117.0, "friendly_name": "家庭"},
    )
    result = await configure(hass, result["flow_id"], {"zone": "zone.home"})
    result = await configure(hass, result["flow_id"], {"edit_location": True})
    result = await configure(hass, result["flow_id"], {"next_step_id": "search"})
    result = await configure(hass, result["flow_id"], {"city_id": "北京"})
    result = await configure(hass, result["flow_id"], {})
    assert result["title"] == "北京市"
    await hass.async_block_till_done()
