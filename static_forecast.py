import os
from datetime import datetime

import pandas as pd
import plotly.graph_objs as go


TREND_FILENAME = "crime_trend_forecast.html"
TOP_LOCATIONS_FILENAME = "top_locations_crime.html"


def _empty_page(title: str, message: str) -> str:
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            font-family: Arial, sans-serif;
            color: #172033;
            background: #f4f7fb;
        }}
        main {{
            width: min(720px, calc(100% - 32px));
            padding: 24px;
            border: 1px solid #d7dfeb;
            border-radius: 8px;
            background: #ffffff;
        }}
        h1 {{ margin: 0 0 12px; font-size: 24px; }}
        p {{ line-height: 1.5; }}
        small {{ color: #5d6b82; }}
    </style>
</head>
<body>
    <main>
        <h1>{title}</h1>
        <p>{message}</p>
        <small>Generated {generated_at}</small>
    </main>
</body>
</html>"""


def _read_csv(data_path: str, filename: str) -> pd.DataFrame:
    path = os.path.join(data_path, filename)
    df = pd.read_csv(path, dtype=str, encoding="utf-8")
    df.columns = df.columns.str.strip().str.lower()
    return df


def load_static_crime_data(data_path: str) -> pd.DataFrame:
    records = _read_csv(data_path, "crime_records.csv")
    locations = _read_csv(data_path, "locations.csv")
    crime_types = _read_csv(data_path, "crime_types.csv")

    merged = (
        records
        .merge(locations, left_on="location", right_on="_id", how="left", suffixes=("", "_location"))
        .merge(crime_types, left_on="crime_type", right_on="_id", how="left", suffixes=("", "_type"))
    )

    merged["date"] = pd.to_datetime(merged.get("date"), errors="coerce")
    merged = merged.dropna(subset=["date"])
    merged["crime_count"] = 1

    location_parts = []
    for column in ["barangay", "municipality_city", "province"]:
        if column in merged.columns:
            location_parts.append(merged[column].fillna("").str.strip())

    if location_parts:
        label = location_parts[0]
        for part in location_parts[1:]:
            label = label.str.cat(part, sep=", ")
        merged["location_label"] = label.str.replace(r"(, )+", ", ", regex=True).str.strip(", ")
    else:
        merged["location_label"] = merged.get("location", "Unknown").fillna("Unknown")

    merged["location_label"] = merged["location_label"].replace("", "Unknown")
    return merged


def build_static_forecast_payload(data_path: str) -> dict:
    df = load_static_crime_data(data_path)
    if df.empty:
        return {"mode": "static", "trend": [], "baseline": [], "top_locations": []}

    daily = (
        df.groupby(df["date"].dt.date)
        .size()
        .reset_index(name="crime_count")
        .rename(columns={"date": "day"})
        .sort_values("day")
    )
    daily["day"] = pd.to_datetime(daily["day"])
    recent_daily = daily.tail(45).copy()

    recent_window = daily.tail(30)
    baseline_value = float(recent_window["crime_count"].mean()) if not recent_window.empty else 0.0
    last_day = daily["day"].max()
    baseline_days = pd.date_range(last_day + pd.Timedelta(days=1), periods=30, freq="D")
    baseline = pd.DataFrame({
        "day": baseline_days,
        "crime_count": [round(baseline_value, 2)] * len(baseline_days),
    })

    top_locations = (
        df.groupby("location_label")
        .size()
        .reset_index(name="crime_count")
        .sort_values("crime_count", ascending=False)
        .head(10)
    )

    return {
        "mode": "static",
        "note": "Forecast model training is paused. Values use recent historical counts and a flat 30-day baseline.",
        "trend": [
            {"date": row.day.strftime("%Y-%m-%d"), "crime_count": int(row.crime_count)}
            for row in recent_daily.itertuples(index=False)
        ],
        "baseline": [
            {"date": row.day.strftime("%Y-%m-%d"), "crime_count": float(row.crime_count)}
            for row in baseline.itertuples(index=False)
        ],
        "top_locations": [
            {"location": row.location_label, "crime_count": int(row.crime_count)}
            for row in top_locations.itertuples(index=False)
        ],
    }


def _base_layout(title: str, subtitle: str) -> dict:
    return {
        "title": {
            "text": f"<b>{title}</b><br><sup>{subtitle}</sup>",
            "x": 0.03,
            "xanchor": "left",
        },
        "font": {"family": "Arial, sans-serif", "size": 14, "color": "#1f2937"},
        "paper_bgcolor": "#f8fafc",
        "plot_bgcolor": "#ffffff",
        "margin": {"t": 90, "r": 32, "b": 64, "l": 72},
        "height": 560,
    }


def _write_html(fig: go.Figure, path: str) -> None:
    fig.write_html(
        path,
        include_plotlyjs="cdn",
        full_html=True,
        config={"displayModeBar": False, "responsive": True},
    )


def generate_static_forecast_graphs(data_path: str, output_path: str) -> dict:
    os.makedirs(output_path, exist_ok=True)
    trend_path = os.path.join(output_path, TREND_FILENAME)
    top_locations_path = os.path.join(output_path, TOP_LOCATIONS_FILENAME)

    try:
        payload = build_static_forecast_payload(data_path)
    except Exception as exc:
        message = (
            "Forecast model training is paused, and the static graph could not be "
            f"generated from the available data. Details: {exc}"
        )
        with open(trend_path, "w", encoding="utf-8") as file:
            file.write(_empty_page("Static Forecast Unavailable", message))
        with open(top_locations_path, "w", encoding="utf-8") as file:
            file.write(_empty_page("Static Location Graph Unavailable", message))
        return {"trend_path": trend_path, "top_locations_path": top_locations_path, "payload": None}

    trend = pd.DataFrame(payload["trend"])
    baseline = pd.DataFrame(payload["baseline"])
    locations = pd.DataFrame(payload["top_locations"])
    subtitle = "Training paused. Static baseline uses recent historical averages."

    if trend.empty:
        empty_message = "No crime records are available yet for static forecast graphs."
        with open(trend_path, "w", encoding="utf-8") as file:
            file.write(_empty_page("Static Forecast Unavailable", empty_message))
        with open(top_locations_path, "w", encoding="utf-8") as file:
            file.write(_empty_page("Static Location Graph Unavailable", empty_message))
        return {"trend_path": trend_path, "top_locations_path": top_locations_path, "payload": payload}

    trend_fig = go.Figure()
    trend_fig.add_trace(go.Scatter(
        x=trend["date"],
        y=trend["crime_count"],
        mode="lines+markers",
        name="Recent incidents",
        line={"color": "#2563eb", "width": 3},
        marker={"size": 7},
        hovertemplate="<b>%{x}</b><br>Incidents: %{y}<extra></extra>",
    ))
    trend_fig.add_trace(go.Scatter(
        x=baseline["date"],
        y=baseline["crime_count"],
        mode="lines",
        name="Static 30-day baseline",
        line={"color": "#dc2626", "width": 3, "dash": "dash"},
        hovertemplate="<b>%{x}</b><br>Baseline: %{y:.2f}<extra></extra>",
    ))
    trend_fig.update_layout(**_base_layout("Crime Trend Static Forecast", subtitle))
    trend_fig.update_xaxes(title="Date", gridcolor="#e5e7eb")
    trend_fig.update_yaxes(title="Incidents", gridcolor="#e5e7eb", rangemode="tozero")
    _write_html(trend_fig, trend_path)

    location_fig = go.Figure()
    if not locations.empty:
        locations = locations.sort_values("crime_count", ascending=True)
        location_fig.add_trace(go.Bar(
            x=locations["crime_count"],
            y=locations["location"],
            orientation="h",
            marker={"color": "#0f766e"},
            hovertemplate="<b>%{y}</b><br>Incidents: %{x}<extra></extra>",
        ))
    location_fig.update_layout(**_base_layout("Top Locations Static Graph", subtitle))
    location_fig.update_xaxes(title="Incidents", gridcolor="#e5e7eb", rangemode="tozero")
    location_fig.update_yaxes(title="")
    _write_html(location_fig, top_locations_path)

    return {"trend_path": trend_path, "top_locations_path": top_locations_path, "payload": payload}
