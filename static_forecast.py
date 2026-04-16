import os
from datetime import datetime

import pandas as pd
import plotly.graph_objs as go


TREND_FILENAME = "crime_trend_forecast.html"
TOP_LOCATIONS_FILENAME = "top_locations_crime.html"

COLORS = {
    "page": "#f6fbff",
    "panel": "#ffffff",
    "plot": "#fbfdff",
    "grid": "rgba(8, 145, 178, 0.14)",
    "text": "#102033",
    "muted": "#5f6f86",
    "line": "#0891b2",
    "line_soft": "rgba(8, 145, 178, 0.14)",
    "baseline": "#e11d48",
    "yellow": "#b77900",
    "edge": "rgba(8, 145, 178, 0.24)",
    "header": "#f9fdff",
    "shadow": "rgba(15, 23, 42, 0.12)",
}

BAR_COLORS = [
    "#0891b2",
    "#14b8a6",
    "#e11d48",
    "#7c3aed",
    "#f59e0b",
    "#2563eb",
    "#16a34a",
    "#db2777",
    "#65a30d",
    "#0ea5e9",
]


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
            color: {COLORS["text"]};
            background:
                linear-gradient(90deg, rgba(8, 145, 178, 0.07) 1px, transparent 1px),
                linear-gradient(0deg, rgba(8, 145, 178, 0.07) 1px, transparent 1px),
                {COLORS["page"]};
            background-size: 32px 32px;
        }}
        main {{
            width: min(720px, calc(100% - 32px));
            padding: 24px;
            border: 1px solid {COLORS["edge"]};
            border-radius: 8px;
            background: {COLORS["panel"]};
            box-shadow: 0 18px 60px {COLORS["shadow"]};
        }}
        h1 {{ margin: 0 0 12px; font-size: 24px; }}
        p {{ line-height: 1.5; }}
        small {{ color: {COLORS["muted"]}; }}
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
            "font": {"size": 25, "color": COLORS["text"]},
        },
        "template": "none",
        "font": {"family": "Arial, sans-serif", "size": 14, "color": COLORS["text"]},
        "paper_bgcolor": COLORS["panel"],
        "plot_bgcolor": COLORS["plot"],
        "margin": {"t": 94, "r": 42, "b": 74, "l": 78},
        "height": 590,
        "hovermode": "x unified",
        "legend": {
            "orientation": "h",
            "x": 0.03,
            "y": 1.03,
            "bgcolor": "rgba(255, 255, 255, 0.88)",
            "bordercolor": COLORS["edge"],
            "borderwidth": 1,
            "font": {"color": COLORS["text"]},
        },
        "hoverlabel": {
            "bgcolor": "#ffffff",
            "bordercolor": COLORS["line"],
            "font": {"color": COLORS["text"], "family": "Arial, sans-serif"},
        },
    }


def _write_html(fig: go.Figure, path: str, title: str, subtitle: str) -> None:
    chart_html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            font-family: Arial, sans-serif;
            color: {COLORS["text"]};
            background:
                linear-gradient(90deg, rgba(8, 145, 178, 0.07) 1px, transparent 1px),
                linear-gradient(0deg, rgba(8, 145, 178, 0.07) 1px, transparent 1px),
                {COLORS["page"]};
            background-size: 34px 34px;
        }}
        main {{
            width: min(1180px, calc(100% - 28px));
            margin: 18px auto;
            border: 1px solid {COLORS["edge"]};
            border-radius: 8px;
            background: {COLORS["panel"]};
            box-shadow: 0 22px 70px {COLORS["shadow"]};
            overflow: hidden;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            gap: 18px;
            padding: 18px 20px;
            background: {COLORS["header"]};
            border-bottom: 1px solid rgba(8, 145, 178, 0.16);
        }}
        .eyebrow {{
            margin: 0 0 6px;
            color: {COLORS["line"]};
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0;
            text-transform: uppercase;
        }}
        h1 {{
            margin: 0;
            font-size: 26px;
            line-height: 1.2;
        }}
        .subtitle {{
            margin: 8px 0 0;
            color: {COLORS["muted"]};
            line-height: 1.45;
        }}
        .status {{
            min-width: 176px;
            align-self: start;
            padding: 12px;
            border: 1px solid rgba(183, 121, 0, 0.28);
            border-radius: 8px;
            color: {COLORS["yellow"]};
            background: rgba(245, 158, 11, 0.11);
            text-align: right;
        }}
        .status strong {{
            display: block;
            margin-bottom: 4px;
            color: {COLORS["text"]};
        }}
        .chart {{
            padding: 8px;
            min-height: 610px;
        }}
        .js-plotly-plot .plotly .main-svg {{
            border-radius: 8px;
        }}
        footer {{
            padding: 12px 20px 18px;
            color: {COLORS["muted"]};
            border-top: 1px solid rgba(8, 145, 178, 0.12);
            font-size: 13px;
        }}
        @media (max-width: 720px) {{
            header {{ display: block; }}
            .status {{ margin-top: 14px; text-align: left; }}
            h1 {{ font-size: 22px; }}
            .chart {{ min-height: 560px; }}
        }}
    </style>
</head>
<body>
    <main>
        <header>
            <div>
                <p class="eyebrow">Aretex Risk Radar</p>
                <h1>{title}</h1>
                <p class="subtitle">{subtitle}</p>
            </div>
            <div class="status">
                <strong>Training Paused</strong>
                Static signal active
            </div>
        </header>
        <section class="chart">{chart_html}</section>
        <footer>Generated {generated_at}. Static baseline uses historical crime records while model training is paused.</footer>
    </main>
</body>
</html>"""
    with open(path, "w", encoding="utf-8") as file:
        file.write(html)


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
        line={"color": COLORS["line"], "width": 4, "shape": "spline", "smoothing": 0.55},
        marker={
            "size": 8,
            "color": COLORS["plot"],
            "line": {"color": COLORS["line"], "width": 2},
        },
        fill="tozeroy",
        fillcolor=COLORS["line_soft"],
        hovertemplate="<b>%{x}</b><br>Incidents: %{y}<extra></extra>",
    ))
    trend_fig.add_trace(go.Scatter(
        x=baseline["date"],
        y=baseline["crime_count"],
        mode="lines",
        name="Static 30-day baseline",
        line={"color": COLORS["baseline"], "width": 4, "dash": "dash"},
        hovertemplate="<b>%{x}</b><br>Baseline: %{y:.2f}<extra></extra>",
    ))
    trend_fig.update_layout(**_base_layout("Crime Trend Static Forecast", subtitle))
    trend_fig.update_xaxes(
        title={"text": "Date", "font": {"color": COLORS["text"]}},
        gridcolor=COLORS["grid"],
        zeroline=False,
        linecolor=COLORS["edge"],
        tickfont={"color": COLORS["muted"]},
    )
    trend_fig.update_yaxes(
        title={"text": "Incidents", "font": {"color": COLORS["text"]}},
        gridcolor=COLORS["grid"],
        zeroline=False,
        rangemode="tozero",
        linecolor=COLORS["edge"],
        tickfont={"color": COLORS["muted"]},
    )
    _write_html(trend_fig, trend_path, "Crime Trend Static Forecast", subtitle)

    location_fig = go.Figure()
    if not locations.empty:
        locations = locations.sort_values("crime_count", ascending=True)
        bar_colors = [BAR_COLORS[index % len(BAR_COLORS)] for index in range(len(locations))]
        location_fig.add_trace(go.Bar(
            x=locations["crime_count"],
            y=locations["location"],
            orientation="h",
            marker={
                "color": bar_colors,
                "line": {"color": "rgba(237, 253, 249, 0.36)", "width": 1},
            },
            text=locations["crime_count"],
            textposition="auto",
            textfont={"color": COLORS["text"], "size": 13},
            hovertemplate="<b>%{y}</b><br>Incidents: %{x}<extra></extra>",
        ))
    location_fig.update_layout(**_base_layout("Top Locations Static Graph", subtitle))
    location_fig.update_layout(showlegend=False)
    location_fig.update_xaxes(
        title={"text": "Incidents", "font": {"color": COLORS["text"]}},
        gridcolor=COLORS["grid"],
        zeroline=False,
        rangemode="tozero",
        linecolor=COLORS["edge"],
        tickfont={"color": COLORS["muted"]},
    )
    location_fig.update_yaxes(
        title="",
        gridcolor="rgba(0,0,0,0)",
        tickfont={"color": COLORS["text"], "size": 12},
    )
    _write_html(location_fig, top_locations_path, "Top Locations Static Graph", subtitle)

    return {"trend_path": trend_path, "top_locations_path": top_locations_path, "payload": payload}
