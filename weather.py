import httpx
from config import OPENWEATHER_API_KEY, CITY


async def get_weather() -> dict:
    """
    Fetch current weather from OpenWeatherMap.
    Returns a dict with temp, high, low, description, city.
    Falls back to placeholder values on any error.
    """
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q":     CITY,
            "appid": OPENWEATHER_API_KEY,
            "units": "imperial",   # Fahrenheit
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        return {
            "temp":        round(data["main"]["temp"]),
            "feels_like":  round(data["main"]["feels_like"]),
            "high":        round(data["main"]["temp_max"]),
            "low":         round(data["main"]["temp_min"]),
            "description": data["weather"][0]["description"].capitalize(),
            "city":        data["name"],
            "error":       False,
        }

    except Exception as exc:
        print(f"[weather] Error fetching weather: {exc}")
        return {
            "temp":        "?",
            "feels_like":  "?",
            "high":        "?",
            "low":         "?",
            "description": "Weather unavailable",
            "city":        CITY,
            "error":       True,
        }
