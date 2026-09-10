"""Shared fixtures using the real Home Assistant test harness."""

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiaomi_weather.api import parse_weather
from custom_components.xiaomi_weather.const import DOMAIN


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations: None) -> None:
    """Enable discovery of custom components."""


@pytest.fixture
def payload() -> dict[str, Any]:
    """Load a trimmed response captured from Xiaomi on 2026-09-08."""
    return json.loads((Path(__file__).parent / "fixtures/weather.json").read_text())


@pytest.fixture
def full_payload() -> dict[str, Any]:
    """Full public Beijing response captured on 2026-09-10; no invented alerts."""
    return json.loads(
        (Path(__file__).parent / "fixtures/weather_full.json").read_text()
    )


@pytest.fixture
def client(payload: dict[str, Any]) -> Generator[AsyncMock]:
    """Mock only the external client boundary."""
    with patch(
        "custom_components.xiaomi_weather.api.XiaomiWeatherClient.async_get_weather",
        return_value=parse_weather(payload),
    ) as mock:
        yield mock


@pytest.fixture
def entry() -> MockConfigEntry:
    """An entry for Beijing."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Beijing",
        unique_id="101010100",
        data={
            "name": "Beijing",
            "city_id": "101010100",
            "latitude": 39.9042,
            "longitude": 116.4074,
        },
    )
