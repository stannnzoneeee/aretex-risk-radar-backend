# forecasting.py

import pandas as pd
import plotly.graph_objs as go
import plotly.express as px
from prophet import Prophet
from datetime import timedelta
import os
import locale

# Set default locale for encoding
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, 'C')

def load_crime_data(data_path: str) -> pd.DataFrame:
    """
    Load crime data with UTF-8 encoding support
    """
    crime_records = pd.read_csv(
        os.path.join(data_path, 'crime_records.csv'),
        dtype=str,
        encoding='utf-8'
    )
    crime_types = pd.read_csv(
        os.path.join(data_path, 'crime_types.csv'),
        dtype=str,
        encoding='utf-8'
    )
    locations = pd.read_csv(
        os.path.join(data_path, 'locations.csv'),
        dtype=str,
        encoding='utf-8'
    )

    for df in [crime_records, crime_types, locations]:
        df.columns = df.columns.str.strip().str.lower()

    merged = (
        crime_records
        .merge(locations, left_on='location', right_on='_id', suffixes=(None, '_loc'))
        .merge(crime_types, left_on='crime_type', right_on='_id', suffixes=(None, '_ctype'))
        .rename(columns={
            'crime_type_y': 'crime_type_name',
            'crime_type_category': 'crime_category'
        })
    )

    merged['date'] = pd.to_datetime(merged['date'], errors='coerce')
    merged = merged.dropna(subset=['date'])
    merged['crime_count'] = 1

    return merged

def create_bar_chart(data: pd.DataFrame, x_col: str, title: str, color: str) -> go.Figure:
    """Generates a vertical bar chart with enhanced formatting"""
    total = data['yhat'].sum()
    data['percentage'] = (data['yhat'] / total * 100).round(1)
    
    # Format numerical values
    data['yhat'] = data['yhat'].astype(int)
    data['percentage'] = data['percentage'].apply(lambda x: f"{x:.1f}%")

    # Define vibrant color palettes based on the base color
    vibrant_colors = {
        '#3498db': ['#67e8f9', '#06b6d4', '#0891b2', '#0e7490', '#155e75'],  # Blue palette
        '#2ecc71': ['#86efac', '#4ade80', '#22c55e', '#16a34a', '#15803d'],  # Green palette
        '#e67e22': ['#fdba74', '#fb923c', '#f97316', '#ea580c', '#c2410c']   # Orange palette
    }
    
    # Use default vibrant blue if color not in predefined palettes
    color_palette = vibrant_colors.get(color, ['#38bdf8', '#0ea5e9', '#0284c7', '#0369a1', '#075985'])
    
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=data[x_col],
        y=data['yhat'],
        marker=dict(
            color=data['yhat'],
            colorscale=[[0, color_palette[0]], [0.25, color_palette[1]], 
                        [0.5, color_palette[2]], [0.75, color_palette[3]], 
                        [1, color_palette[4]]],  # Vibrant color gradient
            line=dict(width=1, color='rgba(0,0,0,0.2)'),
            opacity=0.9
        ),
        hovertemplate='<b>%{x}</b><br>Forecasted Crimes: %{y:,}<br>Percent of Total: %{customdata}',
        customdata=data['percentage'],
        text=[f"{y:,}<br>({p})" for y, p in zip(data['yhat'], data['percentage'])],
        textposition='inside',
        textfont=dict(
            family='Montserrat',
            size=12,
            color='#1a1a1a',  # Dark text color
            weight='bold',     # Make text bold for better visibility
        ),
        width=0.5,  # Make bars thinner (default is 0.8)
    ))

    fig.update_layout(
        title=f'<b>{title}</b>',
        title_font=dict(size=22, family='Montserrat', color='#2c3e50'),
        font=dict(family='Montserrat', size=14),
        plot_bgcolor='white',
        paper_bgcolor='#f8f9fa',
        margin=dict(t=100, l=100, r=100, b=100),
        width=1400,
        height=700,
        xaxis=dict(
            title=dict(text='Location', font=dict(size=16, family='Montserrat')),
            showgrid=False,
            tickfont=dict(size=12, color='#34495e'),
            type='category'
        ),
        yaxis=dict(
            title=dict(text='Forecasted Crimes', font=dict(size=16, family='Montserrat')),
            gridcolor='rgba(200,200,200,0.2)',
            showline=True,
            linecolor='#bdc3c7',
            tickformat=',',
            zeroline=False
        ),
        bargap=0.3,  # Increase gap between bars
        hoverlabel=dict(
            bgcolor='white',
            font_size=14,
            font_family='Montserrat',
            bordercolor='#bdc3c7'
        ),
        uniformtext=dict(
            minsize=10,
            mode='hide'
        ),
        shapes=[
            dict(
                type='rect',
                xref='paper', yref='paper',
                x0=0, y0=0, x1=1, y1=1,
                line=dict(color='#ecf0f1', width=2),
                fillcolor='rgba(0,0,0,0)'
            )
        ]
    )

    # Add trendline for visual analysis
    fig.add_shape(
        type="line",
        x0=-0.5, x1=len(data)-0.5,
        y0=data['yhat'].mean(), y1=data['yhat'].mean(),
        line=dict(color='#e74c3c', width=2, dash='dot'),
        name="Average"
    )

    # Disable modebar
    fig.update_layout(
        modebar=dict(remove=['zoom', 'pan', 'select', 'zoomIn', 'zoomOut', 'autoScale', 'resetScale']),
        dragmode=False
    )

    return fig

def predict_and_plot_crime_trends(df: pd.DataFrame, forecast_days: int = 30, output_path: str = '.') -> None:
    os.makedirs(output_path, exist_ok=True)

    # Daily crime aggregation
    daily = df.groupby('date')['crime_count'].sum().reset_index(name='y')
    daily = daily.rename(columns={'date': 'ds'})
    daily['y'] = daily['y'].astype(int)

    # Prophet modeling
    model = Prophet()
    model.fit(daily)
    future = model.make_future_dataframe(periods=forecast_days, freq='D')
    forecast = model.predict(future)

    # Prepare data for plotting
    hist = daily.copy()
    pred = forecast[['ds', 'yhat']][forecast['ds'] > hist['ds'].max()].copy()
    pred['yhat'] = pred['yhat'].round().astype(int)

    # Create interactive line chart with dots that only appear on direct hover
    fig_line = go.Figure()
    
    # Historical data - only lines, no markers
    fig_line.add_trace(go.Scatter(
        x=hist['ds'], 
        y=hist['y'],
        mode='lines',  # Only lines, no markers
        name='Historical',
        line=dict(color='#3498db', width=3.5, shape='spline', smoothing=1.1),
        fill='tozeroy',
        fillcolor='rgba(52, 152, 219, 0.15)',
        hoverinfo='none',  # Disable hover on the line itself
    ))
    
    # Historical data - invisible points that show on hover
    fig_line.add_trace(go.Scatter(
        x=hist['ds'], 
        y=hist['y'],
        mode='markers',
        marker=dict(
            color='#3498db',
            size=12,
            opacity=0,  # Completely invisible until hovered
            line=dict(width=2, color='white'),
        ),
        name='Historical',
        showlegend=False,  # Don't show in legend
        hovertemplate='<b>%{x|%b %d}</b><br>Crimes: %{y:,}',
        hoverlabel=dict(bgcolor='rgba(52, 152, 219, 0.9)'),
    ))
    
    # Forecast data - only lines, no markers
    fig_line.add_trace(go.Scatter(
        x=pred['ds'], 
        y=pred['yhat'],
        mode='lines',  # Only lines, no markers
        name='Forecast',
        line=dict(color='#e74c3c', width=3.5, shape='spline', dash='dash', smoothing=1.1),
        hoverinfo='none',  # Disable hover on the line itself
    ))
    
    # Forecast data - invisible points that show on hover
    fig_line.add_trace(go.Scatter(
        x=pred['ds'], 
        y=pred['yhat'],
        mode='markers',
        marker=dict(
            color='#e74c3c',
            size=12,
            symbol='diamond',
            opacity=0,  # Completely invisible until hovered
            line=dict(width=2, color='white'),
        ),
        name='Forecast',
        showlegend=False,  # Don't show in legend
        hovertemplate='<b>%{x|%b %d}</b><br>Forecast: %{y:,}',
        hoverlabel=dict(bgcolor='rgba(231, 76, 60, 0.9)'),
    ))

    fig_line.update_layout(
        title=dict(
            text='<b>Crime Trend Forecast</b>',
            font=dict(size=28, family='Montserrat', color='#2c3e50'),
            x=0.03, y=0.93
        ),
        xaxis=dict(
            title=dict(text='Date', font=dict(size=16, family='Montserrat')),
            gridcolor='rgba(200,200,200,0.2)',
            showline=True,
            linecolor='#bdc3c7',
            rangeslider=dict(
                visible=True,
                thickness=0.08,
                bgcolor='rgba(150,150,150,0.1)'
            ),
            rangeselector=dict(
                buttons=list([
                    dict(count=7, label='1W', step='day'),
                    dict(count=1, label='1M', step='month'),
                    dict(step='all')
                ]),
                bgcolor='rgba(240,240,240,0.9)',
                activecolor='#3498db',
                font=dict(color='#666', size=12, family='Montserrat')
            )
        ),
        yaxis=dict(
            title=dict(text='Crime Count', font=dict(size=16, family='Montserrat')),
            gridcolor='rgba(200,200,200,0.2)',
            showline=True,
            linecolor='#bdc3c7',
            tickformat=',',
            zerolinecolor='rgba(200,200,200,0.5)'
        ),
        hoverlabel=dict(
            bgcolor='rgba(255,255,255,0.95)',
            font_size=14,
            bordercolor='#ecf0f1',
            font_family='Montserrat'
        ),
        plot_bgcolor='rgba(255, 255, 255, 1)',
        paper_bgcolor='#ffffff',
        height=750,
        margin=dict(l=80, r=30, t=140, b=80),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            font=dict(size=14, family='Montserrat'),
            bgcolor='rgba(255,255,255,0.9)'
        ),
        shapes=[dict(
            type="rect",
            xref="paper", yref="paper",
            x0=0, y0=0, x1=1, y1=1,
            fillcolor="rgba(0, 0, 0, 0.03)",
            layer="below",
            line_width=0
        )],
        dragmode='pan',
        hovermode='closest'
    )

    # Save trend forecast without modebar
    trend_file = os.path.join(output_path, 'crime_trend_forecast.html')
    fig_line.write_html(
        trend_file,
        include_plotlyjs='cdn',
        config={
            'scrollZoom': True,
            'displayModeBar': False,
            'responsive': True,
            'showTips': True
        }
    )

    # Location-based forecasts
    locations = ['province', 'municipality_city', 'barangay']
    bar_colors = ['#3498db', '#2ecc71', '#e67e22']
    charts = []

    for loc_type, color in zip(locations, bar_colors):
        if loc_type in df.columns:
            loc_df = df.groupby([loc_type, 'date'])['crime_count'].sum().reset_index()
            loc_df = loc_df.rename(columns={'date': 'ds', 'crime_count': 'y'})

            top_locations = loc_df.groupby(loc_type)['y'].sum().nlargest(5).index.tolist()
            loc_df_top5 = loc_df[loc_df[loc_type].isin(top_locations)]

            forecasts = []
            for location in top_locations:
                location_df = loc_df_top5[loc_df_top5[loc_type] == location].copy()
                if not location_df.empty and location_df['y'].nunique() > 1:
                    model = Prophet()
                    model.fit(location_df.rename(columns={loc_type: 'location'}))
                    future = model.make_future_dataframe(periods=forecast_days, freq='D')
                    forecast = model.predict(future)
                    forecast['location'] = location
                    forecasts.append(forecast)

            if forecasts:
                combined_forecasts = pd.concat(forecasts)
                pred = combined_forecasts[['ds', 'yhat', 'location']][combined_forecasts['ds'] > loc_df['ds'].max()].copy()
                pred['yhat'] = pred['yhat'].round().astype(int).clip(lower=0)
                predicted_crimes = pred.groupby('location')['yhat'].sum().reset_index().sort_values('yhat', ascending=False)
                
                charts.append(create_bar_chart(
                    predicted_crimes,
                    'location',  # x_col parameter
                    f'Top {loc_type.title()} Crime Forecasts',
                    color
                ))

    # Save location forecasts without modebar
    if charts:
        loc_file = os.path.join(output_path, 'top_locations_crime.html')
        with open(loc_file, 'w', encoding='utf-8') as f:
            f.write(f'''<html><head>
                <meta charset="UTF-8">
                <title>Crime Forecast - Top Locations</title>
                <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600&display=swap" rel="stylesheet">
                <style>
                    body {{ 
                        background: #f8f9fa; 
                        font-family: 'Montserrat', sans-serif;
                        margin: 0;
                        padding: 20px;
                    }}
                    .header {{
                        text-align: center;
                        padding: 30px 0;
                        background: #2c3e50;
                        color: white;
                        margin-bottom: 40px;
                        border-radius: 12px;
                    }}
                    .chart-container {{
                        background: white;
                        border-radius: 16px;
                        box-shadow: 0 8px 30px rgba(0,0,0,0.08);
                        margin: 40px auto;
                        padding: 30px;
                        max-width: 1400px;
                    }}
                </style>
            </head><body>
                <div class="header">
                    <h1>Crime Forecast - Top Locations</h1>
                    <p>Next {forecast_days} Days Prediction</p>
                </div>
            ''')

            for chart in charts:
                html = chart.to_html(
                    full_html=False,
                    include_plotlyjs='cdn',
                    config={'displayModeBar': False}
                )
                f.write(f'<div class="chart-container">{html}</div>')

            f.write('</body></html>')

if __name__ == '__main__':
    data_dir = 'crime_data'
    df = load_crime_data(data_dir)
    predict_and_plot_crime_trends(df, output_path='reports')