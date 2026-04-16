import requests
from datetime import datetime
import os
import json
from dotenv import load_dotenv # Import dotenv

# Load environment variables from .env file
load_dotenv()


# Configuration
WEATHERAPI_KEY = os.getenv("WEATHER_API_KEY") # Load key from environment
DEFAULT_LOCATION = "Laoag City, Ilocos Norte" # Default location for initial load
RAIN_THRESHOLD = 30 # Rain-chance threshold (percent)

# Paths (assuming this file is in the same directory as main.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
STATIC_PATH = os.path.join(current_dir, 'static')

# Icon mapping (filenames are case-sensitive)
ICON_MAPPING = {
    "clear":         "Sunny.png",
    "partly_cloudy": "PartlyCloudy.png",
    "cloudy":        "Cloudy.png",
    "fog":           "Fog.png",
    "freezing":      "Freezing.png",
    "hail":          "Hail.png",
    "rain":          "Rain.png",
    "snow":          "Snow.png",
    "thunderstorm":  "Storm.png",
    "windy":         "Wind.png",
    "typhoon":       "Typhoon.png",
    "default":       "Sunny.png"
}

# WMO weather codes (for reference) - Keep if map_code_to_icon uses them
WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
}

def map_code_to_icon(code, wind_speed_kph, rain_chance):
    """
    Map WMO weather code, wind speed, and precipitation probability
    to one of your icons.
    """
    # Ensure inputs are numbers, default if not
    code = int(code or 0) # Use Python's int()
    wind_speed_kph = float(wind_speed_kph or 0.0) # Use Python's float()
    rain_chance = int(rain_chance or 0) # Use Python's int()

    # 1) Typhoon / extreme wind
    if wind_speed_kph and wind_speed_kph > 60:
        return ICON_MAPPING["typhoon"] if wind_speed_kph > 100 else ICON_MAPPING["windy"]
    # 2) High hail codes
    if code in (96, 99):
        return ICON_MAPPING["hail"]
    # 3) Freezing precipitation
    if code in (56, 57, 66, 67):
        return ICON_MAPPING["freezing"]
    # 4) Fog
    if code in (45, 48):
        return ICON_MAPPING["fog"]
    # 5) Snow codes
    if code in (71, 73, 75, 77, 85, 86):
        return ICON_MAPPING["snow"]
    # 6) Rain/Drizzle codes (including light drizzle)
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        # if low chance, fallback to cloudy
        if rain_chance < RAIN_THRESHOLD:
            return ICON_MAPPING["cloudy"]
        return ICON_MAPPING["rain"]
    # 7) Thunderstorm without hail
    if code == 95:
        return ICON_MAPPING["thunderstorm"]
    # 8) Check rain chance *after* specific precipitation codes
    if rain_chance >= RAIN_THRESHOLD:
        return ICON_MAPPING["rain"]
    # 9) Clear / partly / cloudy based on code
    if code == 0:
        return ICON_MAPPING["clear"]
    if code in (1, 2):
        return ICON_MAPPING["partly_cloudy"]
    if code == 3:
        return ICON_MAPPING["cloudy"]
    # default
    return ICON_MAPPING["default"]

def get_weather_data(api_key, location):
    """Fetch current conditions from WeatherAPI."""
    url = "https://api.weatherapi.com/v1/current.json"
    params = {"key": api_key, "q": location, "aqi": "no"}
    try:
        r = requests.get(url, params=params, timeout=10) # Add timeout
        r.raise_for_status()
        d = r.json()
        # Basic validation of response structure
        if "current" not in d or "location" not in d:
            print(f"WeatherAPI Error: Unexpected response structure for {location}")
            return None
        return {
            "current_temp": d["current"].get("temp_c"),
            "current_uv": d["current"].get("uv"),
            "humidity": d["current"].get("humidity"),
            "visibility": d["current"].get("vis_km"),
            "pressure": d["current"].get("pressure_mb"),
            "wind_speed": d["current"].get("wind_kph"),
            "location": d['location'].get("name", "Unknown Location"),
            "lat": d["location"].get("lat"),
            "lon": d["location"].get("lon"),
            "last_updated": d["current"].get("last_updated"),
            "current_weathercode": d["current"].get("condition", {}).get("code"),
            "rain_chance": 0  # Initialize rain chance (will be updated later)
        }
    except requests.exceptions.Timeout:
        print(f"WeatherAPI Error: Request timed out for {location}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"WeatherAPI Error: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
         print(f"WeatherAPI Error: Could not parse response or missing key - {e}")
         return None

def get_7day_forecast(lat, lon):
    """Fetch 7-day forecast (including weathercode) from Open-Meteo."""
    if lat is None or lon is None:
        print("Open-Meteo Error: Invalid coordinates (lat/lon missing).")
        return None

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 7
    }
    try:
        r = requests.get(url, params=params, timeout=10) # Add timeout
        r.raise_for_status()
        d = r.json()
        # Basic validation
        if "daily" not in d or not all(k in d["daily"] for k in ["time", "weathercode", "temperature_2m_max", "temperature_2m_min", "precipitation_probability_max"]):
             print("Open-Meteo Error: Unexpected response structure.")
             return None

        forecast = []
        num_days = len(d["daily"]["time"])
        if num_days != 7:
             print(f"Open-Meteo Warning: Received {num_days} days forecast instead of 7.")

        for i in range(min(num_days, 7)): # Iterate safely
            forecast.append({
                "date": d["daily"]["time"][i],
                "weathercode": d["daily"]["weathercode"][i],
                "maxtemp_c": d["daily"]["temperature_2m_max"][i],
                "mintemp_c": d["daily"]["temperature_2m_min"][i],
                "rain_chance": d["daily"]["precipitation_probability_max"][i],
            })
        return forecast
    except requests.exceptions.Timeout:
        print(f"Open-Meteo Error: Request timed out for lat={lat}, lon={lon}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Open-Meteo Error: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
         print(f"Open-Meteo Error: Could not parse response or missing key/index - {e}")
         return None

def format_date(date_str):
    """Safely format date string."""
    if not date_str:
        return "Invalid Date"
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a, %b %d")
    except ValueError:
        return "Invalid Date Format"

def generate_html(weather_data, forecast):
    """Generate the HTML content for the weather dashboard."""
    # Safety checks and defaults for weather_data
    current_temp = weather_data.get('current_temp', '--') if weather_data else '--'
    current_uv = weather_data.get('current_uv', 0) if weather_data else 0 # Default UV to 0 for class calculation
    humidity = weather_data.get('humidity', '--') if weather_data else '--'
    wind_speed = weather_data.get('wind_speed', '--') if weather_data else '--'
    visibility = weather_data.get('visibility', '--') if weather_data else '--'
    location_name = weather_data.get('location', 'Location Unknown') if weather_data else 'Location Unknown'
    current_weathercode = weather_data.get('current_weathercode', 0) if weather_data else 0
    current_wind_speed = weather_data.get('wind_speed', 0) if weather_data else 0

    # Update rain chance from forecast if possible
    current_rain_chance = 0
    if weather_data and forecast and forecast[0]:
        current_rain_chance = forecast[0].get("rain_chance", 0)

    uv_class = "uv-low" if current_uv < 3 else "uv-moderate" if current_uv < 6 else "uv-high"
    current_icon = map_code_to_icon(current_weathercode, current_wind_speed, current_rain_chance)

    # --- HTML Start ---
    html_start = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta content="width=device-width, initial-scale=1.0" name="viewport"/>
    <title>Weather Dashboard</title>'''
    # --- CSS Styles (as a separate block for clarity) ---
    css_styles = '''
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        :root {
            --primary-blue: #2B59C3;
            --secondary-blue: #4ECCE6;
            --dark-gray: #2D3142;
            --medium-gray: #4A4E69;
            --light-gray: #F8F9FA;
            --accent-orange: #FF9F1C;
            --success-green: #50C878;
            --warning-yellow: #FFD700;
            --danger-red: #FF6B6B;
        }
        body {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            color: var(--dark-gray);
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .search-container {
            margin-bottom: 30px;
            display: flex; /* Use flexbox for dropdown layout */
            gap: 15px; /* Space between dropdowns */
            flex-wrap: wrap; /* Allow wrapping on smaller screens */
            align-items: center;
            position: relative; /* Needed for suggestions positioning */
            max-width: 700px; /* Adjust width to accommodate button */
            margin-left: auto; /* Center align if needed */
            margin-right: auto;
        }
        /* Style for the main search box container */
        .select-box {
            /* background-color: white; */ /* Handled by inner elements now */
            border-radius: 50px;
            padding: 12px 20px; /* Original padding */
            display: flex;
            align-items: center;
            box-shadow: 0 2px 15px rgba(43,89,195,0.1);
            border: 2px solid var(--primary-blue);
            width: 100%; /* Take full width of container */
            background-color: white; /* Add background here */
            transition: all 0.3s ease;
        }
        /* Style the search icon */
        .search-icon {
            color: var(--primary-blue);
            margin-right:10px;
            font-size:18px;
        }
        /* Style the input field */
        #searchInput {
            border:none;
            outline:none;
            flex:1; /* Take remaining space */
            font-size: 16px;
            padding: 5px;
            color: var(--medium-gray);
            background: transparent; /* Make input background transparent */
        }
        /* Style for the dropdown toggle button */
        #dropdown-toggle-btn {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: var(--primary-blue);
            padding: 0 5px 0 10px; /* Adjust padding */
            margin-left: 5px;
            transition: all 0.3s ease;
        }
        #dropdown-toggle-btn:hover {
            color: var(--secondary-blue);
        }
        /* Suggestions Dropdown Styles */
        #suggestions {
            position: absolute;
            top: calc(100% + 5px); /* Position below the search box with a small gap */
            left: 0;
            right: 0;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 15px; /* Rounded corners */
            box-shadow: 0 8px 15px rgba(43,89,195,0.1);
            max-height: 200px;
            overflow-y: auto;
            z-index: 100; /* Ensure it's above other content */
            display: none; /* Hidden by default */
        }
        .suggestion-item {
            padding: 12px 20px;
            cursor: pointer;
            font-size: 15px;
            color: var(--medium-gray);
        }
        .suggestion-item:hover {
            background-color: #f0f4f8;
            color: var(--primary-blue);
        }
        /* Container for the PSGC dropdowns */
        #location-dropdowns {
            /* display: none; */ /* Controlled by JS, start hidden */
            position: absolute;
            top: calc(100% + 10px); /* Position below search container */
            left: 0;
            right: 0;
            background-color: white;
            border-radius: 15px;
            box-shadow: 0 10px 25px rgba(43,89,195,0.15);
            padding: 20px;
            z-index: 99; /* Below suggestions */
            border: 1px solid #e0e0e0;
            display: none; /* Start hidden */
            flex-direction: column;
            gap: 15px;
        }
        /* Style for select boxes *inside* the dropdown container */
        #location-dropdowns .select-box {
            width: 100%; /* Full width inside the dropdown */
            padding: 0 15px; /* Adjust padding */
            height: 45px; /* Slightly smaller height */
            margin-bottom: 0; /* Remove bottom margin */
            box-shadow: 0 1px 5px rgba(0,0,0,0.05); /* Lighter shadow */
        }
        #location-dropdowns .select-box label {
            font-size: 13px; /* Smaller label */
        }
         #location-dropdowns .select-box select {
            font-size: 15px; /* Smaller font */
        }


        /* End Suggestions Styles */
        .weather-card {
            background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(246,248,249,0.9) 100%);
            border-radius:20px;
            padding:30px;
            box-shadow:0 4px 30px rgba(43,89,195,0.1);
            margin-bottom:30px;
            position:relative;
            overflow:hidden;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.3);
        }
        .location h2 {
            font-size:28px;
            margin-bottom:5px;
            color: var(--primary-blue);
        }
        .date {
            color: var(--medium-gray);
            margin-bottom:20px;
            font-size:18px;
            font-weight: 500;
        }
        .current-temp {
            display:flex;
            align-items:center;
            margin-bottom:20px;
        }
        .current-temp h1 {
            font-size:42px;
            margin:0 15px;
            color: var(--dark-gray);
            background: linear-gradient(45deg, var(--primary-blue), var(--secondary-blue));
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .condition-icon {
            width:50px;
            height:50px;
            filter: drop-shadow(0 2px 4px rgba(43,89,195,0.2));
        }
        .weather-details {
            display:grid;
            grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); /* Responsive grid */
            gap:20px;
            margin-top:30px;
            padding-top:20px;
            border-top:2px solid rgba(43,89,195,0.1);
        }
        .detail p {
            color: var(--medium-gray);
            font-size:14px;
            margin-bottom:5px;
            font-weight: 600;
            text-transform: uppercase; /* Consistent casing */
        }
        .detail h3 {
            font-size:18px;
            font-weight:bold;
            color: var(--dark-gray);
        }
        .forecast-section h3 {
            font-size:24px;
            margin-bottom:20px;
            color: var(--primary-blue);
            padding-left: 10px;
            border-left: 4px solid var(--accent-orange);
        }
        .forecast-container {
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
            gap:15px;
        }
        .forecast-day {
            background: rgba(255,255,255,0.9);
            border-radius:15px;
            padding:20px;
            text-align:center;
            box-shadow:0 4px 20px rgba(43,89,195,0.05);
            border:2px solid rgba(43,89,195,0.1);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .forecast-day:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow:0 8px 25px rgba(43,89,195,0.15);
        }
        .forecast-day.active {
            border-color: var(--secondary-blue);
            background: linear-gradient(135deg, rgba(78,204,230,0.1) 0%, rgba(255,255,255,0.9) 100%);
        }
        .forecast-day p {
            margin-bottom:10px;
            font-size:16px;
            color: var(--medium-gray);
            font-weight: 600;
        }
        .forecast-icon img {
            width:40px;
            height:40px;
            filter: drop-shadow(0 2px 3px rgba(43,89,195,0.2));
        }
        .forecast-temp {
            font-size:18px;
            font-weight:bold;
            color: var(--dark-gray);
            margin: 8px 0;
        }
        .uv-low { color: var(--success-green); }
        .uv-moderate { color: var(--warning-yellow); }
        .uv-high { color: var(--danger-red); }
        .rain-high { color: var(--danger-red); font-weight: 700; }

        .loader {
            display: none; /* Hidden by default */
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 50px;
            height: 50px;
            border: 5px solid #f3f3f3; /* Light grey */
            border-top: 5px solid var(--primary-blue); /* Blue */
            border-radius: 50%;
            animation: spin 1s linear infinite;
            z-index: 1001; /* Above overlay */
        }

        @keyframes spin {
            0% { transform: translate(-50%, -50%) rotate(0deg); }
            100% { transform: translate(-50%, -50%) rotate(360deg); }
        }

        .overlay {
            display: none; /* Hidden by default */
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.7); /* Semi-transparent white */
            z-index: 1000; /* Below loader */
        }
    </style>
    '''
    # --- HTML Body Start ---
    html_body_start = f'''</head>
<body>
    <div class="overlay"></div>
    <div class="loader"></div> <!-- Simplified loader -->

    <div class="container">
        <div class="search-container">
            <!-- Main Search Box with Autocomplete and Dropdown Toggle -->
            <div class="select-box">
                <span class="search-icon">🔍</span>
                <input id="searchInput" type="text" placeholder="Search for a location (e.g., Manila, London)">
                <button id="dropdown-toggle-btn" title="Select location by region">▼</button>
                <div id="suggestions"></div> <!-- Container for suggestions -->
            </div>

            <!-- Hidden Container for PSGC Dropdowns -->
            <div id="location-dropdowns">
                <div class="select-box">
                    <label for="regionSelect">Region:</label>
                    <select id="regionSelect" disabled><option value="">-- Select Region --</option></select>
                </div>
                <div class="select-box">
                    <label for="provinceSelect">Province:</label>
                    <select id="provinceSelect" disabled><option value="">-- Select Province --</option></select>
                </div>
                <div class="select-box">
                    <label for="municipalitySelect">City/Mun:</label>
                    <select id="municipalitySelect" disabled><option value="">-- Select City/Municipality --</option></select>
                </div>
            </div>
        </div> <!-- End Search Container -->

        <div class="weather-card">
            <div class="location">
                <h2>{location_name}</h2>
            </div>
            <p class="date">{datetime.now().strftime("%B %d, %Y")}</p>
            <div class="current-temp">
                <h1>{current_temp}°C</h1>
                <img alt="Condition icon" class="condition-icon" src="../static/icons/{current_icon}">
            </div>
            <div class="weather-details">
                <div class="detail">
                    <p>HUMIDITY</p>
                    <h3>{humidity}%</h3>
                </div>
                <div class="detail">
                    <p>UV INDEX</p>
                    <h3 class="{uv_class}">{current_uv}</h3>
                </div>
                <div class="detail">
                    <p>WIND</p>
                    <h3>{wind_speed} kph</h3>
                </div>
                <div class="detail">
                    <p>VISIBILITY</p>
                    <h3>{visibility} km</h3>
                </div>
            </div>
        </div>

        <div class="forecast-section">
            <h3>7-DAY FORECAST</h3>
            <div class="forecast-container">'''
    # --- Forecast Loop ---
    forecast_html = ""
    if forecast: # Check if forecast data exists
        today_key = format_date(datetime.now().strftime("%Y-%m-%d"))
        for i, day in enumerate(forecast):
            day_date_str = day.get("date", "")
            day_weathercode = day.get('weathercode', 0)
            day_rain_chance = day.get('rain_chance', 0)
            day_max_temp = day.get('maxtemp_c', '--')
            day_min_temp = day.get('mintemp_c', '--')

            date_label = format_date(day_date_str)
            day_name = "TODAY" if date_label == today_key else datetime.strptime(day_date_str, "%Y-%m-%d").strftime("%A").upper() if day_date_str else "N/A"

            icon_file = map_code_to_icon(day_weathercode, 0, day_rain_chance) # Wind speed not available daily from OpenMeteo
            rain_class = "rain-high" if day_rain_chance >= RAIN_THRESHOLD else ""

            max_temp_formatted = f"{day_max_temp:.0f}" if isinstance(day_max_temp, (int, float)) else '--'
            min_temp_formatted = f"{day_min_temp:.0f}" if isinstance(day_min_temp, (int, float)) else '--'

            forecast_html += f'''
                <div class="forecast-day {'active' if i == 0 else ''}">
                    <p>{day_name}</p>
                    <div class="forecast-icon">
                        <img src="../static/icons/{icon_file}" alt="{day_name} icon">
                    </div>
                    <p class="forecast-temp">
                        {max_temp_formatted}° / {min_temp_formatted}°
                    </p>
                    <p class="{rain_class}" style="font-size:14px; margin-top:5px;">
                        Rain: {day_rain_chance}%
                    </p>
                </div>'''
    else:
        forecast_html = "<p>Forecast data not available.</p>" # Placeholder if no forecast

    # --- HTML End Structure ---
    html_end_structure = f'''
            </div>
        </div>
        <p style="text-align:right; color:var(--medium-gray); margin-top:20px;">
            Last Updated: {datetime.now().strftime("%B %d, %Y %I:%M %p")}
        </p>
    </div>'''
    # --- JavaScript Block (Raw String using placeholders) ---
    javascript_template = '''
    <script>
        const WEATHERAPI_KEY = "{{WEATHERAPI_KEY_PLACEHOLDER}}";
        const RAIN_THRESHOLD = {{RAIN_THRESHOLD_PLACEHOLDER}};

        // Elements for Search Bar Autocomplete
        const searchInput = document.getElementById('searchInput');
        const suggestionsDiv = document.getElementById('suggestions');
        // Elements for PSGC Dropdowns
        const dropdownToggleBtn = document.getElementById('dropdown-toggle-btn');
        const locationDropdownsDiv = document.getElementById('location-dropdowns');
        const regionSelect = document.getElementById('regionSelect');
        const provinceSelect = document.getElementById('provinceSelect');
        const municipalitySelect = document.getElementById('municipalitySelect');
        // Common Elements
        const overlay = document.querySelector('.overlay');
        const loader = document.querySelector('.loader');

        let suggestionTimeout; // To handle hiding suggestions

        // --- Helper function to populate dropdown ---
        function populateDropdown(selectElement, items, defaultOptionText) {
            selectElement.innerHTML = `<option value="">-- ${defaultOptionText} --</option>`; // Reset
            if (items && items.length > 0) {
                items.forEach(item => {
                    const option = document.createElement('option');
                    option.value = item.code; // Use code as value
                    option.textContent = item.name;
                    selectElement.appendChild(option);
                });
                selectElement.disabled = false;
            } else {
                 selectElement.disabled = true; // Keep disabled if no items
            }
        }

        // --- Show/Hide Loader ---
        function showLoader(show) {
            overlay.style.display = show ? 'block' : 'none';
            loader.style.display = show ? 'block' : 'none';
        }

        // --- Fetch and Populate Regions on Load (for PSGC dropdowns) ---
        document.addEventListener('DOMContentLoaded', async () => {
            try {
                // No loader here, happens in background
                const response = await fetch('/api/regions'); // Fetch from backend endpoint
                if (!response.ok) throw new Error(`Failed to fetch regions: ${response.statusText}`);
                const regions = await response.json();
                populateDropdown(regionSelect, regions, 'Select Region');
            } catch (error) {
                console.error("Error loading regions:", error.message, error.stack); // More detail
                // Consider a less intrusive error display than alert
                // alert("Could not load regions. Please try refreshing the page.");
            }
        });

        // --- Event Listeners for PSGC Dropdowns ---

        // Region Change (PSGC) -> Populate Provinces OR Cities/Mun for NCR
        regionSelect.addEventListener('change', async (e) => {
            const selectedRegionOption = e.target.options[e.target.selectedIndex];
            const selectedRegionCode = e.target.value;
            const selectedRegionName = selectedRegionOption.text; // Get the region name

            // Reset subsequent dropdowns
            populateDropdown(provinceSelect, [], 'Select Province');
            populateDropdown(municipalitySelect, [], 'Select City/Municipality');
            provinceSelect.disabled = true;
            municipalitySelect.disabled = true;

            // --- Special Handling for NCR ---
            const isNCR = selectedRegionName.toUpperCase().includes("NATIONAL CAPITAL REGION");

            if (selectedRegionCode) {
                try {
                    showLoader(true);
                    if (isNCR) {
                        console.log(`NCR selected (${selectedRegionCode}), fetching region locations...`);
                        const response = await fetch(`/api/region-locations/${selectedRegionCode}`);
                        if (!response.ok) throw new Error(`Failed to fetch NCR locations: ${response.statusText}`);
                        const ncrLocations = await response.json();
                        populateDropdown(municipalitySelect, ncrLocations, 'Select City/Municipality');
                    } else {
                        console.log(`Fetching provinces for region ${selectedRegionCode}...`);
                        const response = await fetch(`/api/provinces/${selectedRegionCode}`);
                        if (!response.ok) throw new Error(`Failed to fetch provinces: ${response.statusText}`);
                        const provinces = await response.json();
                        populateDropdown(provinceSelect, provinces, 'Select Province');
                    }
                } catch (error) {
                    console.error("Error loading provinces/NCR locations:", error.message, error.stack); // More detail
                    alert("Could not load locations for the selected region.");
                } finally {
                    showLoader(false);
                }
            }
        });

        // Province Change (PSGC) -> Populate Cities/Municipalities
        provinceSelect.addEventListener('change', async (e) => {
            const selectedProvinceCode = e.target.value;
            populateDropdown(municipalitySelect, [], 'Select City/Municipality');
            municipalitySelect.disabled = true;

            if (selectedProvinceCode) {
                 try {
                    showLoader(true);
                    const response = await fetch(`/api/cities-municipalities/${selectedProvinceCode}`);
                    if (!response.ok) throw new Error(`Failed to fetch cities/municipalities: ${response.statusText}`);
                    const citiesMun = await response.json();
                    populateDropdown(municipalitySelect, citiesMun, 'Select City/Municipality');
                } catch (error) {
                    console.error(`Error loading cities/municipalities for province ${selectedProvinceCode}:`, error.message, error.stack); // More detail
                    alert("Could not load cities/municipalities for the selected province.");
                } finally {
                    showLoader(false);
                }
            }
        });

        // Municipality/City Change (PSGC) -> Fetch Weather
        municipalitySelect.addEventListener('change', async (e) => {
            const selectedMunicipalityCode = e.target.value;
            const selectedMunicipalityName = municipalitySelect.options[municipalitySelect.selectedIndex]?.text;
            const selectedProvinceName = provinceSelect.disabled ? '' : provinceSelect.options[provinceSelect.selectedIndex]?.text;

            if (selectedMunicipalityCode && selectedMunicipalityName) {
                const location = selectedProvinceName ? `${selectedMunicipalityName}, ${selectedProvinceName}` : selectedMunicipalityName;
                try {
                    locationDropdownsDiv.style.display = 'none'; // Hide the PSGC dropdowns after selection
                    await fetchAndDisplayWeather(location); // Use the combined function
                } catch (error) {
                    // Error handled within fetchAndDisplayWeather
                }
            }
        });

        // --- Event Listener for Dropdown Toggle Button ---
        dropdownToggleBtn.addEventListener('click', () => {
            const isHidden = locationDropdownsDiv.style.display === 'none' || locationDropdownsDiv.style.display === '';
            locationDropdownsDiv.style.display = isHidden ? 'flex' : 'none';
            // Hide autocomplete suggestions if showing PSGC dropdowns
            if (isHidden) {
                suggestionsDiv.style.display = 'none';
            }
        });

        // --- Combined Weather Fetch/Display Function ---
        async function fetchAndDisplayWeather(location) {
            if (!location) return;
            suggestionsDiv.style.display = 'none'; // Hide autocomplete suggestions
            locationDropdownsDiv.style.display = 'none'; // Hide PSGC dropdowns
            searchInput.value = location; // Update search bar text

            try {
                showLoader(true);
                const weatherData = await fetchWeatherDataJS(location);
                if (!weatherData) throw new Error("Could not fetch current weather data. Check console for details.");

                const forecastData = await fetchForecastJS(weatherData.lat, weatherData.lon);
                if (!forecastData) throw new Error("Could not fetch forecast data.");

                updateDashboard(weatherData, forecastData);
            } catch (error) {
                console.error('Error fetching or displaying weather:', error);
                alert(`Failed to fetch weather data for "${location}". Please check the location or try again. Error: ${error.message}`);
            } finally {
                showLoader(false);
            }
        }

        // --- Autocomplete Suggestions Logic (for search bar) ---
        async function fetchWeatherAPISuggestions(query) {
             if (query.length < 3) { // Only search if query is long enough
                suggestionsDiv.style.display = 'none';
                return;
            }
            try {
                const response = await fetch(`https://api.weatherapi.com/v1/search.json?key=${WEATHERAPI_KEY}&q=${encodeURIComponent(query)}`);
                if (!response.ok) {
                    console.warn(`WeatherAPI search failed: ${response.status}`);
                    suggestionsDiv.style.display = 'none'; return;
                }
                const locations = await response.json();
                displaySuggestions(locations);
            } catch (error) {
                console.error("Error fetching suggestions:", error);
                suggestionsDiv.style.display = 'none';
            }
        }

        function displaySuggestions(locations) {
            suggestionsDiv.innerHTML = ''; // Clear previous suggestions
            if (!locations || locations.length === 0) {
                suggestionsDiv.style.display = 'none';
                return;
            }
            locations.forEach(location => {
                const item = document.createElement('div');
                item.classList.add('suggestion-item');
                item.textContent = `${location.name}, ${location.region || ''}${location.region && location.country ? ', ' : ''}${location.country || ''}`;
                item.addEventListener('mousedown', (e) => { // Use mousedown
                    e.preventDefault();
                    fetchAndDisplayWeather(location.name); // Use primary name
                });
                suggestionsDiv.appendChild(item);
            });
            suggestionsDiv.style.display = 'block'; // Show suggestions
            locationDropdownsDiv.style.display = 'none'; // Hide PSGC dropdowns if showing suggestions
        }

        // --- Event Listeners for Search Input Autocomplete ---
        searchInput.addEventListener('input', (e) => {
            clearTimeout(suggestionTimeout);
            suggestionTimeout = setTimeout(() => {
                fetchWeatherAPISuggestions(e.target.value);
            }, 300);
        });

        searchInput.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter') {
                clearTimeout(suggestionTimeout);
                suggestionsDiv.style.display = 'none';
                locationDropdownsDiv.style.display = 'none'; // Hide PSGC dropdowns on Enter
                await fetchAndDisplayWeather(e.target.value);
            }
        });

        // Hide suggestions/dropdowns when clicking outside
        document.addEventListener('click', (e) => {
            const searchContainer = document.querySelector('.search-container');
            // Check if the click is outside the search container entirely
            if (searchContainer && !searchContainer.contains(e.target)) {
                suggestionsDiv.style.display = 'none';
                locationDropdownsDiv.style.display = 'none';
            }
        });

        // Show suggestions again on focus if input is long enough
        searchInput.addEventListener('focus', () => {
             // Hide PSGC dropdowns when focusing on search input
             locationDropdownsDiv.style.display = 'none';
             // Re-fetch suggestions only if input is already populated
             if(searchInput.value.length >= 3) {
                 fetchWeatherAPISuggestions(searchInput.value);
             }
        });


        // --- Client-Side Weather Fetching Functions (Mirroring Python logic) ---
        async function fetchWeatherDataJS(location) {
            try {
                const response = await fetch(
                    `https://api.weatherapi.com/v1/current.json?key=${WEATHERAPI_KEY}&q=${encodeURIComponent(location)}&aqi=no`
                );
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: { message: 'Unknown API error' } }));
                    if (errorData.error && errorData.error.code === 1006) {
                        throw new Error(`Location not found: "${location}"`);
                    }
                    throw new Error(`WeatherAPI request failed: ${response.status} - ${errorData.error?.message || 'Unknown error'}`);
                }
                const data = await response.json();
                if (!data.current || !data.location) {
                    throw new Error("Invalid data received from WeatherAPI");
                }
                // Fetch forecast immediately to get today's rain chance
                // Ensure lat/lon are valid before fetching forecast
                if (data.location.lat == null || data.location.lon == null) {
                    throw new Error("Missing coordinates from WeatherAPI response.");
                }
                const forecastToday = await fetchForecastJS(data.location.lat, data.location.lon);
                const todayRainChance = (forecastToday && forecastToday.length > 0) ? forecastToday[0].rain_chance : 0;

                return {
                    current_temp: data.current.temp_c,
                    current_uv: data.current.uv,
                    humidity: data.current.humidity,
                    visibility: data.current.vis_km,
                    wind_speed: data.current.wind_kph,
                    location: `${data.location.name}`, // Use name directly
                    lat: data.location.lat,
                    lon: data.location.lon,
                    current_weathercode: data.current.condition.code,
                    rain_chance: todayRainChance // Updated rain chance
                };
            } catch (error) {
                console.error("fetchWeatherDataJS error:", error.message); // Log only message for clarity
                return null; // Return null on error
            }
        }

        async function fetchForecastJS(lat, lon) {
             if (lat == null || lon == null) return null; // Use == to check for null or undefined
             try {
                 const response = await fetch(
                    `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=7`
                 );
                 if (!response.ok) {
                     const errorData = await response.json().catch(() => ({ reason: 'Unknown API error' }));
                     throw new Error(`Open-Meteo request failed: ${response.status} - ${errorData.reason || 'Unknown error'}`);
                 }
                 const data = await response.json();
                 if (!data.daily || !data.daily.time) {
                    throw new Error("Invalid data received from Open-Meteo");
                 }
                 // Map the data similarly to the Python version
                 return data.daily.time.map((date, i) => ({
                    date: date,
                    weathercode: data.daily.weathercode[i],
                    maxtemp_c: data.daily.temperature_2m_max[i],
                    mintemp_c: data.daily.temperature_2m_min[i],
                    rain_chance: data.daily.precipitation_probability_max[i]
                 }));
            } catch (error) {
                console.error("fetchForecastJS error:", error.message); // Log only message
                return null; // Return null on error
            }
        }

        // --- Dashboard Update Function ---
        function updateDashboard(weatherData, forecast) {
            if (!weatherData || !forecast || forecast.length === 0) {
                console.error('Cannot update dashboard with invalid data:', weatherData, forecast);
                // Maybe display a message on the page instead of alert
                document.querySelector('.location h2').textContent = 'Error Loading Data';
                return;
            }
            try {
                // Update current weather section
                document.querySelector('.location h2').textContent = weatherData.location || 'Location Unknown'; // Fallback
                document.querySelector('.current-temp h1').textContent = `${weatherData.current_temp ?? '--'}°C`;
                const currentIcon = mapCodeToIconJS( // Use JS version of map function
                    weatherData.current_weathercode ?? 0, // Fallback for code
                    weatherData.wind_speed,
                    weatherData.rain_chance // Use updated rain chance
                );
                document.querySelector('.condition-icon').src = `../static/icons/${currentIcon}`;
                document.querySelector('.condition-icon').alt = currentIcon.replace('.png', ''); // Update alt text

                // Update details section
                document.querySelectorAll('.detail h3')[0].textContent = `${weatherData.humidity ?? '--'}%`;
                const uvValue = weatherData.current_uv ?? 0;
                const uvElement = document.querySelectorAll('.detail h3')[1]; // Ensure this element exists
                uvElement.textContent = uvValue;
                uvElement.className = uvValue < 3 ? 'uv-low' : uvValue < 6 ? 'uv-moderate' : 'uv-high';
                document.querySelectorAll('.detail h3')[2].textContent = `${weatherData.wind_speed ?? '--'} kph`;
                document.querySelectorAll('.detail h3')[3].textContent = `${weatherData.visibility ?? '--'} km`;

                // Update forecast section
                const forecastContainer = document.querySelector('.forecast-container');
                forecastContainer.innerHTML = ''; // Clear previous forecast

                const todayDateStr = new Date().toISOString().split('T')[0]; // Get today's date string YYYY-MM-DD

                forecast.forEach((day, i) => {
                    // Add check for valid day object
                    if (!day) {
                        console.warn(`Skipping invalid forecast day data at index ${i}`);
                        return;
                    }
                    const dayDateStr = day?.date ?? '';
                    const dayName = dayDateStr === todayDateStr ? 'TODAY' : new Date(dayDateStr + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'long' }).toUpperCase(); // Ensure correct date parsing
                    const dayCode = day?.weathercode ?? 0;
                    const dayRainChance = day?.rain_chance ?? 0;
                    const dayMaxTemp = day?.maxtemp_c;
                    const dayMinTemp = day?.mintemp_c;

                    const icon = mapCodeToIconJS(dayCode, 0, dayRainChance); // Wind speed not available daily
                    const rainClass = dayRainChance >= RAIN_THRESHOLD ? 'rain-high' : '';

                    const maxTempFormatted = typeof dayMaxTemp === 'number' ? Math.round(dayMaxTemp) : '--';
                    const minTempFormatted = typeof dayMinTemp === 'number' ? Math.round(dayMinTemp) : '--';

                    forecastContainer.innerHTML += `
                        <div class="forecast-day ${i === 0 ? 'active' : ''}">
                            <p>${dayName}</p>
                            <div class="forecast-icon">
                                <img src="../static/icons/${icon}" alt="${icon.replace('.png', '')} icon">
                            </div>
                            <p class="forecast-temp">
                                ${maxTempFormatted}° / ${minTempFormatted}°
                            </p>
                            <p class="${rainClass}" style="font-size:14px; margin-top:5px;">
                                Rain: ${dayRainChance}%
                            </p>
                        </div>`;
                });

                // Update timestamp
                document.querySelector('p[style*="text-align:right"]').textContent =
                    `Last Updated: ${new Date().toLocaleString()}`;

             } catch (error) {
                console.error('Dashboard Update Error:', error.message, error.stack); // Log stack trace too
                alert('An error occurred while updating the dashboard display.');
            }
        }

        // --- Client-Side Icon Mapping (Mirroring Python logic) ---
        function mapCodeToIconJS(code, windSpeed, rainChance) {
            // Ensure inputs are numbers
            code = Number(code) || 0;
            windSpeed = Number(windSpeed) || 0;
            rainChance = Number(rainChance) || 0;

            // Mapping logic (same as Python)
            if (windSpeed > 60) return windSpeed > 100 ? 'Typhoon.png' : 'Wind.png';
            if ([96, 99].includes(code)) return 'Hail.png';
            if ([56, 57, 66, 67].includes(code)) return 'Freezing.png';
            if ([45, 48].includes(code)) return 'Fog.png';
            if ([71, 73, 75, 77, 85, 86].includes(code)) return 'Snow.png';
            if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) {
                 return rainChance < RAIN_THRESHOLD ? 'Cloudy.png' : 'Rain.png';
            }
            if (code === 95) return 'Storm.png';
            if (rainChance >= RAIN_THRESHOLD) return 'Rain.png'; // Check rain chance after specific codes
            if (code === 0) return 'Sunny.png';
            if ([1, 2].includes(code)) return 'PartlyCloudy.png';
            if (code === 3) return 'Cloudy.png';
            return 'Sunny.png'; // Default icon
        }

    </script>
    '''
    # Inject Python variables into the JavaScript template
    # Ensure WEATHERAPI_KEY is a string, even if None, to avoid JS errors
    weather_api_key_str = WEATHERAPI_KEY if WEATHERAPI_KEY is not None else ""
    javascript_block = javascript_template.replace("{{WEATHERAPI_KEY_PLACEHOLDER}}", weather_api_key_str)
    javascript_block = javascript_block.replace("{{RAIN_THRESHOLD_PLACEHOLDER}}", str(RAIN_THRESHOLD))


    # --- Combine Parts ---
    # Ensure all parts are strings before concatenation
    return str(html_start) + str(css_styles) + str(html_body_start) + str(forecast_html) + str(html_end_structure) + str(javascript_block)

def generate_weather_dashboard(output_dir=None):
    """Fetches data and generates the weather dashboard HTML file."""
    target_static_path = output_dir or STATIC_PATH
    print("Generating weather dashboard...")
    # Check if the API key was loaded successfully
    if not WEATHERAPI_KEY:
        print("❌ Error: WEATHER_API_KEY not found in environment variables. Please check your .env file.")
        # Optionally, raise an error or return early
        # Create a basic error HTML if key is missing
        error_html = "<html><body><h1>Configuration Error</h1><p>Weather API Key is missing. Please check server configuration.</p></body></html>"
        try:
            os.makedirs(target_static_path, exist_ok=True)
            output_file = os.path.join(target_static_path, "weather_updated.html")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(error_html)
            print(f"⚠️ Weather dashboard generated with error message: {output_file}")
        except Exception as e:
            print(f"Error writing error HTML file: {e}")
        return # Stop generation

    # Fetch initial weather for the default location
    weather_data = get_weather_data(WEATHERAPI_KEY, DEFAULT_LOCATION)
    if not weather_data:
        print("Failed to retrieve initial current weather. Dashboard may be incomplete.")
        # Proceed with empty data or defaults? Let's proceed but log it.
        weather_data = {} # Use empty dict to avoid errors in generate_html

    # Fetch initial forecast using coordinates from weather_data if available
    forecast = None
    if weather_data and weather_data.get("lat") is not None and weather_data.get("lon") is not None:
        forecast = get_7day_forecast(weather_data["lat"], weather_data["lon"])
    if not forecast:
        print("Failed to retrieve initial forecast. Dashboard may be incomplete.")
        forecast = [] # Use empty list

    # Generate HTML content
    try:
        html_content = generate_html(weather_data, forecast)
    except Exception as e:
        print(f"Error during HTML generation: {e}")
        # Optionally, create a basic error HTML
        html_content = f"<html><body><h1>Error generating weather dashboard</h1><p>{e}</p></body></html>"

    # Save the generated HTML
    try:
        os.makedirs(target_static_path, exist_ok=True) # Ensure static directory exists
        output_file = os.path.join(target_static_path, "weather_updated.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ Weather dashboard generated successfully: {output_file}")
    except IOError as e:
         print(f"Error writing weather dashboard file: {e}")
    except Exception as e:
         print(f"An unexpected error occurred while saving the file: {e}")

# Allow running this file directly for testing generation
if __name__ == "__main__":
    generate_weather_dashboard()
