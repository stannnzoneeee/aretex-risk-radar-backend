import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# --- PSGC API Fetching Logic ---
PSGC_API_BASE = "https://psgc.cloud/api"

def fetch_regions():
    """Fetches regions from the PSGC API."""
    try:
        response = requests.get(f"{PSGC_API_BASE}/regions", timeout=10)
        response.raise_for_status()
        regions = response.json()
        return sorted(regions, key=lambda x: x['name'])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching regions: {e}")
        return []

def fetch_provinces(region_code: str):
    """Fetches provinces for a given region code from the PSGC API."""
    if not region_code: return []
    try:
        response = requests.get(f"{PSGC_API_BASE}/regions/{region_code}/provinces", timeout=10)
        response.raise_for_status()
        provinces = response.json()
        return sorted(provinces, key=lambda x: x['name'])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching provinces for region {region_code}: {e}")
        return []

def fetch_cities_municipalities(province_code: str):
    """Fetches cities and municipalities for a given province code from the PSGC API."""
    if not province_code: return []
    combined_list = []
    for loc_type in ["cities", "municipalities"]:
        try:
            response = requests.get(f"{PSGC_API_BASE}/provinces/{province_code}/{loc_type}", timeout=10)
            if response.status_code == 200:
                combined_list.extend(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {loc_type} for province {province_code}: {e}")
            continue
    return sorted(combined_list, key=lambda x: x['name'])

def fetch_locations_for_region(region_code: str):
    """Fetches cities and municipalities directly for a given region code (useful for NCR)."""
    if not region_code: return []
    combined_list = []
    # Fetch cities and municipalities directly under the region
    for loc_type in ["cities", "municipalities"]:
        try:
            # Use the region-based endpoint from PSGC API
            response = requests.get(f"{PSGC_API_BASE}/regions/{region_code}/{loc_type}", timeout=10)
            if response.status_code == 200:
                combined_list.extend(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {loc_type} for region {region_code}: {e}")
            continue
    return sorted(combined_list, key=lambda x: x['name'])

# --- FastAPI Router for PSGC Endpoints ---
router = APIRouter(prefix="/api", tags=["PSGC Locations"]) # Add prefix and tags for organization

@router.get("/regions", response_class=JSONResponse)
async def get_regions():
    regions = fetch_regions()
    if not regions:
        raise HTTPException(status_code=500, detail="Failed to fetch regions from PSGC API")
    return regions

@router.get("/provinces/{region_code}", response_class=JSONResponse)
async def get_provinces(region_code: str):
    return fetch_provinces(region_code)

@router.get("/cities-municipalities/{province_code}", response_class=JSONResponse)
async def get_cities_municipalities(province_code: str):
    return fetch_cities_municipalities(province_code)

@router.get("/region-locations/{region_code}", response_class=JSONResponse)
async def get_locations_for_region(region_code: str):
    return fetch_locations_for_region(region_code)