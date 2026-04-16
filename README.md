# Crime Visualization Dashboard

FastAPI dashboard for crime maps, hotspot analysis, PSGC location APIs, and weather context.

## Local Setup

1. Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create `.env`:

```env
MONGO_URI="YOUR_MONGO_DB_URL"
MONGO_DB_NAME="YOUR_DATABASE_NAME"
ALLOWED_ORIGINS="http://localhost:8000"
WEATHER_API_KEY="YOUR_WEATHER_API_KEY"
ENABLE_FORECASTING=false
ENABLE_PERIODIC_UPDATES=false
```

4. Run the app:

```powershell
uvicorn main:app --reload
```

## Deploy To Vercel

This project exposes a top-level FastAPI `app` in `main.py`, so Vercel can detect it as a Python/FastAPI project.

1. Push the repo to GitHub.
2. In Vercel, create a new project and import the repo.
3. Keep the framework preset as FastAPI or Python if Vercel detects it.
4. Add these Environment Variables in Vercel Project Settings:

```env
MONGO_URI="YOUR_MONGO_DB_URL"
MONGO_DB_NAME="YOUR_DATABASE_NAME"
ALLOWED_ORIGINS="https://your-vercel-domain.vercel.app"
WEATHER_API_KEY="YOUR_WEATHER_API_KEY"
ENABLE_FORECASTING=false
ENABLE_PERIODIC_UPDATES=false
```

5. Deploy.

You can also deploy from the CLI:

```powershell
npm i -g vercel
vercel login
vercel
vercel --prod
```

## Forecasting Is Paused

Forecast model training is intentionally paused for deployment:

- `ENABLE_FORECASTING=false` skips Prophet training during startup.
- `prophet` is commented out in `requirements.txt` to keep the Vercel install smaller.
- The forecast endpoints still return static graph HTML generated from recent historical counts.
- `/api/forecast/data` returns the same static trend and top-location data as JSON.

Frontend origin:

```env
ALLOWED_ORIGINS="https://aretex-risk-radar.vercel.app"
```

Frontend fetch/iframe URLs:

```text
/forecast/crime-trend
/forecast/top-locations
/api/forecast/crime-trend
/api/forecast/top-locations
/api/forecast/data
```

To turn forecasting back on later:

1. Uncomment `prophet==1.1.6` in `requirements.txt`.
2. Set `ENABLE_FORECASTING=true`.
3. Redeploy.

For production, consider generating forecast HTML in a scheduled/offline job instead of training during serverless cold starts.

## Vercel Notes

Vercel Functions have a read-only project filesystem at runtime, with writable temporary storage under `/tmp`. In Vercel, the app writes downloaded CSVs and generated HTML to `/tmp/cv3`, so those files are temporary and can disappear between cold starts.

Because `data/*.csv` is ignored, the deployed app needs MongoDB environment variables so it can download fresh crime data on startup.
