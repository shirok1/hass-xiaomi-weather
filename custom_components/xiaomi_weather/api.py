"""Asynchronous Xiaomi weather client, independent of Home Assistant.

The endpoint is used by Xiaomi Weather and is not a documented public API.
"""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

URL = "https://weatherapi.market.xiaomi.com/wtr-v3/weather/all"
LOCATION_URL = "https://weatherapi.market.xiaomi.com/wtr-v3/location/city"
CONDITIONS = {
    "0": "sunny",
    "1": "partlycloudy",
    "2": "cloudy",
    "3": "rainy",
    "4": "lightning-rainy",
    "5": "hail",
    "6": "snowy-rainy",
    "7": "rainy",
    "8": "rainy",
    "9": "pouring",
    "10": "pouring",
    "11": "pouring",
    "12": "pouring",
    "13": "snowy",
    "14": "snowy",
    "15": "snowy",
    "16": "snowy",
    "17": "snowy",
    "18": "fog",
    "19": "snowy-rainy",
    "20": "exceptional",
    "21": "rainy",
    "22": "pouring",
    "23": "pouring",
    "24": "pouring",
    "25": "pouring",
    "26": "snowy",
    "27": "snowy",
    "28": "snowy",
    "29": "exceptional",
    "30": "exceptional",
    "31": "exceptional",
    "53": "fog",
}


class XiaomiWeatherError(Exception):
    """A transport or invalid response error."""


@dataclass(frozen=True, slots=True)
class ForecastData:
    """One forecast period in Celsius and UTC."""

    time: datetime
    temperature: float
    low: float | None
    condition: str | None


@dataclass(frozen=True, slots=True)
class WeatherData:
    """Validated snapshot; optional measurements may be unavailable."""

    temperature: float
    condition: str | None
    humidity: float | None
    pressure: float | None
    wind_speed: float | None
    wind_bearing: float | None
    apparent_temperature: float | None
    uv_index: float | None
    daily: tuple[ForecastData, ...]
    hourly: tuple[ForecastData, ...]
    aqi: float | None
    pm25: float | None
    pm10: float | None


def number(value: object) -> float | None:
    """Accept finite numeric values, preserving zero and rejecting sentinels."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) and result != -999 else None


def timestamp(value: str) -> datetime:
    """Require an explicit timezone; never assume the HA server timezone."""
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Missing timezone")
    return result.astimezone(UTC)


def condition(code: object, time: datetime, suns: list[Any]) -> str | None:
    """Resolve clear nights from the forecast location's sunrise and sunset."""
    result = CONDITIONS.get(str(code))
    if result == "sunny":
        for sun in suns:
            rise = timestamp(sun["from"])
            setting = timestamp(sun["to"])
            local_zone = datetime.fromisoformat(sun["from"]).tzinfo
            if time.astimezone(local_zone).date() == rise.astimezone(local_zone).date():
                return "sunny" if rise <= time < setting else "clear-night"
    return result


def values(series: dict[str, Any]) -> list[Any]:
    """Ignore failed sub-series instead of presenting stale provider values."""
    if series.get("status", 0) != 0:
        return []
    result = series.get("value", [])
    if not isinstance(result, list):
        raise ValueError("Expected a forecast array")
    return result


def parse_weather(payload: Any) -> WeatherData:
    """Validate required data and normalize the provider's parallel arrays."""
    try:
        current = payload["current"]
        temp = measurement(current.get("temperature", {}), "℃")
        if temp is None:
            raise ValueError("Missing current temperature")
        now = timestamp(current["pubTime"])
        daily = payload.get("forecastDaily", {})
        suns = values(daily.get("sunRiseSet", {}))
        days: list[ForecastData] = []
        if daily.get("status", 0) == 0:
            temperatures = daily.get("temperature", {})
            if temperatures.get("unit", "℃") != "℃":
                raise ValueError("Unexpected daily temperature unit")
            codes = values(daily.get("weather", {}))
            for index, item in enumerate(values(temperatures)):
                high, low = number(item["from"]), number(item["to"])
                if high is None or index >= len(suns):
                    continue
                local = datetime.fromisoformat(suns[index]["from"])
                date = timestamp(local.replace(hour=0, minute=0, second=0).isoformat())
                code = codes[index]["from"] if index < len(codes) else None
                days.append(ForecastData(date, high, low, CONDITIONS.get(str(code))))
        hourly = payload.get("forecastHourly", {})
        hours: list[ForecastData] = []
        temperatures = hourly.get("temperature", {})
        if hourly.get("status", 0) == 0 and values(temperatures):
            if temperatures.get("unit", "℃") != "℃":
                raise ValueError("Unexpected hourly temperature unit")
            start = timestamp(temperatures["pubTime"])
            weather = hourly.get("weather", {})
            codes = (
                values(weather)
                if weather.get("pubTime") == temperatures["pubTime"]
                else []
            )
            for index, value in enumerate(values(temperatures)):
                high = number(value)
                if high is None:
                    continue
                date = start + timedelta(hours=index)
                code = codes[index] if index < len(codes) else None
                hours.append(
                    ForecastData(date, high, None, condition(code, date, suns))
                )
        wind = current.get("wind", {})
        air = payload.get("aqi", {})
        if air.get("status", 0) != 0:
            air = {}
        return WeatherData(
            temperature=temp,
            condition=condition(current.get("weather"), now, suns),
            humidity=measurement(current.get("humidity", {}), "%"),
            pressure=measurement(current.get("pressure", {}), "hPa"),
            wind_speed=measurement(wind.get("speed", {}), "km/h"),
            wind_bearing=measurement(wind.get("direction", {}), "°"),
            apparent_temperature=measurement(current.get("feelsLike", {}), "℃"),
            uv_index=number(current.get("uvIndex")),
            daily=tuple(days),
            hourly=tuple(hours),
            aqi=number(air.get("aqi")),
            pm25=number(air.get("pm25")),
            pm10=number(air.get("pm10")),
        )
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as err:
        raise XiaomiWeatherError("Invalid weather response") from err


def measurement(value: dict[str, Any], unit: str) -> float | None:
    """Never label a measurement with an unverified unit."""
    if value.get("unit") != unit:
        return None
    return number(value.get("value"))


class XiaomiWeatherClient:
    """Fetch weather using the caller-owned HTTP session."""

    def __init__(
        self, session: ClientSession, city_id: str, latitude: float, longitude: float
    ) -> None:
        """Store location and session without performing I/O."""
        self._session = session
        self._params = {
            "locationKey": f"weathercn:{city_id}",
            "latitude": str(latitude),
            "longitude": str(longitude),
            "days": "15",
            "isLocated": "true",
            "appKey": "weather20151024",
            "sign": "zUFJoAR2ZVrDy1vF3D07",
            "romVersion": "7.2.16",
            "appVersion": "87",
            "alpha": "false",
            "isGlobal": "false",
            "device": "cancro",
            "modDevice": "",
            "locale": "zh_cn",
        }

    async def async_get_weather(self) -> WeatherData:
        """Fetch one snapshot with bounded network time and no internal retries."""
        payload = await _async_get_json(self._session, URL, self._params)
        return parse_weather(payload)


@dataclass(frozen=True, slots=True)
class Location:
    """A mainland China weather location returned by Xiaomi."""

    city_id: str
    name: str
    affiliation: str
    latitude: float
    longitude: float


class XiaomiLocationClient:
    """Resolve city codes, city names and coordinates during configuration only."""

    def __init__(self, session: ClientSession) -> None:
        """Reuse the caller-owned session."""
        self._session = session

    async def async_search(self, name: str) -> list[Location]:
        """Search names without guessing which similarly named city was intended."""
        return await self._async_locations("search", {"name": name})

    async def async_city(self, city_id: str) -> list[Location]:
        """Look up an exact code, discarding unexpected provider matches."""
        locations = await self._async_locations(
            "info", {"locationKey": f"weathercn:{city_id}"}
        )
        return [location for location in locations if location.city_id == city_id]

    async def async_locate(self, latitude: float, longitude: float) -> list[Location]:
        """Resolve coordinates to the provider's city identifier."""
        return await self._async_locations(
            "geo", {"latitude": str(latitude), "longitude": str(longitude)}
        )

    async def _async_locations(
        self, endpoint: str, params: dict[str, str]
    ) -> list[Location]:
        """Validate provider metadata and exclude unsupported global locations."""
        payload = await _async_get_json(
            self._session,
            f"{LOCATION_URL}/{endpoint}",
            {**params, "locale": "zh_cn"},
        )
        try:
            if not isinstance(payload, list):
                raise ValueError("Expected a location list")
            locations: dict[str, Location] = {}
            for item in payload:
                key = item["locationKey"]
                if item.get("status", 0) != 0 or not key.startswith("weathercn:"):
                    continue
                city_id = key.removeprefix("weathercn:")
                latitude, longitude = (
                    number(item["latitude"]),
                    number(item["longitude"]),
                )
                if (
                    re.fullmatch(r"101[0-9]{6}", city_id) is None
                    or latitude is None
                    or not -90 <= latitude <= 90
                    or longitude is None
                    or not -180 <= longitude <= 180
                    or not isinstance(item["name"], str)
                    or not item["name"].strip()
                    or not isinstance(item.get("affiliation", ""), str)
                ):
                    raise ValueError("Invalid location metadata")
                locations[city_id] = Location(
                    city_id,
                    item["name"],
                    item.get("affiliation", ""),
                    latitude,
                    longitude,
                )
            return list(locations.values())
        except (KeyError, TypeError, ValueError, AttributeError) as err:
            raise XiaomiWeatherError("Invalid location response") from err


async def _async_get_json(
    session: ClientSession, url: str, params: dict[str, str]
) -> Any:
    """Bound every provider request and normalize transport failures."""
    try:
        async with session.get(
            url, params=params, timeout=ClientTimeout(total=20)
        ) as response:
            response.raise_for_status()
            return await response.json()
    except (ClientError, TimeoutError, ValueError) as err:
        raise XiaomiWeatherError("Unable to fetch Xiaomi data") from err
