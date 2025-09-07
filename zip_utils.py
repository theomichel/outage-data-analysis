import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# Default file paths
DEFAULT_ZIP_GEO_FILE = os.path.join(os.path.dirname(__file__), 'constant_data', 'wa_washington_zip_codes_geo.min.json')
DEFAULT_ZIP_POPULATION_FILE = os.path.join(os.path.dirname(__file__), 'constant_data', 'washington_zip_populations.csv')

_zip_geo_df = None

def load_zip_codes(zip_file_path=None):
    """
    Load zip code boundaries from GeoJSON file.
    Returns a GeoDataFrame with zip code polygons.
    
    Args:
        zip_file_path (str, optional): Path to the zip code GeoJSON file.
                                      If None, uses default path.
    """
    global _zip_geo_df
    
    if _zip_geo_df is None:
        if zip_file_path is None:
            zip_file_path = DEFAULT_ZIP_GEO_FILE
        
        if not os.path.exists(zip_file_path):
            print(f"Warning: Zip code file not found at {zip_file_path}")
            return None
            
        try:
            print(f"Loading zip code boundaries from {zip_file_path}...")
            _zip_geo_df = gpd.read_file(zip_file_path)
            print(f"Loaded {len(_zip_geo_df)} zip code boundaries")
            return _zip_geo_df
        except Exception as e:
            print(f"Error loading zip code file: {e}")
            return None


def get_zip_code(lon, lat):
    """
    Get zip code for a given longitude and latitude using spatial join.
    
    Args:
        lon (float): Longitude coordinate
        lat (float): Latitude coordinate
        
    Returns:
        str: Zip code if found, None otherwise
    """
    # Handle missing coordinates
    if pd.isna(lon) or pd.isna(lat):
        return None
    
    # Load zip code boundaries
    if _zip_geo_df is None:
        raise Exception("Zip code boundaries not loaded. Load first with load_zip_codes().")
    
    try:
        # Create a Point geometry for the coordinates
        point = Point(lon, lat)
        
        # Create a GeoDataFrame with the point
        point_gdf = gpd.GeoDataFrame(
            [{'geometry': point}], 
            crs='EPSG:4326'  # WGS84 coordinate system
        )
        
        # Perform spatial join to find which zip code contains the point
        result = gpd.sjoin(
            point_gdf, 
            _zip_geo_df, 
            how='left', 
            predicate='within'
        )
        
        # Extract zip code if found
        if len(result) > 0 and 'ZCTA5CE10' in result.columns:
            zip_code = result.iloc[0]['ZCTA5CE10']
            return str(zip_code) if pd.notna(zip_code) else None
        
        return None
        
    except Exception as e:
        print(f"Error getting zip code for coordinates ({lon}, {lat}): {e}")
        return None
