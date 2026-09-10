"""Measurements and structured weather summaries from the shared snapshot."""

from copy import deepcopy
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfDensity,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SensorData
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
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    *(
        SensorEntityDescription(
            key=key,
            translation_key=key,
            device_class=device_class,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for key, device_class, unit in (
            ("o3", SensorDeviceClass.OZONE, UnitOfDensity.MICROGRAMS_PER_CUBIC_METER),
            (
                "no2",
                SensorDeviceClass.NITROGEN_DIOXIDE,
                UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
            ),
            (
                "so2",
                SensorDeviceClass.SULPHUR_DIOXIDE,
                UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
            ),
            ("co", SensorDeviceClass.CO, UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER),
        )
    ),
    *(
        SensorEntityDescription(
            key=key,
            translation_key=key,
            device_class=SensorDeviceClass.TIMESTAMP,
        )
        for key in (
            "observed_at",
            "aqi_observed_at",
            "provider_updated_at",
            "sunrise",
            "sunset",
            "nowcast_observed_at",
            "yesterday",
        )
    ),
    *(
        SensorEntityDescription(
            key=key,
            translation_key=key,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
        for key in ("yesterday_high", "yesterday_low", "previous_hour")
    ),
    *(
        SensorEntityDescription(
            key=key, translation_key=key, device_class=SensorDeviceClass.AQI
        )
        for key in ("daily_aqi", "hourly_aqi", "yesterday_aqi")
    ),
    SensorEntityDescription(
        key="rain_distance",
        translation_key="rain_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
    ),
    *(
        SensorEntityDescription(key=key, translation_key=key)
        for key in (
            "primary_pollutant",
            "air_quality_suggestion",
            "alerts",
            "typhoons",
            "nowcast",
            "indices",
            "car_wash",
            "sports",
            "moon_phase",
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiWeatherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors even if the first snapshot lacks optional measurements."""
    async_add_entities(XiaomiSensor(entry, description) for description in DESCRIPTIONS)


class XiaomiSensor(XiaomiWeatherEntity, SensorEntity):
    """Expose a measurement or summary, preserving missing values."""

    def __init__(
        self, entry: XiaomiWeatherConfigEntry, description: SensorEntityDescription
    ) -> None:
        """Initialize stable sensor metadata."""
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | float | datetime | None:
        """Return the current measurement or unknown when absent."""
        key = self.entity_description.key
        if key in ("aqi", "pm25", "pm10"):
            return getattr(self.coordinator.data, key)
        return self.coordinator.data.sensors.get(key, SensorData(None)).value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detached details so consumers cannot change the cache."""
        key = self.entity_description.key
        if key in ("aqi", "pm25", "pm10"):
            # Keep the existing entities' measurements and source metadata together.
            air = self.coordinator.data.raw.get("aqi", {})
            if isinstance(air, dict) and air.get("status", 0) == 0:
                return {
                    "pub_time": air.get("pubTime"),
                    "source": air.get("src"),
                    "description": air.get(f"{key}Desc"),
                }
            return {}
        return deepcopy(
            self.coordinator.data.sensors.get(key, SensorData(None)).attributes
        )
