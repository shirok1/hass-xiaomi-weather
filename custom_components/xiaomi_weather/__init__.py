"""The Xiaomi Weather integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import XiaomiWeatherConfigEntry, XiaomiWeatherCoordinator

PLATFORMS = [Platform.WEATHER, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the cached full-response action, including before entries load."""
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        "get_data",
        entity_domain="weather",
        schema={},
        func="async_get_data",
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: XiaomiWeatherConfigEntry
) -> bool:
    """Fetch initial data before setting up platforms."""
    coordinator = XiaomiWeatherCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: XiaomiWeatherConfigEntry
) -> bool:
    """Unload entities and their coordinator subscriptions."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
