import pandas as pd
from datetime import datetime
import argparse
import json
import math
import requests
import os

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
        print(f"Error calculating expected length: {e.message}")
        return None

def calculate_active_duration_minutes(start_time, current_time):
    """
    Calculate how long an outage has been active in minutes.
    Returns the difference between current time and start time.
    """
    try:        
        print(f"Calculating active duration from start_time: {start_time} and current_time: {current_time}")
        # Convert to datetime if it's a string
        start_time = pd.to_datetime(start_time)
        current_time = pd.to_datetime(current_time)
        
        # Calculate difference in minutes
        time_diff = current_time - start_time
        return int(time_diff.total_seconds() / 60)
    except Exception as e:
        print(f"Error calculating active duration: {e}")
        return None

def reverse_geocode(lat, lon, api_key=None):
    """Reverse geocode coordinates to get formatted location information."""

    # State abbreviation lookup table (lowercase for case-insensitive comparison)
    STATE_ABBREVIATIONS = {
        "alabama": "AL",
        "alaska": "AK",
        "arizona": "AZ",
        "arkansas": "AR",
        "california": "CA",
        "colorado": "CO",
        "connecticut": "CT",
        "delaware": "DE",
        "florida": "FL",
        "georgia": "GA",
        "hawaii": "HI",
        "idaho": "ID",
        "illinois": "IL",
        "indiana": "IN",
        "iowa": "IA",
        "kansas": "KS",
        "kentucky": "KY",
        "louisiana": "LA",
        "maine": "ME",
        "maryland": "MD",
        "massachusetts": "MA",
        "michigan": "MI",
        "minnesota": "MN",
        "mississippi": "MS",
        "missouri": "MO",
        "montana": "MT",
        "nebraska": "NE",
        "nevada": "NV",
        "new hampshire": "NH",
        "new jersey": "NJ",
        "new mexico": "NM",
        "new york": "NY",
        "north carolina": "NC",
        "north dakota": "ND",
        "ohio": "OH",
        "oklahoma": "OK",
        "oregon": "OR",
        "pennsylvania": "PA",
        "rhode island": "RI",
        "south carolina": "SC",
        "south dakota": "SD",
        "tennessee": "TN",
        "texas": "TX",
        "utah": "UT",
        "vermont": "VT",
        "virginia": "VA",
        "washington": "WA",
        "west virginia": "WV",
        "wisconsin": "WI",
        "wyoming": "WY",
        "district of columbia": "DC",
        "american samoa": "AS",
        "guam": "GU",
        "northern mariana islands": "MP",
        "puerto rico": "PR",
        "u.s. virgin islands": "VI"
    }

    # Create Google Maps URL
    maps_url = f"https://maps.google.com/maps?q={lat:.6f},{lon:.6f}"

    try:
        if api_key:
            url = f"https://geocode.maps.co/reverse?lat={lat}&lon={lon}&api_key={api_key}"
        else:
            # Fallback to google URL if no API key provided
            return maps_url

        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        address = data.get('address', {})
        
        suburb = address.get('suburb', '')
        city = address.get('city', '') or address.get('town', '')
        state = address.get('state', '')
        
        # Convert state to abbreviation if available (case-insensitive)
        state_abbr = STATE_ABBREVIATIONS[state.lower()] if state else ''
  
        # Format location information
        if suburb and city and state_abbr:
            location_info = f"[{suburb}, {city}, {state_abbr}]({maps_url})"
        elif city and state_abbr:
            location_info = f"[{city}, {state_abbr}]({maps_url})"
        elif state_abbr:
            location_info = f"[{state_abbr}]({maps_url})"
        else:
            location_info = maps_url
        
        return location_info
    except Exception as e:
        print(f"Error reverse geocoding coordinates {lat}, {lon}: {e}")
        # Fallback to just the Google Maps URL
        return maps_url

def send_telegram_message(token, chat_id, message, thread_id=None):
    """Sends a message to a specified Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "link_preview_options": {
            "is_disabled": True
        },
        "parse_mode": "Markdown"
    }

    if thread_id:
        data["message_thread_id"] = thread_id
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Raise an exception for HTTP errors
        print("Telegram message sent successfully!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
        return False

def send_notification(notification_data, file_input, thresholds, bot_token=None, chat_id=None, thread_id=None, geocode_api_key=None):
    """
    Send Telegram notification about outages that meet the threshold criteria.
    notification_data contains: new_outages, resolved_outages, new_customers, resolved_customers
    """
    try:
        new_outages = notification_data['new_outages']
        resolved_outages = notification_data['resolved_outages']
        messages_to_send = []
        
        # Create individual notification for each new outage
        if not new_outages.empty:
            for _, outage in new_outages.iterrows():
                
                elapsed_hours = outage['elapsed_time_minutes'] / 60
                
                new_message = f"🚨 NEW OUTAGE ALERT 🚨\n\n"
                new_message += f"Utility: {outage['utility'].upper()}\n"
                new_message += f"ID: {outage['outage_id']}\n"
                new_message += f"Customers: {outage['customers_impacted']:,.0f} \n"
                new_message += f"Current Duration: {elapsed_hours:.1f}h \n"
                
                # Add estimated duration if available
                if pd.notna(outage['expected_length_minutes']) and outage['expected_length_minutes'] is not None:
                    expected_hours = outage['expected_length_minutes'] / 60
                    new_message += f"Expected Duration: {expected_hours:.1f}h \n"
                
                new_message += f"Status: {outage['status']}\n"
                new_message += f"Cause: {outage['cause']}\n"
                
                # Add location if available
                if pd.notna(outage['center_lat']) and pd.notna(outage['center_lon']):
                    location_info = reverse_geocode(outage['center_lat'], outage['center_lon'], geocode_api_key)
                    new_message += f"Location: {location_info}\n"
                
                messages_to_send.append(('new', new_message, outage['outage_id']))

        # Create individual notification for each resolved outage  
        if not resolved_outages.empty:
            for _, outage in resolved_outages.iterrows():
                resolved_message = f"😌 RESOLVED OUTAGE ALERT 😌\n\n"
                resolved_message += f"Utility: {outage['utility'].upper()}\n"
                resolved_message += f"ID: {outage['outage_id']}\n"
                resolved_message += f"Customers: {outage['customers_impacted']:,.0f}\n"
                
                # Add actual duration if available
                if pd.notna(outage['elapsed_time_minutes']) and outage['elapsed_time_minutes'] is not None:
                    actual_hours = outage['elapsed_time_minutes'] / 60
                    resolved_message += f"Actual Duration: {actual_hours:.1f}h\n"
                
                # Add location if available
                if pd.notna(outage['center_lat']) and pd.notna(outage['center_lon']):
                    location_info = reverse_geocode(outage['center_lat'], outage['center_lon'], geocode_api_key)
                    resolved_message += f"Location: {location_info}\n"
                
                messages_to_send.append(('resolved', resolved_message, outage['outage_id']))
        
        # Send each message separately
        for msg_type, message, outage_id in messages_to_send:
            # Send Telegram notification if credentials provided
            if bot_token and chat_id:
                success = send_telegram_message(bot_token, chat_id, message, thread_id)
                if success:
                    print(f"Telegram {msg_type} outage notification sent for {outage_id} to chat {chat_id}" + (f" (thread {thread_id})" if thread_id else ""))
                else:
                    print(f"Failed to send Telegram {msg_type} outage notification for {outage_id}")
            else:
                print(f"Telegram credentials not provided, skipping {msg_type} notification for {outage_id}")
                
            # Save notification to timestamped file with outage ID
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            notification_filename = f"notification_{msg_type}_{outage_id}_{timestamp}.txt"
            with open(notification_filename, 'w', encoding="utf-8") as f:
                f.write(message)
            print(f"{msg_type.capitalize()} outage notification for {outage_id} saved to: {notification_filename}")
        
        if not messages_to_send:
            print("No outages meeting criteria - no notification sent.")
            
    except Exception as e:
        print(f"Error sending notification: {e}")

def main():
    parser = argparse.ArgumentParser(description="Analyze current PSE outages.")
    parser.add_argument('-f', '--file_input', type=str, default="outage_updates.csv", 
                       help='Input file name (default: outage_updates.csv)')
    parser.add_argument('-l', '--length_threshold', type=float, default=0.0, 
                       help='Expected length threshold in hours (default: 0.0)')
    parser.add_argument('-c', '--customer_threshold', type=int, default=0, 
                       help='Customers affected threshold  (default: 0)')
    parser.add_argument('-e', '--elapsed_time_threshold', type=float, default=0.0, 
                       help='Minimum elapsed time threshold in hours (default: 0.0)')
    parser.add_argument('-u', '--utility', type=str, required=True,
                       help='utility, for now only used in output file naming')
    parser.add_argument('--telegram-token', type=str,
                       help='Telegram bot token for notifications')
    parser.add_argument('--telegram-chat-id', type=str,
                       help='Telegram chat ID for notifications')
    parser.add_argument('--telegram-thread-id', type=str,
                       help='Telegram thread ID for notifications (optional)')
    parser.add_argument('--geocode-api-key', type=str,
                       help='API key for geocoding service (optional)')
    args = parser.parse_args()
    
    print(f"====== analyze_current_outages.py starting for utility {args.utility} =======")


    # Convert thresholds from hours to minutes
    expected_length_threshold_minutes = args.length_threshold * 60
    elapsed_time_threshold_minutes = args.elapsed_time_threshold * 60

    print(f"Expected length threshold: {args.length_threshold} hours ({expected_length_threshold_minutes} minutes)")
    print(f"Customer threshold: {args.customer_threshold}")
    print(f"Elapsed time threshold: {args.elapsed_time_threshold} hours ({elapsed_time_threshold_minutes} minutes)")


    # Load the outage data
    df = pd.read_csv(args.file_input)
    
    # Find the two most recent snapshot times
    unique_timestamps = sorted(df['file_datetime'].unique(), reverse=True)
    
    if len(unique_timestamps) >= 2:
        latest_update_time = unique_timestamps[0]
        previous_update_time = unique_timestamps[1]
        print(f"Latest snapshot: {latest_update_time}")
        print(f"Previous snapshot: {previous_update_time}")
        
        # Split data into latest and previous snapshots
        latest_outages_df = df[df['file_datetime'] == latest_update_time].copy()
        previous_outages_df = df[df['file_datetime'] == previous_update_time].copy()
        
    elif len(unique_timestamps) == 1:
        latest_update_time = unique_timestamps[0]
        print(f"Only one snapshot available: {latest_update_time}")
        
        # Check if isFromMostRecent column exists and all rows have the same value for that column
        if 'isFromMostRecent' in df.columns:
            is_from_most_recent_values = df['isFromMostRecent'].unique()
            print(f"isFromMostRecent values found: {is_from_most_recent_values}")
            
            if len(is_from_most_recent_values) == 1:
                is_from_most_recent = is_from_most_recent_values[0]
                print(f"All rows have isFromMostRecent = {is_from_most_recent}")
                
                if is_from_most_recent:
                    # All rows are from the most recent file
                    previous_update_time = None
                    latest_update_time = unique_timestamps[0]
                    latest_outages_df = df[df['file_datetime'] == latest_update_time].copy()
                    previous_outages_df = pd.DataFrame()  # Empty dataframe
                else:
                    # All rows are from the previous file
                    previous_update_time = unique_timestamps[0]
                    latest_update_time = None
                    latest_outages_df = pd.DataFrame()  # Empty dataframe
                    previous_outages_df = df[df['file_datetime'] == previous_update_time].copy()
            else:
                # Mixed values - this shouldn't happen with single timestamp
                assert False, f"Mixed isFromMostRecent values ({is_from_most_recent_values}) found with single timestamp"
        else:
            # No isFromMostRecent column - fall back to original behavior
            print("No isFromMostRecent column found, treating as latest data")
            latest_outages_df = df[df['file_datetime'] == latest_update_time].copy()
            previous_outages_df = pd.DataFrame()  # Empty dataframe
        
    else:
        print("No snapshot data found")
        return
    
    # do some length calculations on our dataframes of new and previous outages
    if not latest_outages_df.empty:
        # Calculate expected length in minutes for latest outages
        latest_outages_df['expected_length_minutes_latest'] = latest_outages_df.apply(
            lambda row: calculate_expected_length_minutes(latest_update_time, row['est_restoration_time']), 
            axis=1
        )
        
        # Calculate active duration in minutes for latest outages
        latest_outages_df['elapsed_time_minutes_latest'] = latest_outages_df.apply(
            lambda row: calculate_active_duration_minutes(row['start_time'], latest_update_time), 
            axis=1
        )

    if not previous_outages_df.empty:
        # Calculate expected length in minutes for previous outages
        previous_outages_df['expected_length_minutes_previous'] = previous_outages_df.apply(
            lambda row: calculate_expected_length_minutes(previous_update_time, row['est_restoration_time']), 
            axis=1
        )
        
        # Calculate active duration in minutes for previous outages
        previous_outages_df['elapsed_time_minutes_previous'] = previous_outages_df.apply(
            lambda row: calculate_active_duration_minutes(row['start_time'], previous_update_time), 
            axis=1
        )

    new_outages = pd.DataFrame()
    if not latest_outages_df.empty:
        # If previous_outages_df is empty, create a placeholder DataFrame with the required columns
        # so that the join (merge) doesn't fail
        if previous_outages_df.empty:
            previous_outages_df = pd.DataFrame(columns=['outage_id', 'expected_length_minutes_previous', 'elapsed_time_minutes_previous', 'customers_impacted'])

        # join the latest_outages_df with the previous_outages_df on outage_id,
        # bringing in the est_restoration_time and duration_minutes from the previous_outages_df
        latest_outages_df = latest_outages_df.merge(previous_outages_df[['outage_id', 'expected_length_minutes_previous', 'elapsed_time_minutes_previous', "customers_impacted"]], on='outage_id', how='left', suffixes=('_latest', '_previous'))

        # a "new" outage is one that has elapsed time > threshold and expected length > threshold, 
        # and either is not in the previous, or didn't meet one of those conditions in the previous
        new_outages = latest_outages_df[
            # the latest snapshot meets all the thresholds
            (latest_outages_df['expected_length_minutes_latest'] > expected_length_threshold_minutes) &
            (latest_outages_df['customers_impacted_latest'] > args.customer_threshold) &
            (latest_outages_df['elapsed_time_minutes_latest'] > elapsed_time_threshold_minutes) &
            # the previous snapshot missed on at least one threshold
            ((pd.isna(latest_outages_df['expected_length_minutes_previous']) | (latest_outages_df['expected_length_minutes_previous'] <= expected_length_threshold_minutes)) |
            (pd.isna(latest_outages_df['customers_impacted_previous']) | (latest_outages_df['customers_impacted_previous'] <= args.customer_threshold)) |
            (pd.isna(latest_outages_df['elapsed_time_minutes_previous']) | (latest_outages_df['elapsed_time_minutes_previous'] <= elapsed_time_threshold_minutes)))
        ]
        
    # Process resolved outages (in previous but not in latest)
    resolved_outages = pd.DataFrame()
    if not previous_outages_df.empty:
        # Filter previous outages that would have met our alert thresholds
        significant_previous = previous_outages_df[
            (previous_outages_df['expected_length_minutes_previous'] > expected_length_threshold_minutes) &
            (previous_outages_df['customers_impacted'] > args.customer_threshold) &
            (previous_outages_df['elapsed_time_minutes_previous'] > elapsed_time_threshold_minutes)
        ]
        
        # Find significant outages that were in previous snapshot but not in latest
        previous_outage_ids = set(significant_previous['outage_id'].unique())
        if(not latest_outages_df.empty):
            latest_outage_ids = set(latest_outages_df['outage_id'].unique())
            resolved_outage_ids = previous_outage_ids - latest_outage_ids
        else:
            resolved_outage_ids = previous_outage_ids
        
        if resolved_outage_ids:
            resolved_outages = significant_previous[significant_previous['outage_id'].isin(resolved_outage_ids)].copy()
            print(f"Found {len(resolved_outages)} resolved outages that met alert thresholds")
        else:
            print("No significant resolved outages found")
    
  
    # Select and rename columns in new_outages dataframe
    if not new_outages.empty:
        # Rename columns to remove _latest suffix
        new_outages = new_outages.rename(columns={
            'customers_impacted_latest': 'customers_impacted',
            'expected_length_minutes_latest': 'expected_length_minutes',
            'elapsed_time_minutes_latest': 'elapsed_time_minutes'
        })

    if not resolved_outages.empty:
        resolved_outages = resolved_outages.rename(columns={
            'customers_impacted_previous': 'customers_impacted',
            'expected_length_minutes_previous': 'expected_length_minutes',
            'elapsed_time_minutes_previous': 'elapsed_time_minutes'
        })



    # Save to new CSV file
    output_file = f"{args.utility}_current_outages_analysis.csv"
    new_outages.to_csv(output_file, index=False)
    print(f"Current outages analysis saved to {output_file}")
    print(f"New outages meeting criteria: {len(new_outages)}")
    if not resolved_outages.empty:
        print(f"Resolved outages: {len(resolved_outages)}")
    
    # Send notification if there are new outages or resolved outages
    if len(new_outages) > 0 or len(resolved_outages) > 0:
        thresholds = {
            'length': args.length_threshold,
            'customers': args.customer_threshold,
            'elapsed': args.elapsed_time_threshold
        }
        # Pass both new and resolved outages to notification logic
        notification_data = {
            'new_outages': new_outages,
            'resolved_outages': resolved_outages
        }
        send_notification(notification_data, args.file_input, thresholds, args.telegram_token, args.telegram_chat_id, args.telegram_thread_id, args.geocode_api_key)

    print(f"====== analyze_current_outages.py completed =======")

if __name__ == "__main__":
    main()
    
    