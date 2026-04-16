from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from data_downloader.downloader import PeriodicMongoDBDataDownloader
from data_processing import load_and_preprocess_data, generate_analysis_maps, get_hotspot_data
import os
import asyncio
import tempfile
from dotenv import load_dotenv
import requests
from weather_dashboard_generator import generate_weather_dashboard
from psgc_router import router as psgc_api_router # Import the router
from static_forecast import build_static_forecast_payload, generate_static_forecast_graphs


# Load environment variables
load_dotenv()


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
IS_VERCEL = env_flag("VERCEL")
RUNTIME_PATH = os.path.join(tempfile.gettempdir(), "cv3") if IS_VERCEL else current_dir

DATA_PATH = os.getenv("DATA_PATH", os.path.join(RUNTIME_PATH, 'data'))
STATIC_ASSETS_PATH = os.path.join(current_dir, 'static')
STATIC_PATH = os.getenv(
    "GENERATED_STATIC_PATH",
    os.path.join(RUNTIME_PATH, 'static') if IS_VERCEL else STATIC_ASSETS_PATH
)
ENABLE_FORECASTING = env_flag("ENABLE_FORECASTING", False)
ENABLE_PERIODIC_UPDATES = env_flag("ENABLE_PERIODIC_UPDATES", not IS_VERCEL)
FRONTEND_ORIGIN = "https://aretex-risk-radar.vercel.app"

os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(STATIC_PATH, exist_ok=True)

# Downloader
downloader = PeriodicMongoDBDataDownloader(output_dir=DATA_PATH)

# FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_ASSETS_PATH), name="static")
app.include_router(psgc_api_router) # Re-include the PSGC routes
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

default_allowed_origins = [
    "http://localhost:8000",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5173",
    FRONTEND_ORIGIN,
]

configured_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
allowed_origins = configured_origins or default_allowed_origins
if "*" not in allowed_origins and FRONTEND_ORIGIN not in allowed_origins:
    allowed_origins.append(FRONTEND_ORIGIN)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials="*" not in allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"]
)


def run_forecasting() -> None:
    from forecasting import load_crime_data, predict_and_plot_crime_trends

    forecast_df = load_crime_data(DATA_PATH)
    predict_and_plot_crime_trends(forecast_df, forecast_days=30, output_path=STATIC_PATH)


def run_static_forecasting() -> None:
    generate_static_forecast_graphs(DATA_PATH, STATIC_PATH)


def get_forecast_file(filename: str) -> FileResponse:
    forecast_path = os.path.join(STATIC_PATH, filename)
    if not os.path.exists(forecast_path):
        run_static_forecasting()
    if not os.path.exists(forecast_path):
        raise HTTPException(404, detail="Forecast graph is not available yet.")
    return FileResponse(forecast_path)


@app.on_event("startup")
async def startup_event():
    try:
        print("Initializing application...")
        print(f"Runtime data path: {DATA_PATH}")
        print(f"Generated static path: {STATIC_PATH}")
        print(f"Forecasting enabled: {ENABLE_FORECASTING}")
        downloader.start_single_download(['crime_records', 'crime_types', 'locations'])

        # Load and preprocess data
        df, kmeans_model = load_and_preprocess_data(DATA_PATH)
        if df.empty:
            raise ValueError("No valid data available")
        print(f"Processed {len(df)} records")

        # Generate maps
        generate_analysis_maps(df, kmeans_model, DATA_PATH, STATIC_PATH)

        # Forecasting
        if ENABLE_FORECASTING:
            run_forecasting()
        else:
            print("Crime forecasting is paused. Set ENABLE_FORECASTING=true to generate forecasts.")
            run_static_forecasting()

        # Generate weather dashboard
        generate_weather_dashboard(output_dir=STATIC_PATH)  # Call the function here

        app.state.initialized = True
        print("Maps and weather dashboard generated successfully")

        # Periodic Update
        async def periodic_update():
            while True:
                await asyncio.sleep(1800)  # 30 min
                try:
                    print("Periodic update starting...")
                    downloader.start_single_download(['crime_records', 'crime_types', 'locations'])
                    new_df, new_kmeans = load_and_preprocess_data(DATA_PATH)

                    generate_analysis_maps(new_df, new_kmeans, DATA_PATH, STATIC_PATH)
                    if ENABLE_FORECASTING:
                        run_forecasting()
                    else:
                        run_static_forecasting()

                    # Re-generate weather dashboard periodically as well? Optional.
                    # generate_weather_dashboard(output_dir=STATIC_PATH)

                    app.state.initialized = True
                    print("Periodic update done!")
                except Exception as e:
                    print(f"Periodic update failed: {str(e)}")

        if ENABLE_PERIODIC_UPDATES:
            asyncio.create_task(periodic_update())
        else:
            print("Periodic updates are disabled for this runtime.")

    except Exception as e:
        app.state.initialized = False
        print(f"Initialization failed: {str(e)}")

# DASHBOARD ROUTES
@app.get("/", response_class=HTMLResponse)
async def backend_test_ui():
    initialized = getattr(app.state, "initialized", False)
    status = "Ready" if initialized else "Initializing or startup failed"
    forecasting_mode = "Prophet training enabled" if ENABLE_FORECASTING else "Static graphs, training paused"
    periodic_mode = "Enabled" if ENABLE_PERIODIC_UPDATES else "Disabled"

    return HTMLResponse(f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Aretex Risk Radar Backend</title>
    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f5f7fb;
            color: #182033;
        }}
        main {{
            width: min(960px, calc(100% - 32px));
            margin: 40px auto;
        }}
        header {{
            padding: 24px;
            background: #ffffff;
            border: 1px solid #d9e2ef;
            border-radius: 8px;
        }}
        h1 {{
            margin: 0 0 8px;
            font-size: 28px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 14px;
            margin-top: 18px;
        }}
        a, .panel {{
            display: block;
            padding: 16px;
            border: 1px solid #d9e2ef;
            border-radius: 8px;
            background: #ffffff;
            color: #0f4c81;
            text-decoration: none;
        }}
        a:hover {{
            border-color: #0f4c81;
        }}
        small {{
            display: block;
            margin-top: 6px;
            color: #5c6b82;
        }}
        code {{
            background: #eef3f8;
            padding: 2px 5px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <main>
        <header>
            <h1>Aretex Risk Radar Backend</h1>
            <p>Status: <strong>{status}</strong></p>
            <p>Forecasting: <strong>{forecasting_mode}</strong></p>
            <p>Periodic updates: <strong>{periodic_mode}</strong></p>
            <p>Frontend allowed origin: <code>{FRONTEND_ORIGIN}</code></p>
        </header>
        <section class="grid">
            <a href="/health">Health Check<small>JSON status response</small></a>
            <a href="/dashboard">Legacy Dashboard<small>Backend dashboard template</small></a>
            <a href="/api/heatmap">Heatmap<small>Generated map HTML</small></a>
            <a href="/api/hotspot-map">Hotspot Map<small>Generated hotspot HTML</small></a>
            <a href="/api/status-map">Status Map<small>Generated status HTML</small></a>
            <a href="/api/forecast/crime-trend">Crime Trend Graph<small>Static graph while training is paused</small></a>
            <a href="/api/forecast/top-locations">Top Locations Graph<small>Static graph while training is paused</small></a>
            <a href="/api/forecast/data">Forecast JSON<small>Data for frontend charts</small></a>
            <a href="/weather">Weather Dashboard<small>Generated weather HTML</small></a>
        </section>
    </main>
</body>
</html>""")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        return HTMLResponse("<h1>Initializing... Please refresh shortly</h1>", status_code=503)
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/heat-map", response_class=HTMLResponse)
async def get_heat_map():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return FileResponse(os.path.join(STATIC_PATH, 'heatmap.html'))

@app.get("/hotspot-map", response_class=HTMLResponse)
async def get_hotspot_map():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return FileResponse(os.path.join(STATIC_PATH, 'hotspot_map.html'))

@app.get("/status-map", response_class=HTMLResponse)
async def get_status_map():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return FileResponse(os.path.join(STATIC_PATH, 'status_map.html'))

@app.get("/forecast/crime-trend", response_class=HTMLResponse)
async def get_crime_trend_forecast():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return get_forecast_file('crime_trend_forecast.html')

@app.get("/forecast/top-locations", response_class=HTMLResponse)
async def get_top_locations_forecast():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return get_forecast_file('top_locations_crime.html')

# Endpoint to trigger weather dashboard generation manually (optional)
@app.get("/generate-weather-dashboard", response_class=JSONResponse)
async def generate_weather_dashboard_api_trigger():
    try:
        generate_weather_dashboard(output_dir=STATIC_PATH)
        return {"status": "success", "message": "Weather dashboard generated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate weather dashboard: {str(e)}")

# Endpoint to serve the generated weather dashboard
@app.get("/weather", response_class=HTMLResponse) # Changed path to /weather
async def get_weather_dashboard_page():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
         # Allow access even if main init failed, as weather might be independent
         print("Warning: Serving weather dashboard while main app might not be fully initialized.")
    weather_file = os.path.join(STATIC_PATH, 'weather_updated.html')
    if not os.path.exists(weather_file):
        # Optionally generate it on the fly if it doesn't exist
        try:
            generate_weather_dashboard(output_dir=STATIC_PATH)
        except Exception as e:
             raise HTTPException(status_code=500, detail=f"Weather dashboard not found and failed to generate: {str(e)}")
    return FileResponse(weather_file)


@app.get("/hotspot-data", response_class=JSONResponse)
async def hotspot_data():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    try:
        df, kmeans_model = load_and_preprocess_data(DATA_PATH)
        return get_hotspot_data(df, kmeans_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get hotspot data: {str(e)}")


@app.get("/api/forecast/data", response_class=JSONResponse)
async def get_forecast_data():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    try:
        return build_static_forecast_payload(DATA_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get forecast data: {str(e)}")


@app.get("/health")
async def health_check():
    return {"status": "OK" if hasattr(app.state, 'initialized') and app.state.initialized else "Initializing"}


# API endpoints to expose HTML maps (These seem redundant with the dashboard routes above)
# Consider removing these if the dashboard routes are sufficient
@app.get("/api/heatmap", response_class=HTMLResponse)
async def get_heatmap_api():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return FileResponse(f'{STATIC_PATH}/heatmap.html')

@app.get("/api/hotspot-map", response_class=HTMLResponse)
async def get_hotspot_map_api():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return FileResponse(f'{STATIC_PATH}/hotspot_map.html')

@app.get("/api/status-map", response_class=HTMLResponse)
async def get_status_map_api():
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return FileResponse(f'{STATIC_PATH}/status_map.html')

@app.get("/api/forecast/crime-trend", response_class=HTMLResponse)
async def get_crime_trend_api(): # Renamed function
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return get_forecast_file('crime_trend_forecast.html')

@app.get("/api/forecast/top-locations", response_class=HTMLResponse)
async def get_top_locations_api(): # Renamed function
    if not hasattr(app.state, 'initialized') or not app.state.initialized:
        raise HTTPException(503, detail="Service initializing")
    return get_forecast_file('top_locations_crime.html')

# New API endpoint to generate weather dashboard (Redundant with /generate-weather-dashboard)
# Consider keeping only one endpoint for triggering generation
@app.get("/api/generate-weather-dashboard", response_class=JSONResponse)
async def generate_weather_dashboard_api_redundant():
     try:
         generate_weather_dashboard(output_dir=STATIC_PATH)
         return {"status": "success", "message": "Weather dashboard generated successfully"}
     except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to generate weather dashboard: {str(e)}")

# API endpoint to serve the weather dashboard (Redundant with /weather)
#Consider keeping only one endpoint for serving the page
@app.get("/api/generate-weather", response_class=HTMLResponse) # Path is confusing, maybe /api/weather ?
async def get_weather_api():
     if not hasattr(app.state, 'initialized') or not app.state.initialized:
         raise HTTPException(503, detail="Service initializing")
     return FileResponse(f'{STATIC_PATH}/weather_updated.html')

if __name__ == "__main__":
    import uvicorn
    # Ensure app state is initialized before running
    if not hasattr(app.state, 'initialized'):
        app.state.initialized = False # Default if startup hasn't run
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) # Added reload=True for development
