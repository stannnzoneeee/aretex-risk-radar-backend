import pandas as pd
import folium
from folium.plugins import HeatMap, MousePosition, Fullscreen
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import os

def load_and_preprocess_data(data_path):
    """Load and preprocess crime data from specified path"""
    try:
        # Load datasets
        crime_records = pd.read_csv(
            os.path.join(data_path, 'crime_records.csv'),
            sep=',',
            dtype={'crime_type': 'string', 'location': 'string', 'date': 'string', 'time': 'string'}
        )
        
        crime_records['datetime'] = pd.to_datetime(
            crime_records['date'] + ' ' + crime_records['time'],
            errors='coerce'
        )
        
        locations = pd.read_csv(
            os.path.join(data_path, 'locations.csv'),
            sep=',',
            dtype={'_id': 'string'}
        )
        crime_types = pd.read_csv(
            os.path.join(data_path, 'crime_types.csv'),
            sep=',',
            dtype={'_id': 'string'}
        )

        # Clean and merge data
        crime_records.columns = crime_records.columns.str.strip().str.lower()
        locations.columns = locations.columns.str.strip().str.lower()
        crime_types.columns = crime_types.columns.str.strip().str.lower()

        merged_df = (
            crime_records
            .merge(locations, left_on='location', right_on='_id', how='inner')
            .merge(crime_types, left_on='crime_type', right_on='_id', how='inner')
        )

        merged_df = merged_df.rename(columns={
            'crime_type_y': 'crime_type_name',
            'case_status': 'status'
        })

        # Validate coordinates
        merged_df['latitude'] = pd.to_numeric(merged_df['latitude'], errors='coerce')
        merged_df['longitude'] = pd.to_numeric(merged_df['longitude'], errors='coerce')
        coord_mask = (
            merged_df['latitude'].between(-90, 90) & 
            merged_df['longitude'].between(-180, 180)
        )
        merged_df = merged_df[coord_mask].dropna(subset=['latitude', 'longitude'])

        # Validate datetime
        merged_df = merged_df.dropna(subset=['datetime'])

        # Create temporal features
        merged_df['hour'] = merged_df['datetime'].dt.hour
        merged_df['day_of_week'] = merged_df['datetime'].dt.dayofweek
        merged_df['month'] = merged_df['datetime'].dt.month

        # Spatial clustering
        coords = merged_df[['latitude', 'longitude']].values
        if len(coords) > 1:
            n_clusters = min(10, len(coords))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            merged_df['cluster'] = kmeans.fit_predict(coords)
        else:
            merged_df['cluster'] = 0
            kmeans = KMeans(n_clusters=1, random_state=42)

        return merged_df, kmeans

    except Exception as e:
        raise RuntimeError(f"Data processing failed: {str(e)}")

def generate_heatmap(df, static_path):
    """Generate crime heatmap visualization"""
    try:
        base_lat = df['latitude'].mean()
        base_lon = df['longitude'].mean()
        
        heatmap = folium.Map(location=[base_lat, base_lon], zoom_start=12)
        HeatMap(
            df[['latitude', 'longitude', 'risk_score']].values.tolist(),
            radius=15,
            blur=20,
            gradient={
                '0.5': '#0000ff',     
                '0.6': '#00ff00',
                '0.7': '#ffff00',     
                '0.8': '#ff3333', 
                '0.9': '#8b0000'      
            }
        ).add_to(heatmap)
        
        MousePosition().add_to(heatmap)
        Fullscreen().add_to(heatmap)
        heatmap.save(os.path.join(static_path, 'heatmap.html'))
        return True

    except Exception as e:
        raise RuntimeError(f"Heatmap generation failed: {str(e)}")

def generate_hotspot_map(df, kmeans_model, static_path):
    """Generate hotspot map with cluster markers"""
    try:
        base_lat = df['latitude'].mean()
        base_lon = df['longitude'].mean()

        cluster_risk = df.groupby('cluster')['risk_score'].mean().reset_index()
        top_clusters = cluster_risk.nlargest(5, 'risk_score')['cluster'].values
        
        hotspots = []
        for cluster in top_clusters:
            center = kmeans_model.cluster_centers_[cluster]
            risk = cluster_risk.loc[cluster_risk['cluster'] == cluster, 'risk_score'].values[0]
            count = df[df['cluster'] == cluster].shape[0]
            
            hotspots.append({
                "latitude": center[0],
                "longitude": center[1],
                "risk_score": risk,
                "crime_count": count
            })

        hotspot_map = folium.Map(location=[base_lat, base_lon], zoom_start=12)
        
        for hotspot in hotspots:
            folium.CircleMarker(
                location=[hotspot['latitude'], hotspot['longitude']],
                radius=10 + (hotspot['risk_score'] * 10),
                color='#ff4444',
                fill=True,
                fill_color='#ff0000',
                fill_opacity=0.7,
                popup=folium.Popup(
                    f"""🚨 **High-Risk Hotspot** 🚨
                    🔥 **Risk Score**: {hotspot['risk_score']:.2f}<br>
                    📍 Coordinates: {hotspot['latitude']:.4f}, {hotspot['longitude']:.4f}<br>
                    ⚠️ **Crime Count**: {hotspot['crime_count']}<br>
                    <i>This area requires increased monitoring</i>""",
                    max_width=250,
                    max_height=150
                )
            ).add_to(hotspot_map)
        
        MousePosition().add_to(hotspot_map)
        Fullscreen().add_to(hotspot_map)
        hotspot_map.save(os.path.join(static_path, 'hotspot_map.html'))
        return True
        
    except Exception as e:
        raise RuntimeError(f"Hotspot map generation failed: {str(e)}")

def generate_analysis_maps(df, kmeans_model, data_path, static_path):
    """Generate all map visualizations"""
    try:
        # Status Map
        base_lat = df['latitude'].mean()
        base_lon = df['longitude'].mean()
        status_map = folium.Map(location=[base_lat, base_lon], zoom_start=12)
        
        status_colors = {
            'Closed': 'green',
            'Open': 'red',
            'Pending': 'blue',
            'Resolved': 'green',
            'Ongoing': 'red',
            'Under Investigation': 'blue'
        }
        
        for _, row in df.iterrows():
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=6,
                color=status_colors.get(row['status'].title(), 'blue'),
                fill=True,
                fill_opacity=0.7,
                popup=folium.Popup(
                    f"<b>{row.get('crime_type_name', 'N/A')}</b><br>"
                    f"Status: {row.get('status', 'N/A')}<br>"
                    f"Date: {row.get('date', 'N/A')}",
                    max_width=300
                ),
                tooltip=f"Status: {row.get('status', 'N/A')}"
            ).add_to(status_map)
        status_map.save(os.path.join(static_path, 'status_map.html'))

        # Risk Prediction Model
        features = ['hour', 'day_of_week', 'month', 'latitude', 'longitude', 'cluster']
        target = 'crime_occurred_indoors_or_outdoors'
        
        model = Pipeline([
            ('preprocessor', ColumnTransformer([('num', StandardScaler(), features)])),
            ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
        ])
        model.fit(df[features], df[target])
        df['risk_score'] = model.predict_proba(df[features])[:, 1]
        
        # Generate visualizations
        generate_heatmap(df, static_path)
        generate_hotspot_map(df, kmeans_model, static_path)
        return True

    except Exception as e:
        raise RuntimeError(f"Map generation failed: {str(e)}")

def get_hotspot_data(df, kmeans_model):
    """Get hotspot data for API endpoint"""
    try:
        features = ['hour', 'day_of_week', 'month', 'latitude', 'longitude', 'cluster']
        target = 'crime_occurred_indoors_or_outdoors'
        
        model = Pipeline([
            ('preprocessor', ColumnTransformer([('num', StandardScaler(), features)])),
            ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
        ])
        model.fit(df[features], df[target])
        df['risk_score'] = model.predict_proba(df[features])[:, 1]
        
        cluster_risk = df.groupby('cluster')['risk_score'].mean().reset_index()
        top_clusters = cluster_risk.nlargest(5, 'risk_score')['cluster'].values
        
        return {
            "hotspots": [
                {
                    "latitude": kmeans_model.cluster_centers_[cluster][0],
                    "longitude": kmeans_model.cluster_centers_[cluster][1],
                    "risk_score": cluster_risk.loc[cluster_risk['cluster'] == cluster, 'risk_score'].values[0],
                    "crime_count": df[df['cluster'] == cluster].shape[0]
                }
                for cluster in top_clusters
            ]
        }

    except Exception as e:
        raise RuntimeError(f"Hotspot data generation failed: {str(e)}")