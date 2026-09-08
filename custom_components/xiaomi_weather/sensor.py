"""Air quality measurements; AQI uses the provider's China index."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import XiaomiWeatherConfigEntry
from .entity import XiaomiWeatherEntity

DESCRIPTIONS = (
    SensorEntityDescription(
        key="aqi",
        translation_key="aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm25",
        translation_key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiWeatherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors even if the first snapshot lacks optional measurements."""
    async_add_entities(
        XiaomiAirQuality(entry, description) for description in DESCRIPTIONS
    )


class XiaomiAirQuality(XiaomiWeatherEntity, SensorEntity):
    """Expose a single air quality measurement."""

    def __init__(
        self, entry: XiaomiWeatherConfigEntry, description: SensorEntityDescription
    ) -> None:
        """Initialize stable sensor metadata."""
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the current measurement or unknown when absent."""
        return getattr(self.coordinator.data, self.entity_description.key)
