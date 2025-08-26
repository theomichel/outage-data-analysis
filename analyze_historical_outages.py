import argparse
import pandas as pd
from datetime import datetime
from datetime import timedelta
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import matplotlib.animation as animation
import json
from matplotlib.patches import Circle
import matplotlib.dates as mdates
import contextily as ctx
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
from datetime import timezone
import geopandas as gpd
from shapely.geometry import Point
import os
from matplotlib.colors import LogNorm
import folium
from branca.colormap import LinearColormap

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configuration for impact rate visualization
IMPACT_RATE_CAP = 50.0  # Cap impact rates at this percentage for visualization

def has_changes(series):
    return series.nunique() > 1

def parse_datetime(date_str, time_str):
    # Assumes file_date is YYYY-MM-DD and file_time is HH:MM:SS
    try:
        return pd.to_datetime(f"{date_str} {time_str}")
    except Exception:
        return pd.NaT

def parse_est_restoration_time(time_str):
    # Try to parse various formats, fallback to NaT
    # Example format: '08/06 02:00 PM' (MM/DD HH:MM AM/PM)
    try:
        # Try with current year
        return pd.to_datetime(f"2024/{time_str}", format="%Y/%m/%d %I:%M %p")
    except Exception:
        try:
            # Try without year, let pandas infer
            return pd.to_datetime(time_str)
        except Exception:
            return pd.NaT

def format_timedelta_hhmm(td):
    if pd.isnull(td):
        return ""
    total_minutes = int(td.total_seconds() // 60)
    sign = " -" if total_minutes < 0 else " "
    total_minutes = abs(total_minutes)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{sign}{hours:02}:{minutes:02}"

# Helper functions to pick first/last non-null datetime per group, respecting order
def first_valid(s: pd.Series):
    idx = s.first_valid_index()
    return s.loc[idx] if idx is not None else pd.NaT

def last_valid(s: pd.Series):
    idx = s.last_valid_index()
    return s.loc[idx] if idx is not None else pd.NaT

# Global variables to store the zip code GeoDataFrame and population data for caching
_wa_zip_gdf = None
_wa_population_df = None

def load_wa_zip_codes():
    """
    Load Washington zip code boundaries from GeoJSON file.
    Returns a GeoDataFrame with zip code polygons.
    """
    global _wa_zip_gdf
    
    if _wa_zip_gdf is None:
        zip_file_path = os.path.join(os.path.dirname(__file__), 'constant_data', 'wa_washington_zip_codes_geo.min.json')
        
        if not os.path.exists(zip_file_path):
            print(f"Warning: Zip code file not found at {zip_file_path}")
            return None
            
        try:
            print("Loading Washington zip code boundaries...")
            _wa_zip_gdf = gpd.read_file(zip_file_path)
            print(f"Loaded {len(_wa_zip_gdf)} zip code boundaries")
            return _wa_zip_gdf
        except Exception as e:
            print(f"Error loading zip code file: {e}")
            return None
    
    return _wa_zip_gdf

def load_wa_population_data():
    """
    Load Washington zip code population data from CSV file.
    Returns a DataFrame with zip code and population information.
    """
    global _wa_population_df
    
    if _wa_population_df is None:
        pop_file_path = os.path.join(os.path.dirname(__file__), 'constant_data', 'washington_zip_populations.csv')
        
        if not os.path.exists(pop_file_path):
            print(f"Warning: Population file not found at {pop_file_path}")
            return None
            
        try:
            print("Loading Washington zip code population data...")
            _wa_population_df = pd.read_csv(pop_file_path)
            
            # Clean population data - remove quotes and convert to numeric
            _wa_population_df['Population'] = _wa_population_df['Population'].str.replace('"', '').str.replace(',', '').astype(int)
            
            # Create a mapping from ZIP to population
            _wa_population_df['ZIP'] = _wa_population_df['ZIP'].astype(str)
            
            print(f"Loaded population data for {len(_wa_population_df)} zip codes")
            return _wa_population_df
        except Exception as e:
            print(f"Error loading population file: {e}")
            return None
    
    return _wa_population_df

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
    wa_zips = load_wa_zip_codes()
    if wa_zips is None:
        return None
    
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
            wa_zips, 
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

# Create charts showing distribution of total_outage_length values and customers_impacted
def create_distribution_charts(summary):
    plt.figure(figsize=(12, 8))
    
    # Filter outage lengths while still in timedelta format (0 <= hours < 10 days)
    filtered_summary = summary[(summary['total_outage_length'] >= timedelta(hours=0)) & 
                              (summary['total_outage_length'] < timedelta(hours=24 * 10))]
    
    # Convert filtered total_outage_length to hours for visualization
    outage_lengths_hours = filtered_summary['total_outage_length'].apply(lambda x: x.total_seconds() / 3600)

    # Create histogram
    plt.hist(outage_lengths_hours, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
    plt.xlabel('Total Outage Length (hours)')
    plt.ylabel('Number of Outages')
    plt.title('Distribution of Total Outage Lengths')
    plt.grid(True, alpha=0.3)
    plt.xlim(0, 24 * 10)
    
    # Add statistics as text
    mean_hours = outage_lengths_hours.mean()
    median_hours = outage_lengths_hours.median()
    std_hours = outage_lengths_hours.std()
    
    stats_text = f'Mean: {mean_hours:.1f} hours\nMedian: {median_hours:.1f} hours\nStd Dev: {std_hours:.1f} hours'
    plt.text(0.7, 0.9, stats_text, transform=plt.gca().transAxes, 
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
             verticalalignment='top', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('outage_length_distribution.png', dpi=300, bbox_inches='tight')
    # plt.show()
    
    print(f"\nOutage length statistics:")
    print(f"Mean: {mean_hours:.1f} hours")
    print(f"Median: {median_hours:.1f} hours")
    print(f"Standard deviation: {std_hours:.1f} hours")
    print(f"Chart saved as 'outage_length_distribution.png'")

    # Create chart showing distribution of customers impacted
    plt.figure(figsize=(12, 8))
    
    # Convert customers_impacted to numeric, handling any non-numeric values
    customers_impacted_numeric = pd.to_numeric(summary['max_customers_impacted'], errors='coerce')
    customers_impacted_clean = customers_impacted_numeric.dropna()
    
    # Create histogram
    plt.hist(customers_impacted_clean, bins=200, alpha=0.7, color='lightcoral', edgecolor='black')
    plt.xlabel('Maximum Customers Impacted')
    plt.ylabel('Number of Outages')
    plt.title('Distribution of Maximum Customers Impacted per Outage')
    plt.grid(True, alpha=0.3)
    
    # Increase number of x-axis ticks
    plt.xticks(rotation=45)
    plt.locator_params(axis='x', nbins=40)
    
    # Add statistics as text
    mean_customers = customers_impacted_clean.mean()
    median_customers = customers_impacted_clean.median()
    std_customers = customers_impacted_clean.std()
    
    stats_text = f'Mean: {mean_customers:.0f} customers\nMedian: {median_customers:.0f} customers\nStd Dev: {std_customers:.0f} customers'
    plt.text(0.7, 0.9, stats_text, transform=plt.gca().transAxes, 
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
             verticalalignment='top', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('customers_impacted_distribution.png', dpi=300, bbox_inches='tight')
    #  plt.show()
    
    print(f"\nCustomers impacted statistics:")
    print(f"Mean: {mean_customers:.0f} customers")
    print(f"Median: {median_customers:.0f} customers")
    print(f"Standard deviation: {std_customers:.0f} customers")
    print(f"Chart saved as 'customers_impacted_distribution.png'")

def create_animated_outage_map(summary, animation_duration=30):
    """
    Create an animated map showing outages over time.
    
    Args:
        summary: DataFrame with outage data (one row per outage)
        animation_duration: Duration of animation in seconds (default: 30)
    """
    print("Creating animated outage map...")
    
    # Filter out outages without valid coordinates or customer data
    valid_outages = summary.dropna(subset=['center_lon', 'center_lat', 'max_customers_impacted'])
    valid_outages = valid_outages[valid_outages['max_customers_impacted'] > 0]
    
    if len(valid_outages) == 0:
        print("No valid outage data found for animation")
        return
    
    # Calculate time range
    start_time = valid_outages['first_start_time'].min()
    end_time = valid_outages['last_file_datetime'].max()
    total_duration = end_time - start_time
    
    print(f"Animation will cover {total_duration} compressed to {animation_duration} seconds")
    
    # Debug: Check actual coordinate ranges in the data
    print(f"Coordinate ranges in data:")
    print(f"Longitude: {valid_outages['center_lon'].min():.4f} to {valid_outages['center_lon'].max():.4f}")
    print(f"Latitude: {valid_outages['center_lat'].min():.4f} to {valid_outages['center_lat'].max():.4f}")
    
    # Set up the figure and map
    fig, ax = plt.subplots(figsize=(15, 10))
    
    # Set map bounds to Puget Sound area
    ax.set_xlim(-122.8, -121.8)  # Longitude range (Puget Sound)
    ax.set_ylim(47.0, 48.0)      # Latitude range (Puget Sound)
    
    # Add map background
    try:
        ctx.add_basemap(ax, crs='EPSG:4326', source=ctx.providers.OpenStreetMap.Mapnik)
        print("Added OpenStreetMap background")
    except Exception as e:
        print(f"Could not load map background: {e}")
        print("Using basic grid instead")
    
    # Add basic map elements
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title('Puget Sound Outage Animation')
    ax.grid(True, alpha=0.3)
    
    # Calculate circle sizes (scale customer counts to reasonable circle sizes)
    max_customers = valid_outages['max_customers_impacted'].max()
    min_customers = valid_outages['max_customers_impacted'].min()
    
    # Scale circle radius from 0.01 to 0.1 degrees (roughly 1-10 km)
    def scale_radius(customers):
        if max_customers == min_customers:
            return 0.05
        return 0.01 + 0.09 * (customers - min_customers) / (max_customers - min_customers)
    
    # Animation setup
    fps = 10  # frames per second
    total_frames = animation_duration * fps
    time_step = total_duration / total_frames
    
    # Store circles for each frame
    circles = []
    time_indicators = []
    
    def animate(frame):
        # Clear previous circles
        for circle in circles:
            circle.remove()
        circles.clear()
        
        for indicator in time_indicators:
            indicator.remove()
        time_indicators.clear()
        
        # Calculate current time
        current_time = start_time + frame * time_step
        
        # Add time indicator
        time_text = ax.text(0.02, 0.98, f'Time: {current_time.strftime("%Y-%m-%d %H:%M")}', 
                           transform=ax.transAxes, fontsize=12, 
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        time_indicators.append(time_text)
        
        # Add progress bar
        progress = frame / total_frames
        progress_bar = ax.axhline(y=47.0, xmin=0, xmax=progress, color='red', linewidth=3, alpha=0.7)
        time_indicators.append(progress_bar)
        
        # Add circles for active outages
        for _, outage in valid_outages.iterrows():
            outage_start = outage['first_start_time']
            outage_end = outage['last_file_datetime']
            
            # Check if outage is active at current time
            if outage_start <= current_time <= outage_end:
                # Create circle
                radius = scale_radius(outage['max_customers_impacted'])
                circle = Circle((outage['center_lon'], outage['center_lat']), 
                              radius, alpha=0.6, color='red', edgecolor='darkred')
                ax.add_patch(circle)
                circles.append(circle)
                
                # Add customer count label for larger outages
                if outage['max_customers_impacted'] > max_customers * 0.5:  # Top 50%
                    label = ax.text(outage['center_lon'], outage['center_lat'], 
                                  f"{outage['max_customers_impacted']:.0f}", 
                                  ha='center', va='center', fontsize=8, 
                                  bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8))
                    circles.append(label)
        
        return circles + time_indicators
    
    # Create animation
    anim = animation.FuncAnimation(fig, animate, frames=total_frames, 
                                 interval=1000//fps, blit=False, repeat=True)
    
    # Save animation
    print("Saving animation (this may take a while)...")
    anim.save('outage_animation.gif', writer='pillow', fps=fps)
    print("Animation saved as 'outage_animation.gif'")
    
    # Show the animation
    # plt.show()

def create_cumulative_polygon_animation(summary, animation_duration=30):
    """
    Create an animated map showing cumulative outage impacts using actual polygons.
    
    Args:
        summary: DataFrame with outage data (one row per outage)
        animation_duration: Duration of animation in seconds (default: 30)
    """
    print("Creating cumulative polygon outage animation...")
    
    # Filter out outages without valid coordinates, customer data, or polygon data
    valid_outages = summary.dropna(subset=['center_lon', 'center_lat', 'max_customers_impacted', 'last_polygon_json'])
    valid_outages = valid_outages[valid_outages['max_customers_impacted'] > 0]
    
    if len(valid_outages) == 0:
        print("No valid outage data found for polygon animation")
        return
    
    # Calculate time range
    start_time = valid_outages['first_start_time'].min()
    end_time = valid_outages['last_file_datetime'].max()
    total_duration = end_time - start_time
    
    print(f"Animation will cover {total_duration} compressed to {animation_duration} seconds")
    
    # Set up the figure and map
    fig, ax = plt.subplots(figsize=(15, 10))
    
    # Set map bounds to Puget Sound area
    ax.set_xlim(-122.8, -121.8)  # Longitude range (Puget Sound) -122.8, -121.8
    ax.set_ylim(47.0, 48.0)      # Latitude range (Puget Sound) 47.0, 48.0
    
    # Add map background
    try:
        ctx.add_basemap(ax, crs='EPSG:4326', source=ctx.providers.OpenStreetMap.Mapnik)
        print("Added OpenStreetMap background")
    except Exception as e:
        print(f"Could not load map background: {e}")
        print("Using basic grid instead")
    
    # Add basic map elements
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title('Cumulative Outage Impact Animation')
    ax.grid(True, alpha=0.3)
    
    # Calculate customer-hours for each outage
    valid_outages['outage_hours'] = valid_outages['total_outage_length'].apply(lambda x: x.total_seconds() / 3600)
    valid_outages['customer_hours'] = valid_outages['max_customers_impacted'] * valid_outages['outage_hours']
    
    # Normalize customer-hours for color intensity (0 to 1)
    max_customer_hours = valid_outages['customer_hours'].max()
    min_customer_hours = valid_outages['customer_hours'].min()
    
    def normalize_intensity(customer_hours):
        if max_customer_hours == min_customer_hours:
            return 0.5
        return (customer_hours - min_customer_hours) / (max_customer_hours - min_customer_hours)
    
    # Pre-parse all polygons to avoid repeated JSON parsing
    print("Pre-parsing polygon data...")
    parsed_polygons = []
    for idx, (_, outage) in enumerate(valid_outages.iterrows()):
        try:
            polygon_data = json.loads(outage['last_polygon_json'])
            outage_polygons = []
            
            for polygon_idx, polygon_points in enumerate(polygon_data):
                if len(polygon_points) >= 3:  # Need at least 3 points for a polygon
                     # Convert string coordinates to floats
                     float_points = []
                     for point in polygon_points:
                         try:
                             lon = float(point[0])
                             lat = float(point[1])
                             float_points.append([lon, lat])
                         except (ValueError, TypeError, IndexError) as e:
                             print(f"Error converting point {point} to float: {e}")
                             continue
                     
                     if len(float_points) >= 3:  # Still need at least 3 points after conversion
                         # Calculate color intensity based on customer-hours
                         intensity = normalize_intensity(outage['customer_hours'])
                         
                         outage_polygons.append({
                             'points': float_points,  # Store the converted float coordinates
                             'intensity': intensity,
                             'start_time': outage['first_start_time'],
                             'outage_id': outage['outage_id'],
                             'polygon_id': f"{outage['outage_id']}_{polygon_idx}"  # Unique identifier
                         })
                         print(f"Adding polygon {outage['outage_id']}_{polygon_idx} with {len(float_points)} points")
            
            parsed_polygons.extend(outage_polygons)
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"Error parsing polygon for outage {outage['outage_id']}: {e}")
            continue
    
    print(f"Parsed {len(parsed_polygons)} polygons")
    
    # Animation setup - reduce frame rate for better performance
    fps = 5  # Reduced from 10 to 5 frames per second
    total_frames = animation_duration * fps
    time_step = total_duration / total_frames
    
    # Store all polygon patches (they stay on the map)
    all_polygon_patches = []
    added_polygon_ids = set()  # Track which polygons have been added
    time_indicators = []
    
    def animate(frame):
        # Clear previous time indicators only
        for indicator in time_indicators:
            indicator.remove()
        time_indicators.clear()
        
        # Calculate current time
        current_time = start_time + frame * time_step
        
        # Add time indicator
        time_text = ax.text(0.02, 0.98, f'Time: {current_time.strftime("%Y-%m-%d %H:%M")}', 
                           transform=ax.transAxes, fontsize=12, 
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        time_indicators.append(time_text)
        
        # Add progress bar
        progress = frame / total_frames
        progress_bar = ax.axhline(y=47.0, xmin=0, xmax=progress, color='red', linewidth=3, alpha=0.7)
        time_indicators.append(progress_bar)
        
        # Add new polygons that have started since last frame
        for polygon_info in parsed_polygons:
            if polygon_info['start_time'] <= current_time:
                # Check if this polygon is already on the map using unique ID
                if polygon_info['polygon_id'] not in added_polygon_ids:
                    # Create polygon patch
                    print(f"Adding polygon {polygon_info['polygon_id']} {polygon_info['points']}")
                    polygon_patch = Polygon(
                        polygon_info['points'],  # Use the raw [lon, lat] points directly
                        closed=True,
                        facecolor=(1.0, 0.0, 0.0),
                        edgecolor='darkred', 
                        #alpha=polygon_info['intensity']
                    )
                    
                    ax.add_patch(polygon_patch)
                    all_polygon_patches.append(polygon_patch)
                    added_polygon_ids.add(polygon_info['polygon_id'])
        
        return time_indicators
    
    # Create animation
    anim = animation.FuncAnimation(fig, animate, frames=total_frames, 
                                     interval=1000/fps, blit=False, repeat=True)
    
    # Save animation
    print("Saving cumulative polygon animation (this may take a while)...")
    anim.save('cumulative_outage_animation.gif', writer='pillow', fps=fps)
    print("Animation saved as 'cumulative_outage_animation.gif'")
    
    # Show the animation
    plt.show()

# gives a text report and dataframe of how many outages in the given date range meet the given thresholds
def filter_to_high_impact_outages(summary, start_date_utc=datetime.min.replace(tzinfo=timezone.utc), end_date_utc=datetime.now(timezone.utc), min_customers_impacted=100, min_estimated_remaining_outage_length=timedelta(hours=6), min_actual_outage_length=timedelta(hours=1)):
    # filter summary to only include outages in the given date range
    summary = summary[(summary['first_start_time'] >= start_date_utc) & (summary['first_start_time'] <= end_date_utc)]


    # count the number of outages that meet the given thresholds
    num_outages = len(summary)
    print(f"Number of outages in the given date range: {num_outages}")
    print(f"Number of outages with at least {min_customers_impacted} customers impacted: {len(summary[summary['max_customers_impacted'] >= min_customers_impacted])}")
    print(f"Number of outages with at least {min_estimated_remaining_outage_length} hours of predicted outage length: {len(summary[summary['largest_estimated_remaining_outage_length'] >= min_estimated_remaining_outage_length])}")
    
    # Count outages that meet both thresholds
    both_thresholds = summary[
        (summary['max_customers_impacted'] >= min_customers_impacted) & 
        (summary['largest_estimated_remaining_outage_length'] >= min_estimated_remaining_outage_length) &
        (summary['total_outage_length'] >= min_actual_outage_length)
    ]
    print(f"Number of outages meeting both thresholds: {len(both_thresholds)}")
    return both_thresholds

def create_impact_heatmaps(impact_df, population_data, png_filename='puget_sound_impact_heatmap.png', html_filename='puget_sound_impact_heatmap.html'):
    """
    Create heatmaps showing outage impact rates by zip code.
    
    Args:
        impact_df: DataFrame with zip code impact data
        population_data: DataFrame with population data
        png_filename: Filename for the static PNG heatmap (default: 'puget_sound_impact_heatmap.png')
        html_filename: Filename for the interactive HTML map (default: 'puget_sound_impact_heatmap.html')
    """
    if len(impact_df) == 0:
        print("No impact data available for heatmap creation")
        return
    
    # Load zip code boundaries
    wa_zips = load_wa_zip_codes()
    if wa_zips is None:
        print("Could not load zip code boundaries for heatmap")
        return
    
    # Prepare data for mapping
    # Create a mapping from zip code to impact rate
    zip_impact_map = {}
    for _, row in impact_df.iterrows():
        zip_code = row['zip_code']
        if pd.notna(zip_code) and 'impact_rate' in row and pd.notna(row['impact_rate']):
            zip_impact_map[str(zip_code)] = row['impact_rate']
    
    if not zip_impact_map:
        print("No valid impact rate data available for heatmap")
        return
    
    # Merge impact data with zip code boundaries
    wa_zips['ZCTA5CE10_str'] = wa_zips['ZCTA5CE10'].astype(str)
    wa_zips['impact_rate'] = wa_zips['ZCTA5CE10_str'].map(zip_impact_map)
    
    # Filter to only show zip codes with impact data
    impacted_zips = wa_zips[wa_zips['impact_rate'].notna()].copy()
    
    if len(impacted_zips) == 0:
        print("No zip codes with impact data found in boundary file")
        return
    
    print(f"Creating heatmap for {len(impacted_zips)} impacted zip codes")
    
    # Create Puget Sound heatmap
    create_puget_sound_heatmap(impacted_zips, png_filename)
    
    # Create interactive HTML map
    create_interactive_html_map(impacted_zips, impact_df, population_data, html_filename)

def create_puget_sound_heatmap(impacted_zips, filename='puget_sound_impact_heatmap.png'):
    """Create a heatmap of the Puget Sound area showing impact rates by zip code."""
    print("Creating Puget Sound impact heatmap...")
    
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Calculate bounds based on actual data coverage
    if len(impacted_zips) > 0:
        # Get the bounds of all impacted zip codes
        bounds = impacted_zips.geometry.bounds
        lon_min, lat_min, lon_max, lat_max = bounds.minx.min(), bounds.miny.min(), bounds.maxx.max(), bounds.maxy.max()
        
        # Add some padding around the bounds
        lon_padding = (lon_max - lon_min) * 0.1
        lat_padding = (lat_max - lat_min) * 0.1
        
        ax.set_xlim(lon_min - lon_padding, lon_max + lon_padding)
        ax.set_ylim(lat_min - lat_padding, lat_max + lat_padding)
        
        print(f"Dynamic bounds: Longitude {lon_min:.3f} to {lon_max:.3f}, Latitude {lat_min:.3f} to {lat_max:.3f}")
    else:
        # Fallback to original Puget Sound bounds if no data
        ax.set_xlim(-122.8, -121.8)  # Longitude range (Puget Sound)
        ax.set_ylim(47.0, 48.0)      # Latitude range (Puget Sound)
    
    # Add map background with full opacity for maximum visibility
    try:
        ctx.add_basemap(ax, crs='EPSG:4326', source=ctx.providers.CartoDB.Voyager, alpha=1.0)
        print("Added CartoDB Voyager background to Puget Sound heatmap")
    except Exception as e:
        print(f"Could not load map background for Puget Sound: {e}")
        print("Using basic grid instead")
    
    # Load all Washington zip codes for background
    wa_zips = load_wa_zip_codes()
    if wa_zips is not None:
        wa_zips.plot(ax=ax, color='lightgray', edgecolor='black', linewidth=0.5, alpha=0.3)
    
    # Filter impacted zip codes to only those in the displayed area for local color scaling
    if len(impacted_zips) > 0:
        # Get the bounds of all impacted zip codes for filtering
        bounds = impacted_zips.geometry.bounds
        lon_min, lat_min, lon_max, lat_max = bounds.minx.min(), bounds.miny.min(), bounds.maxx.max(), bounds.maxy.max()
        
        # Add some padding around the bounds for filtering
        lon_padding = (lon_max - lon_min) * 0.1
        lat_padding = (lat_max - lat_min) * 0.1
        
        display_bounds = (lon_min - lon_padding, lon_max + lon_padding, lat_min - lat_padding, lat_max + lat_padding)
    else:
        # Fallback to original Puget Sound bounds if no data
        display_bounds = (-122.8, -121.8, 47.0, 48.0)  # lon_min, lon_max, lat_min, lat_max
    
    # Filter to zip codes in the displayed area
    displayed_zips = impacted_zips[
        (impacted_zips.geometry.bounds.minx >= display_bounds[0]) &
        (impacted_zips.geometry.bounds.maxx <= display_bounds[1]) &
        (impacted_zips.geometry.bounds.miny >= display_bounds[2]) &
        (impacted_zips.geometry.bounds.maxy <= display_bounds[3])
    ].copy()
    
    # Use local min/max for color scaling if we have data in the area
    if len(displayed_zips) > 0:
        local_min = displayed_zips['impact_rate'].min()
        local_max = displayed_zips['impact_rate'].max()
        print(f"Displayed area: {len(displayed_zips)} zip codes with impact rates from {local_min:.2f}% to {local_max:.2f}%")
        
                                            # Plot impacted zip codes with color based on local impact rate range using linear scale
        plot = impacted_zips.plot(
                ax=ax, 
                column='impact_rate', 
                cmap='Reds', 
                legend=True,
                                 legend_kwds={'label': 'Impact Rate (sum of impacted customers across all outages / total customers in the zip, as a %) - Linear Scale', 'shrink': 0.8, 'format': lambda x, pos: f'{x:.0f}+' if x == min(local_max, IMPACT_RATE_CAP) else f'{x:.0f}'},
                edgecolor='black', 
                linewidth=0.2,  # Make borders thinner
                missing_kwds={'color': 'lightgray'},
                vmin=local_min,
                vmax=min(local_max, IMPACT_RATE_CAP),
                alpha=0.3,  # Reduce opacity to 30% so background shows through more
                                 # Linear scale - no norm parameter needed
            )
        
        
    else:
                 # Fallback to full range if no local data
         print("No impacted zip codes found in Puget Sound area, using full range")
         plot = impacted_zips.plot(
                 ax=ax, 
                 column='impact_rate', 
                 cmap='Reds', 
                 legend=True,
                 legend_kwds={'label': 'Impact Rate (sum of impacted customers across all outages / total customers in the zip, as a %) - Linear Scale', 'shrink': 0.8, 'format': lambda x, pos: f'{x:.0f}+' if x == min(impacted_zips['impact_rate'].max(), IMPACT_RATE_CAP) else f'{x:.0f}'},
                edgecolor='black', 
                linewidth=0.2,  # Make borders thinner
                missing_kwds={'color': 'lightgray'},
                vmin=impacted_zips['impact_rate'].min(),
                vmax=min(impacted_zips['impact_rate'].max(), IMPACT_RATE_CAP),
                alpha=0.3,  # Reduce opacity to 30% so background shows through more
                                 # Linear scale - no norm parameter needed
            )
        
        
    
    ax.set_title('Puget Sound Area: Outage Impact Rate by Zip Code', fontsize=16, fontweight='bold')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.grid(True, alpha=0.3)
    
    # Add statistics text
    max_impact = impacted_zips['impact_rate'].max()
    avg_impact = impacted_zips['impact_rate'].mean()
    stats_text = f'Max Impact: {max_impact:.2f}%\nAvg Impact: {avg_impact:.2f}%'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
            verticalalignment='top')
    
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"Puget Sound heatmap saved as '{filename}'")

def create_interactive_html_map(impacted_zips, impact_df, population_data, filename='puget_sound_impact_heatmap.html'):
    """Create an interactive HTML map with zoom and popup functionality."""
    print("Creating interactive HTML map...")
    
    # Calculate center point for the map
    bounds = impacted_zips.geometry.bounds
    center_lat = (bounds.miny.min() + bounds.maxy.max()) / 2
    center_lon = (bounds.minx.min() + bounds.maxx.max()) / 2
    
    # Create the map centered on the data
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=9,
        tiles='CartoDB voyager'
    )
    
    # Create a color map for the impact rates
    min_rate = impacted_zips['impact_rate'].min()
    max_rate = min(impacted_zips['impact_rate'].max(), IMPACT_RATE_CAP)  # Cap impact rates for visualization
    
     # Create linear color mapping for impact rate visualization
     
    colormap = LinearColormap(
           colors=['#fee5d9', '#fcae91', '#fb6a4a', '#de2d26', '#a50f15'],
           vmin=min_rate,
           vmax=max_rate,
                       caption='Impact Rate (sum of impacted customers across all outages / total customers in the zip, as a %, capped at 50%)'
       )
    
                   # Add the color map to the map
    colormap.add_to(m)
     
                   # Add custom CSS to position legend further to the left and show full text
     # this is admittedly hackery, and would need to be cleaned up if we wanted to productionize this
    legend_css = '''
     <style>
     .leaflet-right {
         right: 75px !important;
     }
     #legend {
         width: 525px !important;
     }
     # TODO: check whether there's a better way to do this
     /* Override default Leaflet highlighting to prevent bounding box */
     .leaflet-interactive:hover,
     .leaflet-interactive:focus,
     .leaflet-interactive:active {
         outline: none !important;
         box-shadow: none !important;
         border: none !important;
     }
     /* Prevent any default Leaflet styling */
     .leaflet-interactive {
         outline: none !important;
         box-shadow: none !important;
         border: none !important;
     }
     /* Override any Leaflet path styling that might cause bounding box */
     .leaflet-interactive path {
         outline: none !important;
         box-shadow: none !important;
     }
     </style>
     '''
    m.get_root().html.add_child(folium.Element(legend_css))
    
    # Create a mapping from zip code to impact data for popups
    zip_data_map = {}
    for _, row in impact_df.iterrows():
        zip_code = row['zip_code']
        if pd.notna(zip_code):
            zip_data_map[str(zip_code)] = {
                'total_customers': row['total_customers'],
                'num_outages': row['num_outages'],
                'impact_rate': row.get('impact_rate', 'N/A'),
                'population': row.get('Population', 'N/A'),
                'city_town': row.get('City/Town', 'Unknown'),
                'county': row.get('County', 'Unknown')
            }
    
    # Add zip code polygons to the map
    for idx, row in impacted_zips.iterrows():
        zip_code = row['ZCTA5CE10_str']
        impact_rate = row['impact_rate']
        
        if pd.notna(impact_rate):
            # Use linear color mapping for impact rate visualization
            capped_rate = min(impact_rate, IMPACT_RATE_CAP)  # Apply cap
            color = colormap.rgb_hex_str(capped_rate)
            
            # Get data for popup
            zip_data = zip_data_map.get(zip_code, {})
            
                         # Create popup content with safe formatting
            population = zip_data.get('population', 'N/A')
            if isinstance(population, (int, float)):
                 population_str = f"{int(population):,}"  # Convert to int and format with commas
            else:
                 population_str = str(population)
            
            total_customers = zip_data.get('total_customers', 'N/A')
            customers_str = f"{total_customers:,}" if isinstance(total_customers, (int, float)) else str(total_customers)
            
            impact_rate = zip_data.get('impact_rate', 'N/A')
            impact_str = f"{impact_rate:.2f}%" if isinstance(impact_rate, (int, float)) else str(impact_rate)
            
            popup_content = f"""
            <div style="font-family: Arial, sans-serif; min-width: 200px;">
                <h4 style="margin: 0 0 10px 0; color: #333;">ZIP Code: {zip_code}</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 2px 0;"><strong>Population:</strong></td><td style="padding: 2px 0;">{population_str}</td></tr>
                    <tr><td style="padding: 2px 0;"><strong># Outages:</strong></td><td style="padding: 2px 0;">{zip_data.get('num_outages', 'N/A')}</td></tr>
                    <tr><td style="padding: 2px 0;"><strong>Total Customers Impacted:</strong></td><td style="padding: 2px 0;">{customers_str}</td></tr>
                    <tr><td style="padding: 2px 0;"><strong>Impact Rate:</strong></td><td style="padding: 2px 0;">{impact_str}</td></tr>
                    <tr><td style="padding: 2px 0;"><strong>City/Town:</strong></td><td style="padding: 2px 0;">{zip_data.get('city_town', 'Unknown')}</td></tr>
                    <tr><td style="padding: 2px 0;"><strong>County:</strong></td><td style="padding: 2px 0;">{zip_data.get('county', 'Unknown')}</td></tr>
                </table>
            </div>
            """
            
                         # Add the polygon to the map
            folium.GeoJson(
                   row['geometry'],
                   style_function=lambda x, color=color: {
                       'fillColor': color,
                       'color': 'black',
                       'weight': 0.3,  # Make borders thinner
                       'fillOpacity': 0.3  # Reduce opacity to 30% so background shows through more
                   },
                   popup=folium.Popup(popup_content, max_width=300),
                   tooltip=f"ZIP {zip_code}: {impact_rate:.2f}% impact",
                   highlight_function=lambda x: {
                       'weight': 2,  # Thicker border on hover instead of square
                       'color': 'black',  # Same color as non-highlighted borders
                       'fillOpacity': 0.7
                   },
                   smooth_factor=0  # Disable smoothing to prevent bounding box artifacts
               ).add_to(m)
    
    # Fit the map to the data bounds
    bounds = impacted_zips.geometry.bounds
    m.fit_bounds([[bounds.miny.min(), bounds.minx.min()], 
                  [bounds.maxy.max(), bounds.maxx.max()]])
    
    # Save the map
    m.save(filename)
    print(f"Interactive HTML map saved as '{filename}'")

def analyze_outage_impacts_by_area(summary):
    # TODO: implement
    pass

def create_zip_code_impact_analysis(outages_df, population_data=None, png_filename='puget_sound_impact_heatmap.png', html_filename='puget_sound_impact_heatmap.html'):
    """
    Create zip code impact analysis and visualizations for a given outages DataFrame.
    
    Args:
        outages_df: DataFrame with outage data (must have 'center_lon', 'center_lat', 'max_customers_impacted' columns)
        population_data: Optional DataFrame with population data for normalization
        png_filename: Filename for the static PNG heatmap (default: 'puget_sound_impact_heatmap.png')
        html_filename: Filename for the interactive HTML map (default: 'puget_sound_impact_heatmap.html')
    
    Returns:
        impact_df: DataFrame with zip code impact analysis
    """
    if len(outages_df) == 0:
        print("No outages provided for zip code impact analysis")
        return None
    
    # Add zip code for each outage based on the center point - use bulk spatial join for efficiency
    print("Performing bulk spatial join to assign zip codes...")
    
    # Filter out rows with missing coordinates
    valid_coords = outages_df.dropna(subset=['center_lon', 'center_lat']).copy()
    
    if len(valid_coords) > 0:
        # Create Point geometries for all valid coordinates at once
        valid_coords['geometry'] = valid_coords.apply(
            lambda row: Point(row['center_lon'], row['center_lat']), axis=1
        )
        
        # Create GeoDataFrame for all points
        points_gdf = gpd.GeoDataFrame(valid_coords, crs='EPSG:4326')
        
        # Load zip code boundaries
        wa_zips = load_wa_zip_codes()
        if wa_zips is not None:
            # Perform bulk spatial join
            result = gpd.sjoin(points_gdf, wa_zips, how='left', predicate='within')
            
            # Create mapping from index to zip code
            zip_mapping = result.set_index(result.index)['ZCTA5CE10'].astype(str)
            
            # Apply mapping back to original dataframe
            outages_df.loc[valid_coords.index, 'zip_code'] = zip_mapping
        else:
            print("Warning: Could not load zip code boundaries")
    
    # Fill missing values with None - use a more explicit approach
    outages_df['zip_code'] = outages_df['zip_code'].where(outages_df['zip_code'].notna(), None)
    
    # Calculate total impacted customers per zip code
    # Group by zip code and calculate both sum of customers and count of outages
    zip_code_impacts = outages_df.groupby('zip_code').agg({
        'max_customers_impacted': 'sum',
        'outage_id': 'count'
    }).rename(columns={
        'max_customers_impacted': 'total_customers',
        'outage_id': 'num_outages'
    })
    
    # Create a DataFrame with zip code impacts and population data for sorting
    impact_df = zip_code_impacts.reset_index()
    
    # Add population data if available
    if population_data is not None:
        impact_df['zip_str'] = impact_df['zip_code'].astype(str)
        impact_df = impact_df.merge(population_data, left_on='zip_str', right_on='ZIP', how='left')
        impact_df['impact_rate'] = (impact_df['total_customers'] / impact_df['Population']) * 100
        # Sort by impact rate (highest first), then by total customers for ties
        impact_df = impact_df.sort_values(['impact_rate', 'total_customers'], ascending=[False, False])
    else:
        # If no population data, sort by total customers
        impact_df = impact_df.sort_values('total_customers', ascending=False)
    
    # Print the analysis results
    print(f"\nTotal impacted customers by zip code:")
    print("=" * 100)
    print(f"{'ZIP Code':<10} {'Total Customers':<15} {'# Outages':<10} {'Population':<12} {'Impact Rate':<12} {'City/Town':<20}")
    print("-" * 100)
    
    for _, row in impact_df.iterrows():
        zip_code = row['zip_code']
        total_customers = row['total_customers']
        num_outages = row['num_outages']
        
        if pd.notna(zip_code):  # Skip None/NaN zip codes
            if population_data is not None and 'Population' in row and 'City/Town' in row:
                population = row['Population']
                city_town = row['City/Town']
                impact_rate = row['impact_rate']
                if pd.notna(population) and pd.notna(impact_rate):
                    print(f"{zip_code:<10} {total_customers:>14,.0f} {num_outages:>9} {population:>11,.0f} {impact_rate:>11.2f}% {city_town:<20}")
                else:
                    print(f"{zip_code:<10} {total_customers:>14,.0f} {num_outages:>9} {'N/A':>11} {'N/A':>11} {'Unknown':<20}")
            else:
                print(f"{zip_code:<10} {total_customers:>14,.0f} {num_outages:>9} {'N/A':>11} {'N/A':>11} {'Unknown':<20}")
        else:
            print(f"{'Unknown':<10} {total_customers:>14,.0f} {num_outages:>9} {'N/A':>11} {'N/A':>11} {'Unknown':<20}")
    
    # Summary statistics
    total_impacted = zip_code_impacts['total_customers'].sum()
    total_outages = zip_code_impacts['num_outages'].sum()
    num_zip_codes = len(zip_code_impacts)
    print("-" * 100)
    print(f"\nSummary:")
    print(f"  Total impacted customers: {total_impacted:,.0f}")
    print(f"  Total number of outages: {total_outages}")
    print(f"  Number of zip codes affected: {num_zip_codes}")
    if num_zip_codes > 0:
        avg_per_zip = total_impacted / num_zip_codes
        avg_outages_per_zip = total_outages / num_zip_codes
        print(f"  Average customers per zip code: {avg_per_zip:,.0f}")
        print(f"  Average outages per zip code: {avg_outages_per_zip:.1f}")
        
        # Calculate population-normalized statistics if population data is available
        if population_data is not None:
            # Get total population for affected zip codes
            affected_zips = [str(zip_code) for zip_code in zip_code_impacts.index if pd.notna(zip_code)]
            affected_pop_data = population_data[population_data['ZIP'].isin(affected_zips)]
            if len(affected_pop_data) > 0:
                total_population = affected_pop_data['Population'].sum()
                overall_impact_rate = (total_impacted / total_population) * 100
                print(f"  Total population in affected zip codes: {total_population:,.0f}")
                print(f"  Overall impact rate: {overall_impact_rate:.2f}% of population")
    
    # Create heatmaps showing impact rates by zip code
    if len(impact_df) > 0:
        create_impact_heatmaps(impact_df, population_data, png_filename, html_filename)
    
    return impact_df

def main():
    parser = argparse.ArgumentParser(description="Analyze historical outages from multiple utilities.")
    parser.add_argument('-f', '--files', nargs='+', required=True,
                       help='Input CSV file(s) - can specify multiple files to combine')
    parser.add_argument('-o', '--output', default='outage_summary.csv',
                       help='Output CSV file name (default: outage_summary.csv)')
    parser.add_argument('--png-heatmap', default='puget_sound_impact_heatmap.png',
                       help='Filename for the static PNG heatmap (default: puget_sound_impact_heatmap.png)')
    parser.add_argument('--html-heatmap', default='puget_sound_impact_heatmap.html',
                       help='Filename for the interactive HTML heatmap (default: puget_sound_impact_heatmap.html)')
    args = parser.parse_args()
    
    # Read and combine multiple files
    dfs = []
    for file_path in args.files:
        print(f"Reading {file_path}...")
        df = pd.read_csv(file_path)
        dfs.append(df)
        print(f"  Loaded {len(df)} rows")
    
    # Combine all dataframes
    df = pd.concat(dfs, ignore_index=True)
    print(f"Combined total: {len(df)} rows from {len(args.files)} file(s)")
    
    # Show utility breakdown
    if 'utility' in df.columns:
        utility_counts = df['utility'].value_counts()
        print(f"\nData by utility:")
        for utility, count in utility_counts.items():
            print(f"  {utility}: {count} rows ({count/len(df)*100:.1f}%)")
    else:
        print("Warning: No 'utility' column found in data")

    
    # Force all time columns in the input to datetime, coercing invalid/empty to NaT
    df["est_restoration_time"] = pd.to_datetime(df["est_restoration_time"], errors="coerce", utc=True, format=TIME_FORMAT)
    df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce", utc=True, format=TIME_FORMAT)
    df["file_datetime"] = pd.to_datetime(df["file_datetime"], errors="coerce", utc=True, format=TIME_FORMAT)

    df = df.sort_values(["utility","outage_id", "file_datetime"])


    # Find the earliest and latest update datetimes in the dataset
    min_file_datetime = df["file_datetime"].min()
    max_file_datetime = df["file_datetime"].max()

    # For each outage, get the first and last update datetimes
    first_last = df.groupby(["utility","outage_id"])["file_datetime"].agg(["first", "last"])

    # Outages to exclude: those whose first update is at min or last update is at max
    to_exclude = first_last[(first_last["first"] == min_file_datetime) | (first_last["last"] == max_file_datetime)].index

    # Filter out these outages from the dataframe
    filtered_df = df[~df["outage_id"].isin(to_exclude)].copy()

    # Total number of unique outages (after filtering)
    total_outages = filtered_df["outage_id"].nunique()
    print(f"Total number of outages analyzed (excluding edge cases): {total_outages}")
    
    # calculate the estimated remaining outage length from each outage update
    filtered_df["estimated_remaining_outage_length"] = filtered_df["est_restoration_time"] - filtered_df["file_datetime"]

    # Show utility breakdown for filtered outages
    if 'utility' in filtered_df.columns:
        utility_outage_counts = filtered_df.groupby('utility')['outage_id'].nunique()
        print(f"\nOutages by utility (after filtering):")
        for utility, count in utility_outage_counts.items():
            print(f"  {utility}: {count} outages ({count/total_outages*100:.1f}%)")

    # 1. Polygon or Bounding Box changes
    polygon_changes = filtered_df.groupby("outage_id")["polygon_json"].agg(has_changes)
    polygon_change_ids = polygon_changes[polygon_changes].index.tolist()
    num_polygon_changes = len(polygon_change_ids)
    print(f"Number of outages with polygon changes: {num_polygon_changes}")
    #print(f"Outage IDs with polygon changes: {polygon_change_ids}")

    # 2. Outage Start Time changes
    start_time_changes = filtered_df.groupby("outage_id")["start_time"].agg(has_changes)
    start_time_change_ids = start_time_changes[start_time_changes].index.tolist()
    num_start_time_changes = len(start_time_change_ids)
    print(f"Number of outages with start time changes: {num_start_time_changes}")
    # print(f"Outage IDs with start time changes: {start_time_change_ids}")

    # 3. Create dataframe with one row per outage

    # Ensure grouping preserves the sorted order above so first/last valid are chronological
    filtered_df = filtered_df.sort_values(["outage_id", "file_datetime"]) 

    summary = (
        filtered_df.groupby(["utility","outage_id"], sort=False)
        .agg(
            first_start_time=("start_time", "first"),
            first_est_restoration_time=("est_restoration_time", first_valid),
            last_est_restoration_time=("est_restoration_time", last_valid),
            largest_estimated_remaining_outage_length=("estimated_remaining_outage_length", "max"),
            first_file_datetime=("file_datetime", "first"),
            last_file_datetime=("file_datetime", "last"),
            last_polygon_json=("polygon_json", "last"),
            last_start_time=("start_time", "last"),
            max_customers_impacted=("customers_impacted", "max"),
            center_lon=("center_lon", "last"),
            center_lat=("center_lat", "last"),
        )
        .reset_index()
    )
    
    print(f"last_file_datetime: {summary['last_file_datetime']}")


    # Parse start time and estimated restoration times as datetimes for calculations
    summary["first_start_time"] = pd.to_datetime(summary["first_start_time"], utc=True, format=TIME_FORMAT)
    summary["last_file_datetime"] = pd.to_datetime(summary["last_file_datetime"], utc=True, format=TIME_FORMAT)
    summary["first_est_restoration_time"] = pd.to_datetime(summary["first_est_restoration_time"], utc=True, format=TIME_FORMAT)
    summary["last_est_restoration_time"] = pd.to_datetime(summary["last_est_restoration_time"], utc=True, format=TIME_FORMAT)

    # calculate outage lengths
    summary["total_outage_length"] = summary["last_file_datetime"] - summary["first_start_time"]
    summary["length_from_first_est_restoration"] = summary["first_est_restoration_time"] - summary["first_start_time"]
    summary["length_from_last_est_restoration"] = summary["last_est_restoration_time"] - summary["first_start_time"]

    # Calculate difference between actual outage length and length as estimated from first est restoration, formatted as HH:MM
    summary["diff_actual_vs_first_est"] = (summary["total_outage_length"] - summary["length_from_first_est_restoration"]).apply(format_timedelta_hhmm)

    # Reorder columns to put the important ones first
    first_cols = [
        "utility",
        "outage_id",
        "first_start_time",
        "first_est_restoration_time",
        "total_outage_length",
        "length_from_first_est_restoration",
        "largest_estimated_remaining_outage_length",
        "diff_actual_vs_first_est"
    ]
    other_cols = [col for col in summary.columns if col not in first_cols]
    summary = summary[first_cols + other_cols]


    # 4. Save the one-row-per-outage dataframe
    summary.to_csv(args.output, index=False)

    # 5. analyze recent outages to estimate the probability that we'll see an outage
    # with a large enough impact to be worth marketing to
    # start_date_utc=datetime.now(timezone.utc) - timedelta(days=60)
    both_thresholds = filter_to_high_impact_outages(summary, end_date_utc=datetime.now(timezone.utc), min_customers_impacted=1, min_estimated_remaining_outage_length=timedelta(hours=0), min_actual_outage_length=timedelta(hours=4))

    # Load population data for normalization
    population_data = load_wa_population_data()
    
    # Create zip code impact analysis and visualizations for the filtered outages
    if len(both_thresholds) > 0:
        create_zip_code_impact_analysis(both_thresholds, population_data, args.png_heatmap, args.html_heatmap)


     # if len(both_thresholds) > 0:
    #     print(f"\nOutages meeting both thresholds:")
    #     print("=" * 80)
    #     for _, outage in both_thresholds.iterrows():
    #         print(f"Outage ID: {outage['outage_id']}")
    #         print(f"  Start Time: {outage['first_start_time']}")
    #         print(f"  Max Customers Impacted: {outage['max_customers_impacted']}")
    #         print(f"  Largest Predicted Remaining Duration at any point: {outage['largest_estimated_remaining_outage_length']}")
    #         print(f"  Actual Duration: {outage['total_outage_length']}")
    #         print(f"  Zip Code: {outage['zip_code']}")
    #         print("-" * 40)
    # else:
    #     print("No outages meet both thresholds.")

    

    # 5. Create charts 
    # create_distribution_charts(summary)

    # 5.5. Create animated outage map
    # create_animated_outage_map(summary, animation_duration=30)

    # 5.6. Create cumulative polygon animation
    # create_cumulative_polygon_animation(summary, animation_duration=30)


if __name__ == "__main__":
    main()
