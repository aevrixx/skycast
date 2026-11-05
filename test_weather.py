"""
test_weather.py  -  tests that run WITHOUT internet.

We feed shape_weather() a small fake answer shaped like Open-Meteo's, and check the result.
Run them with:   pytest        (install with: pip install pytest)
"""

from weather import compass, describe, humidity_label, shape_weather, uv_label

PLACE = {"name": "Testville", "country": "Nowhere", "region": "", "latitude": 1.0, "longitude": 2.0}


def fake_raw(code=0, is_day=1, temp=28.4):
    """Build a fake Open-Meteo reply: 7 days, 168 hourly values."""
    hourly_times = [f"2026-11-{3 + h // 24:02d}T{h % 24:02d}:00" for h in range(168)]
    days = [f"2026-11-{3 + d:02d}" for d in range(7)]
    return {
        "current": {
            "time": "2026-11-03T10:15", "temperature_2m": temp, "relative_humidity_2m": 64,
            "apparent_temperature": 30.1, "is_day": is_day, "precipitation": 0.0,
            "weather_code": code, "wind_speed_10m": 12.3, "wind_direction_10m": 220,
        },
        "hourly": {
            "time": hourly_times,
            "temperature_2m": [25 + (h % 24) / 3 for h in range(168)],
            "precipitation_probability": [10] * 168,
            "weather_code": [1] * 168,
            "is_day": [1 if 6 <= h % 24 < 18 else 0 for h in range(168)],
        },
        "daily": {
            "time": days,
            "weather_code": [0, 1, 2, 3, 61, 63, 95],
            "temperature_2m_max": [31, 30, 29, 28, 27, 26, 30],
            "temperature_2m_min": [23, 22, 22, 21, 21, 20, 22],
            "sunrise": [f"{d}T06:08" for d in days],
            "sunset": [f"{d}T17:58" for d in days],
            "uv_index_max": [9, 8, 7, 6, 3, 2, 5],
            "precipitation_probability_max": [10, 20, 40, 60, 80, 90, 70],
            "wind_speed_10m_max": [15, 18, 20, 22, 25, 30, 28],
        },
    }


def test_describe_picks_day_or_night_icon():
    assert describe(0, True)["icon"] == "☀️"
    assert describe(0, False)["icon"] == "🌙"
    assert describe(0, False)["theme"] == "clear-night"


def test_unknown_code_does_not_crash():
    assert describe(12345, True)["label"] == "Unsettled"


def test_compass_points():
    assert compass(0) == "N"
    assert compass(90) == "E"
    assert compass(225) == "SW"
    assert compass(359) == "N"


def test_labels():
    assert uv_label(1) == "Low" and uv_label(12) == "Extreme"
    assert humidity_label(20) == "Dry" and humidity_label(90) == "Very humid"


def test_shape_gives_24_hours_and_7_days():
    data = shape_weather(fake_raw(), PLACE)
    assert len(data["hourly"]) == 24
    assert len(data["daily"]) == 7
    assert data["hourly"][0]["label"] == "Now"
    assert data["daily"][0]["day"] == "Today"


def test_current_values_are_rounded():
    data = shape_weather(fake_raw(temp=28.4), PLACE)
    assert data["now"]["temp"] == 28
    assert data["now"]["wind_from"] == "SW"


def test_theme_follows_weather():
    assert shape_weather(fake_raw(code=95, is_day=0), PLACE)["theme"] == "storm-night"
    assert shape_weather(fake_raw(code=73), PLACE)["theme"] == "snow-day"


def test_imperial_units_label():
    assert shape_weather(fake_raw(), PLACE, "imperial")["units"]["temp"] == "°F"