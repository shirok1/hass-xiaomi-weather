"""Verify native brand delivery, high-resolution logos and dark-mode fallbacks."""

from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    "image,asset",
    [
        ("icon.png", "icon.png"),
        ("icon@2x.png", "icon@2x.png"),
        ("logo.png", "logo.png"),
        ("logo@2x.png", "logo@2x.png"),
        ("dark_logo.png", "logo.png"),
        ("dark_icon.png", "icon.png"),
    ],
)
async def test_native_brand_image(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, image: str, asset: str
) -> None:
    assert await async_setup_component(hass, "brands", {})
    integration = await async_get_integration(hass, "xiaomi_weather")
    assert integration.has_branding
    client = await hass_client()
    response = await client.get(
        f"/api/brands/integration/xiaomi_weather/{image}?placeholder=no"
    )
    assert response.status == 200
    assert response.content_type == "image/png"
    expected = (Path(integration.file_path) / "brand" / asset).read_bytes()
    assert await response.read() == expected
