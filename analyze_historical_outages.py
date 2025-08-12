import argparse
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

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

def main():
    parser = argparse.ArgumentParser(description="Analyze historical PSE outages.")
    parser.add_argument('-f', '--file_input', type=str, default="outage_updates.csv", 
                       help='Input file name (default: outage_updates.csv)')
    args = parser.parse_args()
    df = pd.read_csv(args.file_input)

    # Add file_datetime column
    df['snapshot_datetime'] = pd.to_datetime(df['file_datetime'])
    df = df.sort_values(["outage_id", "snapshot_datetime"])

    # Find the earliest and latest update datetimes in the dataset
    min_snapshot_datetime = df["snapshot_datetime"].min()
    max_snapshot_datetime = df["snapshot_datetime"].max()

    # For each outage, get the first and last update datetimes
    first_last = df.groupby("outage_id")["snapshot_datetime"].agg(["first", "last"])

    # Outages to exclude: those whose first update is at min or last update is at max
    to_exclude = first_last[(first_last["first"] == min_snapshot_datetime) | (first_last["last"] == max_snapshot_datetime)].index

    # Filter out these outages from the dataframe
    filtered_df = df[~df["outage_id"].isin(to_exclude)].copy()

    # Total number of unique outages (after filtering)
    total_outages = filtered_df["outage_id"].nunique()
    print(f"Total number of outages analyzed (excluding edge cases): {total_outages}")

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

    # 3. One Row Per Outage Summary
    summary = (
        filtered_df.groupby("outage_id")
        .agg(
            first_start_time=("start_time", "first"),
            first_est_restoration_time=("est_restoration_time", "first"),
            last_est_restoration_time=("est_restoration_time", "last"),
            first_snapshot_datetime=("snapshot_datetime", "first"),
            last_snapshot_datetime=("snapshot_datetime", "last"),
            last_polygon_json=("polygon_json", "last"),
            last_start_time=("start_time", "last"),
            max_customers_impacted=("customers_impacted", "max"),
        )
        .reset_index()
    )
    
    # Parse start time and estimated restoration times as datetimes for calculations
    summary["first_start_time_dt"] = pd.to_datetime(summary["first_start_time"])
    summary["first_est_restoration_dt"] = pd.to_datetime(summary["first_est_restoration_time"])
    summary["last_est_restoration_dt"] = pd.to_datetime(summary["last_est_restoration_time"])

    # do some calculations of outage lengths
    summary["total_outage_length"] = summary["last_snapshot_datetime"] - summary["first_start_time_dt"]
    summary["length_from_first_est_restoration"] = summary["first_est_restoration_dt"] - summary["first_start_time_dt"]
    summary["length_from_last_est_restoration"] = summary["last_est_restoration_dt"] - summary["first_start_time_dt"]

    # Calculate difference between actual outage length and length as estimated from first est restoration, formatted as HH:MM
    summary["diff_actual_vs_first_est"] = (summary["total_outage_length"] - summary["length_from_first_est_restoration"]).apply(format_timedelta_hhmm)

    # Reorder columns to put the important ones first
    first_cols = [
        "outage_id",
        "first_start_time",
        "first_est_restoration_time",
        "total_outage_length",
        "length_from_first_est_restoration",
        "diff_actual_vs_first_est"
    ]
    other_cols = [col for col in summary.columns if col not in first_cols]
    summary = summary[first_cols + other_cols]

    summary.to_csv("outage_summary.csv", index=False)

    # Create chart showing distribution of total_outage_length values
    plt.figure(figsize=(12, 8))
    
    # Convert total_outage_length to hours for better visualization
    outage_lengths_hours = summary['total_outage_length'].dt.total_seconds() / 3600
    
    # Create histogram
    plt.hist(outage_lengths_hours, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
    plt.xlabel('Total Outage Length (hours)')
    plt.ylabel('Number of Outages')
    plt.title('Distribution of Total Outage Lengths')
    plt.grid(True, alpha=0.3)
    
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
    plt.show()
    
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
    plt.show()
    
    print(f"\nCustomers impacted statistics:")
    print(f"Mean: {mean_customers:.0f} customers")
    print(f"Median: {median_customers:.0f} customers")
    print(f"Standard deviation: {std_customers:.0f} customers")
    print(f"Chart saved as 'customers_impacted_distribution.png'")

if __name__ == "__main__":
    main()
