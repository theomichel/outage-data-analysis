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
        print(f"Error calculating expected length: {e}")
        return None

def calculate_active_duration_minutes(start_time, current_time):
    """
    Calculate how long an outage has been active in minutes.
    Returns the difference between current time and start time.
    """
    try:        
        print(f"start_time: {start_time}")
        print(f"current_time: {current_time}")
        # Convert to datetime if it's a string
        start_time = pd.to_datetime(start_time)
        current_time = pd.to_datetime(current_time)
        
        # Calculate difference in minutes
        time_diff = current_time - start_time
        return int(time_diff.total_seconds() / 60)
    except Exception as e:
        print(f"Error calculating active duration: {e}")
        return None

def send_telegram_message(token, chat_id, message, thread_id=None):
    """Sends a message to a specified Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message
    }
    if thread_id:
        params["message_thread_id"] = thread_id
    try:
        response = requests.post(url, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        print("Telegram message sent successfully!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
        return False

def send_notification(notification_data, file_input, thresholds, bot_token=None, chat_id=None, thread_id=None):
    """
    Send Telegram notification about outages that meet the threshold criteria.
    notification_data contains: new_outages, resolved_outages, new_customers, resolved_customers
    """
    try:
        new_outages = notification_data['new_outages']
        resolved_outages = notification_data['resolved_outages']
        new_customers = notification_data['new_customers']
        resolved_customers = notification_data['resolved_customers']
        
        messages_to_send = []
        
        # Create separate notification for new outages
        if not new_outages.empty:
            new_message = f"🚨 **NEW OUTAGE ALERT**\n\n"
            new_message += f"📈 **{len(new_outages)} new outage(s) detected**\n"
            new_message += f"👥 **{new_customers:,.0f} customers affected**\n\n"
            
            # Add details for each new outage
            for i, (_, outage) in enumerate(new_outages.iterrows()):
                if i >= 10:  # Limit to first 10 outages to avoid message length issues
                    new_message += f"... and {len(new_outages) - 10} more outages\n"
                    break
                
                print(f"outage: {outage}")

                elapsed_hours = outage['elapsed_time_minutes'] / 60
                
                new_message += f"🔴 **{outage['outage_id']}**\n"
                new_message += f"  👥 {outage['customers_impacted']:,.0f} customers\n"
                new_message += f"  ⏱️ {elapsed_hours:.1f}h elapsed\n"
                new_message += f"  📍 Status: {outage['status']}\n"
                new_message += f"  ⚠️ Cause: {outage['cause']}\n"
                
                # Add location if available
                if pd.notna(outage['center_lat']) and pd.notna(outage['center_lon']):
                    maps_url = f"https://maps.google.com/maps?q={outage['center_lat']:.6f},{outage['center_lon']:.6f}"
                    new_message += f"  🗺️ Location: [{outage['center_lat']:.4f}, {outage['center_lon']:.4f}]({maps_url})\n"
                
                new_message += "\n"
            
            new_message += f"🕐 Alert generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            messages_to_send.append(('new', new_message))

        # Create separate notification for resolved outages  
        if not resolved_outages.empty:
            resolved_message = f"✅ **OUTAGE RESOLVED ALERT**\n\n"
            resolved_message += f"📉 **{len(resolved_outages)} outage(s) resolved**\n"
            resolved_message += f"👥 **{resolved_customers:,.0f} customers restored**\n\n"
            
            # Add details for each resolved outage
            for i, (_, outage) in enumerate(resolved_outages.iterrows()):
                if i >= 10:  # Limit to first 10 outages
                    resolved_message += f"... and {len(resolved_outages) - 10} more outages\n"
                    break
                    
                resolved_message += f"✅ **{outage['outage_id']}**\n"
                resolved_message += f"  👥 {outage['customers_impacted']:,.0f} customers restored\n"
                resolved_message += f"  📍 Last status: {outage['status']}\n"
                resolved_message += f"  ⚠️ Cause: {outage['cause']}\n"
                
                # Add location if available
                if pd.notna(outage['center_lat']) and pd.notna(outage['center_lon']):
                    maps_url = f"https://maps.google.com/maps?q={outage['center_lat']:.6f},{outage['center_lon']:.6f}"
                    resolved_message += f"  🗺️ Location: [{outage['center_lat']:.4f}, {outage['center_lon']:.4f}]({maps_url})\n"
                
                resolved_message += "\n"
            
            resolved_message += f"🕐 Alert generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            messages_to_send.append(('resolved', resolved_message))
        
        # Send each message separately
        for msg_type, message in messages_to_send:
            # Send Telegram notification if credentials provided
            if bot_token and chat_id:
                success = send_telegram_message(bot_token, chat_id, message, thread_id)
                if success:
                    print(f"Telegram {msg_type} outage notification sent to chat {chat_id}" + (f" (thread {thread_id})" if thread_id else ""))
                else:
                    print(f"Failed to send Telegram {msg_type} outage notification")
            else:
                print("Telegram credentials not provided, skipping notification")
                
            # Save notification to timestamped file
            notification_filename = f"notification_{msg_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(notification_filename, 'w') as f:
                f.write(message)
            print(f"{msg_type.capitalize()} outage notification saved to: {notification_filename}")
        
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
    args = parser.parse_args()
    
    print(f"====== analyze_current_outages.py starting for utility {args.utility} =======")

    # Convert thresholds from hours to minutes
    threshold_minutes = args.length_threshold * 60
    elapsed_time_threshold_minutes = args.elapsed_time_threshold * 60
    
    # Load the outage data
    df = pd.read_csv(args.file_input)
    
    # Find the two most recent snapshot times
    unique_timestamps = sorted(df['file_datetime'].unique(), reverse=True)
    
    if len(unique_timestamps) >= 2:
        latest_time = unique_timestamps[0]
        previous_time = unique_timestamps[1]
        print(f"Latest snapshot: {latest_time}")
        print(f"Previous snapshot: {previous_time}")
        
        # Split data into latest and previous snapshots
        latest_outages_df = df[df['file_datetime'] == latest_time].copy()
        previous_outages_df = df[df['file_datetime'] == previous_time].copy()
        
    elif len(unique_timestamps) == 1:
        latest_time = unique_timestamps[0]
        previous_time = None
        print(f"Only one snapshot available: {latest_time}")
        
        # Only latest data available
        latest_outages_df = df[df['file_datetime'] == latest_time].copy()
        previous_outages_df = pd.DataFrame()  # Empty dataframe
        
    else:
        print("No snapshot data found")
        return
    
    # Process latest outages (new outages logic)
    if not latest_outages_df.empty:
        # Calculate expected length in minutes for latest outages
        latest_outages_df['expected_length_minutes'] = latest_outages_df.apply(
            lambda row: calculate_expected_length_minutes(row['start_time'], row['est_restoration_time']), 
            axis=1
        )
        
        # Calculate active duration in minutes for latest outages
        latest_outages_df['elapsed_time_minutes'] = latest_outages_df.apply(
            lambda row: calculate_active_duration_minutes(row['start_time'], latest_time), 
            axis=1
        )
        
        print(f"latest_outages_df: {latest_outages_df}")

        # Filter latest outages that exceed the thresholds
        significant_latest = latest_outages_df[latest_outages_df['expected_length_minutes'] > threshold_minutes]
        significant_latest = significant_latest[significant_latest['customers_impacted'] > args.customer_threshold]
        significant_latest = significant_latest[significant_latest['elapsed_time_minutes'] > elapsed_time_threshold_minutes]
        
        print(f"significant_latest: {significant_latest}")

        # Only alert on truly NEW outages (not present in previous snapshot)
        if not previous_outages_df.empty:
            previous_outage_ids = set(previous_outages_df['outage_id'].unique())
            latest_outage_ids = set(significant_latest['outage_id'].unique())
            truly_new_outage_ids = latest_outage_ids - previous_outage_ids
            
            if truly_new_outage_ids:
                new_outages = significant_latest[significant_latest['outage_id'].isin(truly_new_outage_ids)].copy()
                print(f"Found {len(new_outages)} truly new outages (not in previous snapshot)")
            else:
                new_outages = pd.DataFrame()
                print("No truly new outages found")
        else:
            # No previous snapshot, so all significant outages are "new"
            new_outages = significant_latest
            print(f"Found {len(new_outages)} outages (no previous snapshot for comparison)")
    else:
        new_outages = pd.DataFrame()
    
    # Process resolved outages (in previous but not in latest)
    resolved_outages = pd.DataFrame()
    if not previous_outages_df.empty and not latest_outages_df.empty:
        # First, filter previous outages using the same thresholds
        # Calculate expected length and elapsed time for previous outages
        previous_outages_df['expected_length_minutes'] = previous_outages_df.apply(
            lambda row: calculate_expected_length_minutes(row['start_time'], row['est_restoration_time']), 
            axis=1
        )
        previous_outages_df['elapsed_time_minutes'] = previous_outages_df.apply(
            lambda row: calculate_active_duration_minutes(row['start_time'], previous_time), 
            axis=1
        )
        
        # Filter previous outages that would have met our alert thresholds
        significant_previous = previous_outages_df[previous_outages_df['expected_length_minutes'] > threshold_minutes]
        significant_previous = significant_previous[significant_previous['customers_impacted'] > args.customer_threshold]
        significant_previous = significant_previous[significant_previous['elapsed_time_minutes'] > elapsed_time_threshold_minutes]
        
        # Find significant outages that were in previous snapshot but not in latest
        previous_outage_ids = set(significant_previous['outage_id'].unique())
        latest_outage_ids = set(latest_outages_df['outage_id'].unique())
        resolved_outage_ids = previous_outage_ids - latest_outage_ids
        
        if resolved_outage_ids:
            resolved_outages = significant_previous[significant_previous['outage_id'].isin(resolved_outage_ids)].copy()
            print(f"Found {len(resolved_outages)} resolved outages that met alert thresholds")
        else:
            print("No significant resolved outages found")
    
    # Combine results for reporting (use new_outages for backward compatibility)
    filtered_outages = new_outages

    # Calculate total customers affected
    if not filtered_outages.empty:
        total_customers = filtered_outages['customers_impacted'].sum()
    else:
        total_customers = 0
    
    # Create new dataframe with only the specified columns
    if not filtered_outages.empty:
        current_outages = filtered_outages[[
            'outage_id',
            'customers_impacted', 
            'start_time',
            'expected_length_minutes',
            'elapsed_time_minutes',
            'status',
            'cause',
            'center_lon',
            'center_lat',
            'radius',
            'polygon_json',
        ]].copy()
    else:
        # Create empty dataframe with correct columns
        current_outages = pd.DataFrame(columns=[
            'outage_id',
            'customers_impacted', 
            'start_time',
            'expected_length_minutes',
            'elapsed_time_minutes',
            'status',
            'cause',
            'center_lon',
            'center_lat',
            'radius',
            'polygon_json',
        ])
    
    # Save to new CSV file
    current_outages.to_csv(f"{args.utility}_current_outages_analysis.csv", index=False)
    print(f"Current outages analysis saved to {args.utility}_current_outages.csv")
    print(f"New outages meeting criteria: {len(current_outages)}")
    print(f"Total customers affected by new outages: {total_customers:.0f}")
    if not resolved_outages.empty:
        resolved_customers = resolved_outages['customers_impacted'].sum()
        print(f"Resolved outages: {len(resolved_outages)}")
        print(f"Total customers restored: {resolved_customers:.0f}")
    print(f"Expected length threshold: {args.length_threshold} hours ({threshold_minutes} minutes)")
    print(f"Customer threshold: {args.customer_threshold}")
    print(f"Elapsed time threshold: {args.elapsed_time_threshold} hours ({elapsed_time_threshold_minutes} minutes)")
    print(f"Latest update time: {latest_time}")
    if previous_time:
        print(f"Previous update time: {previous_time}")
    
    if(len(current_outages) > 0):
        print("WE HAVE OUTAGES!!!")

    # Send notification if there are new outages or resolved outages
    if len(current_outages) > 0 or len(resolved_outages) > 0:
        thresholds = {
            'length': args.length_threshold,
            'customers': args.customer_threshold,
            'elapsed': args.elapsed_time_threshold
        }
        # Pass both new and resolved outages to notification
        notification_data = {
            'new_outages': current_outages,
            'resolved_outages': resolved_outages,
            'new_customers': total_customers,
            'resolved_customers': resolved_outages['customers_impacted'].sum() if not resolved_outages.empty else 0
        }
        send_notification(notification_data, args.file_input, thresholds, args.telegram_token, args.telegram_chat_id, args.telegram_thread_id)

    print(f"====== analyze_current_outages.py completed =======")

if __name__ == "__main__":
    main()
    
    