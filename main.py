
"""
main.py - The main web server for Skycast.

We receives requests from the user's browser here and the gets the required weather
information, and sends everything to the webpage.

"""

# Import json so we can convert Python data into JSON and JSON into Python data.
# We use this when saving and reading recently viewed cities.
import json

# Import random to help us select a random city.
import random

# Optional allows us to say that a value can either be a specific typ or None like nothing.
from typing import Optional

# quote() makes text safe to store in a URL or cookie.
# unquote() reverses that process.
# urlencode() converts information into a URL-friendly format.
from urllib.parse import quote, unquote, urlencode

# Import FastAPI to create our web application and from FASTAPI, Request information sent by the user's browser.
from fastapi import FastAPI, Request

# RedirectResponse here allows us to move to another web address.
from fastapi.responses import RedirectResponse

# We serve files by importing StaticFiles 
from fastapi.staticfiles import StaticFiles

# Import Jinja2Templates to helps connect our Python code to HTML pages.
from fastapi.templating import Jinja2Templates

# Import the functions and error handler we created in weather.py.
# These help us search for cities and retrieve their weather information.
from weather import WeatherError, describe, get_weather, search_city



# Create our FastAPI application and give it the name Skycast.
app = FastAPI(title="Skycast")

# Tell FastAPI where to find our static files.
# Static files include CSS, JavaScript and images.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Tell FastAPI where our HTML templates are stored.
templates = Jinja2Templates(directory="templates")



# CITY LISTS here
# This function creates a dictionary containing information about a city.
# Instead of writing the same dictionary structure repeatedly, we can simply call _city() and provide the city's details.
def _city(name, country, lat, lon):
    return {
        "name": name,
        "country": country,
        "latitude": lat,
        "longitude": lon
    }


# These are some of the cities we want to display on our dashboard.
# Their coordinates are already stored, so anyone can click on them without having to search for the city again.
POPULAR_CITIES = [
    _city("Accra", "Ghana", 5.5560, -0.1969),
    _city("Kumasi", "Ghana", 6.6885, -1.6244),
    _city("Lagos", "Nigeria", 6.5244, 3.3792),
    _city("Nairobi", "Kenya", -1.2921, 36.8219),
    _city("London", "United Kingdom", 51.5072, -0.1276),
    _city("New York", "United States", 40.7128, -74.0060),
    _city("Tokyo", "Japan", 35.6762, 139.6503),
    _city("Reykjavik", "Iceland", 64.1466, -21.9426),
]


# These are the cities available when someone clicks "Surprise me".
# We start with our popular cities and add some more cities around the world.
WORLD_CITIES = POPULAR_CITIES + [
    _city("Dubai", "United Arab Emirates", 25.2048, 55.2708),
    _city("Sydney", "Australia", -33.8688, 151.2093),
    _city("Cape Town", "South Africa", -33.9249, 18.4241),
    _city("Rio de Janeiro", "Brazil", -22.9068, -43.1729),
    _city("Mumbai", "India", 19.0760, 72.8777),
    _city("Cairo", "Egypt", 30.0444, 31.2357),
    _city("Singapore", "Singapore", 1.3521, 103.8198),
    _city("Moscow", "Russia", 55.7558, 37.6173),
    _city("Mexico City", "Mexico", 19.4326, -99.1332),
    _city("Anchorage", "United States", 61.2181, -149.9003),
    _city("Paris", "France", 48.8566, 2.3522),
    _city("Toronto", "Canada", 43.6532, -79.3832),
]


# NOTE:
# SOME HELPER FUNCTIONS
# Here we use the function below to create a web address for a particular city.
# It includes the city's coordinates, name, country and temperature unit.
def place_url(place, units):

    # Collect the city's information into a dictionary.
    query = {
        "lat": place["latitude"],
        "lon": place["longitude"],
        "name": place["name"],
        "country": place.get("country", ""),
        "units": units,
    }

    # urlencode() changes the dictionary into URL-friendly information.
    # so that for example..... spaces and special characters are handled correctly.
    return "/?" + urlencode(query)


# We then create a function that takes a list of cities and gives each city its own URL.
# This makes it easier for our HTML page to create clickable city links.
def with_urls(places, units):
    return [
        {**p, "url": place_url(p, units)}
        for p in places
    ]


# This function reads the recently viewed cities from the browser.
# We store this information in a cookie.
def read_recents(request):

    # Look for a cookie called "recent" in the user's browser.
    raw = request.cookies.get("recent")

    # If there is no recent history, return an empty list.
    if not raw:
        return []

    try:
        # Convert the cookie back into normal text.
        # Then convert the JSON text into a Python list.
        items = json.loads(unquote(raw))

        # Rebuild the city information instead of blindly trusting
        # whatever information comes from the browser.
        return [
            _city(
                str(p["name"])[:60],
                str(p.get("country", ""))[:60],
                float(p["latitude"]),
                float(p["longitude"])
            )
            for p in items
        ][:6]  # Only keep the six most recent cities.

    # If the cookie is damaged or contains missing information,
    # simply return an empty list instead of crashing the application.
    except (ValueError, TypeError, KeyError):
        return []


# This function adds a newly viewed city to the recent history.
def add_recent(recents, place):

    # Create a clean copy of the city information.
    new = _city(
        place["name"],
        place.get("country", ""),
        place["latitude"],
        place["longitude"]
    )

    # Code below checks  the existing history and remove the city if it is already there.
    # This prevents the same city from appearing multiple times.
    others = [
        p for p in recents
        if (
            round(p["latitude"], 2),
            round(p["longitude"], 2)
        ) != (
            round(new["latitude"], 2),
            round(new["longitude"], 2)
        )
    ]

    # Puts the newest city first and keep only six cities.
    return ([new] + others)[:6]



# ROUTE 1: THE MAIN WEATHER DASHBOARD
#
# This tells FastAPI that this function should run whenever someone visits the main address of our application (/).
@app.get("/")
def home(
    request: Request,

    # The city name entered into the search box.
    q: str = "",

    # Latitude and longitude are used when a user selects a city directly.
    # Optional means they can be provided or left empty.
    lat: Optional[float] = None,
    lon: Optional[float] = None,

    # The name and country of the selected city.
    name: str = "",
    country: str = "",

    # Choose how temperature should be displayed.
    # Metric means Celsius, while imperial means Fahrenheit.
    units: str = "metric",
):

    # Makes sure a supported temperature unit is selected.
    # If anything else is provided, use metric by default.
    if units not in ("metric", "imperial"):
        units = "metric"

    # Gets the  recently viewed cities.
    recents = read_recents(request)

    # Start with empty values.
    # We will fill these variables as we process requests.
    place, weather, error, alternatives = None, None, None, []


    # STEP 1: FIND OUT WHICH CITY THE USER WANTS
    # 
    # First, check whether a city is selected  using coordinates.
    # This usually happens when someone clicks a popular city.
    if lat is not None and lon is not None:

        place = {
            "name": name or "Selected place",
            "country": country,
            "latitude": lat,
            "longitude": lon
        }

    # If no coordinates were provided, check whether a city name was typed into the search box.
    elif q.strip():

        try:
            # Search for the city using the function from weather.py.
            # strip() removes unnecessary spaces before and after the name.
            matches = search_city(q.strip())

            # If we find a matching city, select the first result.
            if matches:
                place = matches[0]

                # Keep the other matching cities as alternatives.
                # These can be displayed if the user wants another location.
                alternatives = matches[1:]

            # If no city is found, prepare a helpful error message.
            else:
                error = (
                    f"We couldn't find “{q.strip()}”. "
                    "Check the spelling or try a nearby city."
                )

        # If the city search fails because of a weather/API error,
        # catch the error and display its message.
        except WeatherError as problem:
            error = str(problem)


    # STEP 2: GET THE WEATHER INFORMATION
    # 
    # Only request weather information if we have found a city.
    if place:

        try:
            # Get the weather information for the selected city.
            # The second argument tells the function whether to use
            # Celsius or Fahrenheit.
            weather = get_weather(place, units)

            # Add this city to the  recently viewed cities.
            recents = add_recent(recents, place)

        # If something goes wrong while getting the weather,
        # catch the error instead of allowing the application to crash.
        except WeatherError as problem:
            error = str(problem)


    # STEP 3: CHOOSE THE APPEARANCE OF THE DASHBOARD
    # 
    # here, If we successfully received weather information, we then use the weather conditions to decide the page's appearance.
    if weather:

        theme = weather["theme"]
        is_day = weather["now"]["is_day"]
        scene = weather["now"]["scene"]

    # If no weather information is available, show the default
    # landing-page appearance instead.
    else:
        landing = describe(1, True)

        theme = landing["theme"]
        is_day = True
        scene = landing["scene"]


    # STEP 4: HERE WE PREPARE INFORMATION FOR THE HTML PAGE
    # 
    # Determine the alternative temperature unit.
    # If Celsius is beign used, offer Fahrenheit, and vice versa.
    other = "imperial" if units == "metric" else "metric"

    # Use an empty dictionary if no city has been selected.
    place_for_links = place or {}

    # Collect all the information our HTML template needs.
    # This dictionary is called the context.
    context = {
        "q": q,
        "units": units,
        "weather": weather,
        "error": error,
        "theme": theme,
        "is_day": is_day,
        "scene": scene,

        # Popular cities with clickable URLs.
        "popular": with_urls(POPULAR_CITIES, units),

        # Recently viewed cities with clickable URLs.
        "recents": with_urls(recents, units),

        # Other possible city matches.
        "alternatives": with_urls(alternatives, units),

        # Links for switching between Celsius and Fahrenheit.
        "metric_url": (
            place_url(place_for_links, "metric")
            if place else "/?units=metric"
        ),

        "imperial_url": (
            place_url(place_for_links, "imperial")
            if place else "/?units=imperial"
        ),

        # Link for selecting a random city.
        "random_url": f"/random?units={units}",

        # The alternative temperature unit.
        "other_units": other,
    }

    # Send the information to our HTML dashboard.
    # index.html uses the context dictionary to display the information.
    response = templates.TemplateResponse(
        request,
        "index.html",
        context
    )


    
    # STEP 5: SAViNG RECENTLY VIEWED CITIES
    # 

    if weather:

        # Create a cookie called "recent" in the user's browser.
        response.set_cookie(
            "recent",

            # Convert the city list into JSON and make it safe for a cookie.
            quote(json.dumps(recents)),

            # Keep this cookie for 90 days.
            max_age=60 * 60 * 24 * 90,

            # Prevent JavaScript in the browser from directly reading the cookie.
            httponly=True,

            # Provide additional protection when the browser sends the cookie.
            samesite="lax",
        )

    # Finally, send the completed webpage back to the  browser.
    return response


# 
# ROUTE 2: SURPRISE ME
# 
# This route is used when someone wants to explore a random city.
# It selects a city and redirects to the weather dashboard.
@app.get("/random")
def surprise(units: str = "metric"):

    # Make sure the temperature unit is valid.
    if units not in ("metric", "imperial"):
        units = "metric"

    # Select a random city from our world cities list.
    # Build its dashboard URL and redirect the user there.
    return RedirectResponse(
        url=place_url(random.choice(WORLD_CITIES), units),
        status_code=303
    )
