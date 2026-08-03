from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Europe/Moscow"

CITY_TIMEZONES = {
    "moscow": "Europe/Moscow",
    "москва": "Europe/Moscow",
    "saint petersburg": "Europe/Moscow",
    "st petersburg": "Europe/Moscow",
    "санкт-петербург": "Europe/Moscow",
    "ukhta": "Europe/Moscow",
    "ухта": "Europe/Moscow",
    "sochi": "Europe/Moscow",
    "сочи": "Europe/Moscow",
    "kazan": "Europe/Moscow",
    "казань": "Europe/Moscow",
    "yekaterinburg": "Asia/Yekaterinburg",
    "екатеринбург": "Asia/Yekaterinburg",
    "novosibirsk": "Asia/Novosibirsk",
    "новосибирск": "Asia/Novosibirsk",
    "vladivostok": "Asia/Vladivostok",
    "владивосток": "Asia/Vladivostok",
    "london": "Europe/London",
    "лондон": "Europe/London",
    "berlin": "Europe/Berlin",
    "берлин": "Europe/Berlin",
    "paris": "Europe/Paris",
    "париж": "Europe/Paris",
    "new york": "America/New_York",
    "нью-йорк": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "лос-анджелес": "America/Los_Angeles",
    "istanbul": "Europe/Istanbul",
    "стамбул": "Europe/Istanbul",
    "dubai": "Asia/Dubai",
    "дубай": "Asia/Dubai",
}

COUNTRY_DEFAULT_TIMEZONES = {
    "russia": DEFAULT_TIMEZONE,
    "россия": DEFAULT_TIMEZONE,
    "usa": "America/New_York",
    "us": "America/New_York",
    "united states": "America/New_York",
    "сша": "America/New_York",
    "germany": "Europe/Berlin",
    "германия": "Europe/Berlin",
    "france": "Europe/Paris",
    "франция": "Europe/Paris",
    "turkey": "Europe/Istanbul",
    "турция": "Europe/Istanbul",
}


def infer_timezone(city: str, country: str, fallback: str = DEFAULT_TIMEZONE) -> str:
    normalized_city = city.strip().casefold()
    normalized_country = country.strip().casefold()
    if normalized_city in CITY_TIMEZONES:
        return CITY_TIMEZONES[normalized_city]
    if normalized_country in COUNTRY_DEFAULT_TIMEZONES:
        return COUNTRY_DEFAULT_TIMEZONES[normalized_country]
    return fallback


def get_local_datetime(timezone_name: str) -> datetime:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = UTC
    return datetime.now(timezone)


def describe_time_of_day(hour: int) -> str:
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "daytime"
    if 17 <= hour < 21:
        return "evening"
    if 21 <= hour < 24:
        return "late_evening"
    return "night"


def describe_daylight_context(hour: int) -> str:
    if 5 <= hour < 8:
        return "early light or sunrise may be plausible depending on season"
    if 8 <= hour < 17:
        return "daylight is generally plausible"
    if 17 <= hour < 21:
        return "evening light or sunset may be plausible depending on season"
    return "it is too late for ordinary sunset or daylight outdoor plans"
