"""
weather.py  -  the "brain" of Skycast.

Two jobs:
  1. FETCH: ask the free Open-Meteo service for weather data (no account or API key needed).
  2. SHAPE: turn its long, messy answer into small, clean pieces the web page can show.

Keeping these two jobs in separate functions means we can test the SHAPE part
with fake data, without needing the internet.
"""

from datetime import datetime

import requests    # lets Python visit web addresses and read the reply

# The two web addresses (endpoints) we talk to
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"   # city name -> coordinates
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"          # coordinates -> weather


class WeatherError(Exception):
    """Our own kind of error. It carries a friendly message the page can show to the user."""


# ---------------------------------------------------------------------------
# 1. WEATHER CODES
# ---------------------------------------------------------------------------
# Open-Meteo describes the sky with a number (a "WMO weather code").
# We translate each number into: a label, a mood, two emoji (day and night)
# and instructions for the animated scene (what to draw).

def _scene(orb=False, clouds=0, rain=0, snow=0, bolt=False, fog=False):
    """Build the 'what to draw' settings for the animated scene.
    orb = sun or moon,  clouds = how many,  rain/snow = how many drops/flakes."""
    return {"orb": orb, "clouds": clouds, "rain": rain, "snow": snow, "bolt": bolt, "fog": fog}


# code: (label, mood, day emoji, night emoji, scene)
WEATHER_CODES = {
    0:  ("Clear sky",               "clear",  "☀️", "🌙", _scene(orb=True)),
    1:  ("Mainly clear",            "clear",  "🌤️", "🌙", _scene(orb=True, clouds=1)),
    2:  ("Partly cloudy",           "cloudy", "⛅", "☁️", _scene(orb=True, clouds=2)),
    3:  ("Overcast",                "cloudy", "☁️", "☁️", _scene(clouds=3)),
    45: ("Foggy",                   "fog",    "🌫️", "🌫️", _scene(clouds=1, fog=True)),
    48: ("Freezing fog",            "fog",    "🌫️", "🌫️", _scene(clouds=1, fog=True)),
    51: ("Light drizzle",           "rain",   "🌦️", "🌧️", _scene(clouds=3, rain=14)),
    53: ("Drizzle",                 "rain",   "🌦️", "🌧️", _scene(clouds=3, rain=20)),
    55: ("Heavy drizzle",           "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=28)),
    56: ("Freezing drizzle",        "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=18)),
    57: ("Heavy freezing drizzle",  "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=28)),
    61: ("Light rain",              "rain",   "🌦️", "🌧️", _scene(clouds=3, rain=24)),
    63: ("Rain",                    "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=36)),
    65: ("Heavy rain",              "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=55)),
    66: ("Freezing rain",           "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=30)),
    67: ("Heavy freezing rain",     "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=45)),
    71: ("Light snow",              "snow",   "🌨️", "🌨️", _scene(clouds=3, snow=22)),
    73: ("Snow",                    "snow",   "🌨️", "🌨️", _scene(clouds=3, snow=34)),
    75: ("Heavy snow",              "snow",   "❄️", "❄️", _scene(clouds=3, snow=50)),
    77: ("Snow grains",             "snow",   "🌨️", "🌨️", _scene(clouds=3, snow=26)),
    80: ("Light showers",           "rain",   "🌦️", "🌧️", _scene(clouds=3, rain=26)),
    81: ("Showers",                 "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=38)),
    82: ("Violent showers",         "rain",   "🌧️", "🌧️", _scene(clouds=3, rain=58)),
    85: ("Snow showers",            "snow",   "🌨️", "🌨️", _scene(clouds=3, snow=34)),
    86: ("Heavy snow showers",      "snow",   "❄️", "❄️", _scene(clouds=3, snow=50)),
    95: ("Thunderstorm",            "storm",  "⛈️", "⛈️", _scene(clouds=3, rain=40, bolt=True)),
    96: ("Thunderstorm with hail",  "storm",  "⛈️", "⛈️", _scene(clouds=3, rain=44, bolt=True)),
    99: ("Severe thunderstorm",     "storm",  "⛈️", "⛈️", _scene(clouds=3, rain=55, bolt=True)),
}

# Used if Open-Meteo ever sends a code we don't know about
UNKNOWN_CODE = ("Unsettled", "cloudy", "🌡️", "🌡️", _scene(clouds=2))


def describe(code, is_day):
    """Turn a weather code (and day/night) into everything the page needs to show it."""
    label, mood, day_icon, night_icon, scene = WEATHER_CODES.get(code, UNKNOWN_CODE)
    return {
        "label": label,
        "icon": day_icon if is_day else night_icon,
        "scene": scene,
        # The theme name picks the colour palette in style.css, e.g. "rain-night"
        "theme": f"{mood}-{'day' if is_day else 'night'}",
    }


# ---------------------------------------------------------------------------
# 2. SMALL HELPER FUNCTIONS
# ---------------------------------------------------------------------------
def _num(value, default=0):
    """Round a number. If the API sent nothing (None), use a default instead of crashing."""
    return default if value is None else round(value)


def _clock(dt):
    """datetime -> '6:08 AM' (no leading zero)."""
    return dt.strftime("%I:%M %p").lstrip("0")


def compass(degrees):
    """Wind direction in degrees -> 'N', 'NE', 'E' ... (8 points)."""
    points = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return points[round(degrees / 45) % 8]


def uv_label(uv):
    """UV index number -> a word people understand."""
    if uv < 3:
        return "Low"
    if uv < 6:
        return "Moderate"
    if uv < 8:
        return "High"
    if uv < 11:
        return "Very high"
    return "Extreme"


def humidity_label(h):
    """Humidity percentage -> a word."""
    if h < 30:
        return "Dry"
    if h < 60:
        return "Comfortable"
    if h < 80:
        return "Humid"
    return "Very humid"


# ---------------------------------------------------------------------------
# 3. FETCH: talk to the internet
# ---------------------------------------------------------------------------
def search_city(name, count=5):
    """Turn a city name like 'Accra' into a list of matching places with coordinates."""
    try:
        response = requests.get(
            GEOCODE_URL,
            params={"name": name, "count": count, "language": "en", "format": "json"},
            timeout=10,          # give up after 10 seconds instead of waiting forever
        )
        response.raise_for_status()      # turns HTTP errors (404, 500...) into Python errors
        data = response.json()           # the reply as a Python dictionary
    except (requests.RequestException, ValueError):
        raise WeatherError("We couldn't reach the search service. Check your internet and try again.")

    places = []
    # data.get("results", []) means: use the "results" list, or an empty list if it's missing
    for item in data.get("results", []):
        places.append({
            "name": item.get("name", ""),
            "country": item.get("country", ""),
            "region": item.get("admin1", ""),       # state or region
            "latitude": item["latitude"],
            "longitude": item["longitude"],
        })
    return places


def fetch_forecast(latitude, longitude, units="metric"):
    """Download the raw forecast for a point on the map."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        # Only ask for what we need: smaller and faster
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
                   "precipitation,weather_code,wind_speed_10m,wind_direction_10m",
        "hourly": "temperature_2m,precipitation_probability,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,"
                 "uv_index_max,precipitation_probability_max,wind_speed_10m_max",
        "timezone": "auto",        # times come back in the place's own local time
        "forecast_days": 7,
    }
    if units == "imperial":
        params["temperature_unit"] = "fahrenheit"
        params["wind_speed_unit"] = "mph"
        params["precipitation_unit"] = "inch"

    try:
        response = requests.get(FORECAST_URL, params=params, timeout=10)
        response.raise_for_status()
        raw = response.json()
    except (requests.RequestException, ValueError):
        raise WeatherError("We couldn't download the forecast right now. Please try again in a moment.")

    # Open-Meteo reports problems inside a normal reply as {"error": true, "reason": "..."}
    if raw.get("error"):
        raise WeatherError("The weather service couldn't handle that request.")
    return raw


# ---------------------------------------------------------------------------
# 4. SHAPE: clean data for the page
# ---------------------------------------------------------------------------
def make_tips(now, today, units):
    """Friendly advice based on the conditions. Returns up to 4 tips."""
    tips = []

    # Thresholds below are in °C and km/h, so convert first if the user chose imperial
    temp_c = (now["temp"] - 32) * 5 / 9 if units == "imperial" else now["temp"]
    wind_kmh = now["wind"] * 1.609 if units == "imperial" else now["wind"]

    if now["theme"].startswith("storm"):
        tips.append({"icon": "⚡", "text": "Thunderstorms around. Stay indoors if you can."})
    if today["rain_chance"] >= 50 or now["scene"]["rain"] > 0:
        tips.append({"icon": "☔", "text": "Take an umbrella with you."})
    if today["uv"] >= 6:
        tips.append({"icon": "🧴", "text": "UV is high. Wear sunscreen and a hat."})
    if temp_c >= 31:
        tips.append({"icon": "🥤", "text": "It's hot. Drink plenty of water."})
    elif temp_c <= 0:
        tips.append({"icon": "🧤", "text": "Freezing. Wrap up with a coat, hat and gloves."})
    elif temp_c <= 12:
        tips.append({"icon": "🧥", "text": "Chilly. A warm jacket is a good idea."})
    if wind_kmh >= 40:
        tips.append({"icon": "🌬️", "text": "Very windy. Hold on to your hat!"})
    if not now["is_day"] and now["scene"]["orb"] and now["scene"]["clouds"] < 2:
        tips.append({"icon": "🌟", "text": "Clear night. Great for stargazing."})

    if not tips:
        tips.append({"icon": "😎", "text": "Lovely conditions. Enjoy your day!"})
    return tips[:4]


def shape_weather(raw, place, units="metric"):
    """Turn Open-Meteo's raw answer into the clean dictionary the template uses."""
    cur = raw["current"]
    hourly = raw["hourly"]
    daily = raw["daily"]

    is_day = bool(cur.get("is_day", 1))
    info = describe(cur.get("weather_code", 0), is_day)
    now_dt = datetime.fromisoformat(cur["time"])        # '2026-11-03T22:15' -> a datetime

    # ----- current conditions -----
    wind_dir = _num(cur.get("wind_direction_10m"))
    humidity = _num(cur.get("relative_humidity_2m"))
    now = {
        "temp": _num(cur.get("temperature_2m")),
        "feels": _num(cur.get("apparent_temperature")),
        "humidity": humidity,
        "humidity_label": humidity_label(humidity),
        "wind": _num(cur.get("wind_speed_10m")),
        "wind_dir": wind_dir,
        "wind_from": compass(wind_dir),
        "wind_to": (wind_dir + 180) % 360,   # the arrow points where the wind is GOING
        "precip": round(cur.get("precipitation") or 0, 1),
        "is_day": is_day,
        "label": info["label"],
        "icon": info["icon"],
        "scene": info["scene"],
        "theme": info["theme"],
        "date_text": f"{now_dt.strftime('%A')}, {now_dt.day} {now_dt.strftime('%B')}",
        "time_text": _clock(now_dt),
    }

    # ----- the next 24 hours -----
    # Hourly times look like '2026-11-03T22:00'. These strings sort correctly as text,
    # so we can find "this hour" by matching the first 13 characters of the current time.
    this_hour = cur["time"][:13] + ":00"
    start = hourly["time"].index(this_hour) if this_hour in hourly["time"] else 0
    hours = []
    for i in range(start, min(start + 24, len(hourly["time"]))):
        h_dt = datetime.fromisoformat(hourly["time"][i])
        h_info = describe(hourly["weather_code"][i], bool(hourly["is_day"][i]))
        hours.append({
            "label": "Now" if i == start else h_dt.strftime("%I %p").lstrip("0"),
            "temp": _num(hourly["temperature_2m"][i]),
            "rain": _num(hourly["precipitation_probability"][i]),
            "icon": h_info["icon"],
        })
    # Bar height (25%-100%) shows how warm each hour is compared with the others
    h_min = min(h["temp"] for h in hours)
    h_max = max(h["temp"] for h in hours)
    h_span = (h_max - h_min) or 1       # "or 1" avoids dividing by zero if all equal
    for h in hours:
        h["bar"] = round(25 + (h["temp"] - h_min) / h_span * 75)

    # ----- the next 7 days -----
    week_low = min(_num(t) for t in daily["temperature_2m_min"])
    week_high = max(_num(t) for t in daily["temperature_2m_max"])
    week_span = (week_high - week_low) or 1

    days = []
    for i, date_text in enumerate(daily["time"]):
        d_dt = datetime.fromisoformat(date_text)
        d_info = describe(daily["weather_code"][i], True)
        low = _num(daily["temperature_2m_min"][i])
        high = _num(daily["temperature_2m_max"][i])
        uv = daily["uv_index_max"][i] or 0

        rise_text = set_text = "--"
        if daily["sunrise"][i] and daily["sunset"][i]:
            rise_text = _clock(datetime.fromisoformat(daily["sunrise"][i]))
            set_text = _clock(datetime.fromisoformat(daily["sunset"][i]))

        days.append({
            "day": "Today" if i == 0 else ("Tomorrow" if i == 1 else d_dt.strftime("%A")),
            "date": f"{d_dt.day} {d_dt.strftime('%b')}",
            "icon": d_info["icon"],
            "label": d_info["label"],
            "low": low,
            "high": high,
            # Position and width of the coloured range bar, as percentages of the week's range
            "left": round((low - week_low) / week_span * 100),
            "width": max(round((high - low) / week_span * 100), 10),
            "rain": _num(daily["precipitation_probability_max"][i]),
            "uv": round(uv),
            "uv_label": uv_label(uv),
            "wind": _num(daily["wind_speed_10m_max"][i]),
            "sunrise": rise_text,
            "sunset": set_text,
        })

    # ----- today's sun journey -----
    sun_pct, daylight = 0, "--"
    sun_up = False
    if daily["sunrise"][0] and daily["sunset"][0]:
        rise = datetime.fromisoformat(daily["sunrise"][0])
        sunset = datetime.fromisoformat(daily["sunset"][0])
        span = (sunset - rise).total_seconds()
        if span > 0:
            sun_pct = max(0, min(100, round((now_dt - rise).total_seconds() / span * 100)))
            hours_up, rest = divmod(int(span), 3600)
            daylight = f"{hours_up}h {rest // 60}m"
        sun_up = rise <= now_dt <= sunset

    today = {
        "high": days[0]["high"],
        "low": days[0]["low"],
        "rain_chance": days[0]["rain"],
        "uv": days[0]["uv"],
        "uv_label": days[0]["uv_label"],
        "uv_pct": min(round(days[0]["uv"] / 11 * 100), 100),   # UV 11 = a full ring
        "sunrise": days[0]["sunrise"],
        "sunset": days[0]["sunset"],
        "sun_pct": sun_pct,
        "sun_up": sun_up,
        "daylight": daylight,
    }

    return {
        "place": place,
        "now": now,
        "today": today,
        "hourly": hours,
        "daily": days,
        "tips": make_tips(now, today, units),
        "theme": now["theme"],
        "units": {
            "temp": "°F" if units == "imperial" else "°C",
            "wind": "mph" if units == "imperial" else "km/h",
            "rain": "in" if units == "imperial" else "mm",
        },
    }


def get_weather(place, units="metric"):
    """The one function main.py calls: fetch, then shape."""
    raw = fetch_forecast(place["latitude"], place["longitude"], units)
    return shape_weather(raw, place, units)
