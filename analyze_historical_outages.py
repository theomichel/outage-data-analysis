import argparse
import pandas as pd
from datetime import datetime
from datetime import timedelta
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.animation as animation
import json
from matplotlib.patches import Circle
import matplotlib.dates as mdates
import contextily as ctx
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon
from datetime import timezone

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
    start_time = valid_outages['first_start_time_dt'].min()
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
            outage_start = outage['first_start_time_dt']
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
    start_time = valid_outages['first_start_time_dt'].min()
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
                             'start_time': outage['first_start_time_dt'],
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

# gives a text report of how many outages in the given date range meet the given thresholds
def analyze_recent_outage_impacts(summary, start_date_utc, end_date_utc=datetime.now(), min_customers_impacted=100, min_predicted_outage_length=timedelta(hours=6), min_actual_outage_length=timedelta(hours=1)):
    # filter summary to only include outages in the given date range
    summary = summary[(summary['first_start_time_dt'] >= start_date_utc) & (summary['first_start_time_dt'] <= end_date_utc)]


    # count the number of outages that meet the given thresholds
    num_outages = len(summary)
    print(f"Number of outages in the given date range: {num_outages}")
    print(f"Number of outages with at least {min_customers_impacted} customers impacted: {len(summary[summary['max_customers_impacted'] >= min_customers_impacted])}")
    print(f"Number of outages with at least {min_predicted_outage_length} hours of predicted outage length: {len(summary[summary['length_from_first_est_restoration'] >= min_predicted_outage_length])}")
    
    # Count outages that meet both thresholds
    both_thresholds = summary[
        (summary['max_customers_impacted'] >= min_customers_impacted) & 
        (summary['length_from_first_est_restoration'] >= min_predicted_outage_length) &
        (summary['total_outage_length'] >= min_predicted_outage_length)
    ]
    print(f"Number of outages meeting both thresholds: {len(both_thresholds)}")
    
    # Output details of outages that meet both thresholds
    if len(both_thresholds) > 0:
        print(f"\nOutages meeting both thresholds:")
        print("=" * 80)
        for _, outage in both_thresholds.iterrows():
            print(f"Outage ID: {outage['outage_id']}")
            print(f"  Start Time: {outage['first_start_time']}")
            print(f"  Max Customers Impacted: {outage['max_customers_impacted']}")
            print(f"  Predicted Duration: {outage['length_from_first_est_restoration']}")
            print(f"  Actual Duration: {outage['total_outage_length']}")
            print(f"  Difference (Actual - Predicted): {outage['diff_actual_vs_first_est']}")
            print("-" * 40)
    else:
        print("No outages meet both thresholds.")


def analyze_outage_impacts_by_area(summary):
    # TODO: implement
    pass

def main():
    parser = argparse.ArgumentParser(description="Analyze historical outages from multiple utilities.")
    parser.add_argument('-f', '--files', nargs='+', required=True,
                       help='Input CSV file(s) - can specify multiple files to combine')
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

    # Add file_datetime column
#    df['file_datetime'] = pd.to_datetime(df['file_datetime'], format="ISO8601") # %Y-%m-%dT%H%M%S%f
    df = df.sort_values(["outage_id", "file_datetime"])
    
    # Parse estimated restoration time to datetime, coercing invalid/empty to NaT
    df["est_restoration_dt"] = pd.to_datetime(df["est_restoration_time"], errors="coerce")

    # Find the earliest and latest update datetimes in the dataset
    min_file_datetime = df["file_datetime"].min()
    max_file_datetime = df["file_datetime"].max()

    # For each outage, get the first and last update datetimes
    first_last = df.groupby("outage_id")["file_datetime"].agg(["first", "last"])

    # Outages to exclude: those whose first update is at min or last update is at max
    to_exclude = first_last[(first_last["first"] == min_file_datetime) | (first_last["last"] == max_file_datetime)].index

    # Filter out these outages from the dataframe
    filtered_df = df[~df["outage_id"].isin(to_exclude)].copy()

    # Total number of unique outages (after filtering)
    total_outages = filtered_df["outage_id"].nunique()
    print(f"Total number of outages analyzed (excluding edge cases): {total_outages}")
    
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
    print(f"Outage IDs with polygon changes: {polygon_change_ids}")

    # 2. Outage Start Time changes
    start_time_changes = filtered_df.groupby("outage_id")["start_time"].agg(has_changes)
    start_time_change_ids = start_time_changes[start_time_changes].index.tolist()
    num_start_time_changes = len(start_time_change_ids)
    print(f"Number of outages with start time changes: {num_start_time_changes}")
    print(f"Outage IDs with start time changes: {start_time_change_ids}")

    # 3. Create dataframe with one row per outage

    # Ensure grouping preserves the sorted order above so first/last valid are chronological
    filtered_df = filtered_df.sort_values(["outage_id", "file_datetime"]) 

    summary = (
        filtered_df.groupby("outage_id", sort=False)
        .agg(
            first_start_time=("start_time", "first"),
            first_est_restoration_time_dt=("est_restoration_dt", first_valid),
            last_est_restoration_time_dt=("est_restoration_dt", last_valid),
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
    
    # Parse start time and estimated restoration times as datetimes for calculations
    summary["first_start_time_dt"] = pd.to_datetime(summary["first_start_time"], utc=True, format="%Y-%m-%d %H:%M:%S%z") #2025-02-27 20:49:32-08:00
    summary["last_file_datetime"] = pd.to_datetime(summary["last_file_datetime"], utc=True, format="%Y-%m-%d %H:%M:%S%z") #2025-02-27 20:49:32-08:00
    summary["first_est_restoration_time_dt"] = pd.to_datetime(summary["first_est_restoration_time_dt"], utc=True, format="%Y-%m-%d %H:%M:%S%z") #2025-02-27 20:49:32-08:00
    summary["last_est_restoration_time_dt"] = pd.to_datetime(summary["last_est_restoration_time_dt"], utc=True, format="%Y-%m-%d %H:%M:%S%z") #2025-02-27 20:49:32-08:00

    # calculate outage lengths
    print(f"last_file_datetime: {summary['last_file_datetime']}")
    print(f"first_start_time_dt: {summary['first_start_time_dt']}")
    summary["total_outage_length"] = summary["last_file_datetime"] - summary["first_start_time_dt"]
    summary["length_from_first_est_restoration"] = summary["first_est_restoration_time_dt"] - summary["first_start_time_dt"]
    summary["length_from_last_est_restoration"] = summary["last_est_restoration_time_dt"] - summary["first_start_time_dt"]

    # Calculate difference between actual outage length and length as estimated from first est restoration, formatted as HH:MM
    summary["diff_actual_vs_first_est"] = (summary["total_outage_length"] - summary["length_from_first_est_restoration"]).apply(format_timedelta_hhmm)

    # Reorder columns to put the important ones first
    first_cols = [
        "outage_id",
        "first_start_time",
        "first_est_restoration_time_dt",
        "total_outage_length",
        "length_from_first_est_restoration",
        "diff_actual_vs_first_est"
    ]
    other_cols = [col for col in summary.columns if col not in first_cols]
    summary = summary[first_cols + other_cols]


    # 4. Save the one-row-per-outage dataframe
    summary.to_csv("outage_summary.csv", index=False)

    # 5. Create charts 
    # create_distribution_charts(summary)

    # 5.5. Create animated outage map
    # create_animated_outage_map(summary, animation_duration=30)

    # 5.6. Create cumulative polygon animation
    # create_cumulative_polygon_animation(summary, animation_duration=30)

    # 6. analyze recent outages to estimate the probability that we'll see an outage
    # with a large enough impact to be worth marketing to
    analyze_recent_outage_impacts(summary, start_date_utc=datetime(2025, 7, 14, tzinfo=timezone.utc), end_date_utc=datetime(2025, 8, 15, tzinfo=timezone.utc), min_customers_impacted=100, min_predicted_outage_length=timedelta(hours=6), min_actual_outage_length=timedelta(hours=.5))




if __name__ == "__main__":
    main()
