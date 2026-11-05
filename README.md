# Skycast

A beautiful, animated weather dashboard built with **Python (FastAPI), HTML and CSS only** (no JavaScript).

![Skycast screenshot](docs/Screenshot%202.png)
![Skycast screenshot](docs/Screenshot%201.png)

## Features

- Search any city in the world (free Open-Meteo API, no key needed)
- The whole page changes mood with the weather: sunny, clear night, cloudy, rain, thunderstorm, snow, fog
- Animated sky: rotating sun rays, drifting clouds, falling rain and snow, twinkling stars, lightning
- Current conditions, hourly forecast for the next 24 hours, and a 7-day forecast
- Humidity and UV rings, wind compass, sunrise/sunset progress bar
- Smart tips ("Take an umbrella", "UV is high")
- °C / °F switch, "Surprise me" random city, and recently viewed cities (saved in a cookie)

## Project structure

```
skycast/
├── docs            # screenshots
├── static/
│   └── style.css      # themes, layout, animations
├── templates/
│   └── index.html     # page template (Jinja2)
├── .gitignore    
├── main.py            # routes (FastAPI)
├── README.md           # instructions
├── requirements.txt            
├── test_weather.py    # tests that run without internet
└── weather.py         # fetches and shapes weather data
```

## Run it

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

## Credits

Weather data by [Open-Meteo.com](https://open-meteo.com/) (free for non-commercial use).
