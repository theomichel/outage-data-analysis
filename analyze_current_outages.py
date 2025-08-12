import pandas as pd
from datetime import datetime
import argparse
import json
import math

def calculate_expected_length_minutes(start_time, est_restoration_time):
    """
    Calculate the expected length of an outage in minutes.
    Returns the difference between estimated restoration time and start time.
    """
    try:
        if pd.isna(start_time) or pd.isna(est_restoration_time):
            return None
        
        # Convert to datetime if they're strings
        if isinstance(start_time, str):
            start_time = pd.to_datetime(start_time)
        if isinstance(est_restoration_time, str):
            est_restoration_time = pd.to_datetime(est_restoration_time)
        
        # Calculate difference in minutes
        time_diff = est_restoration_time - start_time
        return int(time_diff.total_seconds() / 60)
    except Exception as e:
        print(f"Error calculating expected length: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Analyze current PSE outages.")
    parser.add_argument('-f', '--file_input', type=str, default="outage_updates.csv", 
                       help='Input file name (default: outage_updates.csv)')
    parser.add_argument('-l', '--length_threshold', type=float, default=0.0, 
                       help='Expected length threshold in hours (default: 0.0)')
    parser.add_argument('-c', '--customer_threshold', type=int, default=0, 
                       help='Customers effected threshold  (default: 0)')
    args = parser.parse_args()
    
    # Convert threshold from hours to minutes
    threshold_minutes = args.length_threshold * 60
    
    # Load the outage data
    df = pd.read_csv(args.file_input)
    
    # Find the most recent snapshot time in the entire dataset
    max_update_time = df['snapshot_datetime'].max()
    
    # Filter to only include outages that have the most recent update time
    current_outages_df = df[df['snapshot_datetime'] == max_update_time].copy()
    
    # print out the snapshot time for vis
    print(f"using snapshot with timestamp {max_update_time}")
    
    # Calculate expected length in minutes for each outage
    current_outages_df['expected_length_minutes'] = current_outages_df.apply(
        lambda row: calculate_expected_length_minutes(row['start_time'], row['est_restoration_time']), 
        axis=1
    )
    
    # Filter outages that exceed the threshold
    filtered_outages = current_outages_df[current_outages_df['expected_length_minutes'] > threshold_minutes]
    filtered_outages = filtered_outages[filtered_outages['customers_impacted'] > args.customer_threshold]

    # Calculate total customers affected
    # Convert customers_impacted to numeric, handling any non-numeric values
#    filtered_outages['customers_impacted_numeric'] = pd.to_numeric(filtered_outages['customers_impacted'], errors='coerce')
    total_customers = filtered_outages['customers_impacted'].sum()
    
    # Create new dataframe with only the specified columns
    current_outages = filtered_outages[[
        'outage_id',
        'customers_impacted', 
        'start_time',
        'polygon_json',
        'center_lon',
        'center_lat',
        'radius',
        'expected_length_minutes'
    ]].copy()
    
    # Save to new CSV file
    current_outages.to_csv("current_outages.csv", index=False)
    print(f"Current outages analysis saved to current_outages.csv")
    print(f"Total outages: {len(current_outages)}")
    print(f"Total customers affected: {total_customers:.0f}")
    print(f"Threshold: {args.length_threshold} hours ({threshold_minutes} minutes)")
    print(f"Most recent update time: {max_update_time}")

if __name__ == "__main__":
    main()
    
    