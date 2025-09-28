import pandas as pd
from datetime import datetime
import argparse
import json
import math
import requests
import os
import sys
import outage_utils
import glob
import zip_utils
import pytz

def get_utility_display_name(utility):
    if utility == "pge":
        return "PG&E"
    else:
        return utility.upper()

def escape_markdown(text):
    """Escape special Markdown characters to prevent parsing issues."""
    if pd.isna(text) or text is None:
        return ""
    
    # Convert to string and escape special Markdown characters
    text = str(text)
    # Escape backticks, asterisks, underscores, brackets, parentheses, and other special chars
    text = text.replace('\\', '\\\\')  # Escape backslashes first
    text = text.replace('`', '\\`')    # Escape backticks
    text = text.replace('*', '\\*')    # Escape asterisks
    text = text.replace('_', '\\_')    # Escape underscores
    
    return text

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
        
        # Check for HTTP errors and log detailed response for 400 errors
        if response.status_code == 400:
            print(f"HTTP 400 Bad Request from Telegram API:")
            print(f"  URL: {url}")
            print(f"  Chat ID: {chat_id}")
            print(f"  Thread ID: {thread_id}")
            print(f"  Message length: {len(message)} characters")
            print(f"  Message preview (first 200 chars): {message[:200]}...")
            print(f"  Request data: {data}")
            print(f"  Response status: {response.status_code}")
            print(f"  Response headers: {dict(response.headers)}")
            print(f"  Response body: {response.text}")
            
            # Try to parse the error response for more details
            try:
                error_data = response.json()
                if 'description' in error_data:
                    print(f"  Error description: {error_data['description']}")
                if 'error_code' in error_data:
                    print(f"  Error code: {error_data['error_code']}")
                if 'parameters' in error_data:
                    print(f"  Error parameters: {error_data['parameters']}")
                
                # Check for common Telegram API errors
                description = error_data.get('description', '').lower()
                if 'message is too long' in description:
                    print(f"  → Message exceeds Telegram's 4096 character limit")
                elif 'bad request: chat not found' in description:
                    print(f"  → Chat ID {chat_id} not found or bot not added to chat")
                elif 'bad request: message thread not found' in description:
                    print(f"  → Thread ID {thread_id} not found in chat {chat_id}")
                elif 'bad request: parse entities' in description:
                    print(f"  → Markdown parsing error in message content")
                elif 'bad request: message to edit not found' in description:
                    print(f"  → Message to edit not found")
                elif 'forbidden' in description:
                    print(f"  → Bot doesn't have permission to send messages to this chat")
                    
            except:
                print(f"  Could not parse error response as JSON")
            
            return False
        
        # For other HTTP errors, log basic info
        elif not response.ok:
            print(f"HTTP {response.status_code} error from Telegram API:")
            print(f"  Response: {response.text}")
            return False
        
        response.raise_for_status()  # This shouldn't trigger now, but keeping for safety
        print("Telegram message sent successfully!")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Network error sending Telegram message: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error sending Telegram message: {e}")
        return False

def send_notification(notification_data, thresholds, bot_token=None, chat_id=None, thread_id=None, geocode_api_key=None, notification_output_dir="."):
    """
    Send Telegram notification about outages that meet the threshold criteria.
    notification_data contains: new_outages, resolved_outages, new_customers, resolved_customers
    """
    try:
        new_outages = notification_data['new_outages']
        resolved_outages = notification_data['resolved_outages']
        active_outages = notification_data['active_outages']
        messages_to_send = []
        current_time = datetime.now(pytz.timezone('GMT'))
        
        # Create individual notification for each new outage
        if not new_outages.empty:
            for _, outage in new_outages.iterrows():
                
                elapsed_hours = outage['elapsed_time_minutes'] / 60
                
                new_message = f"🚨 NEW OUTAGE 🚨\n\n"
                new_message += f"Utility/ID: {get_utility_display_name(outage['utility'])} / {outage['outage_id']}\n"
                new_message += f"Customers: {outage['customers_impacted']:,.0f} \n"
                
                # Add estimated duration if available
                if pd.notna(outage['expected_length_minutes']) and outage['expected_length_minutes'] is not None:
                    expected_hours_string = f"{outage['expected_length_minutes'] / 60:.1f}h"
                else:
                    expected_hours_string = "Unknown"

                new_message += f"Elapsed / Remaining Time: {elapsed_hours:.1f}h / {expected_hours_string} \n"

                new_message += f"Status: {outage['status']}\n"
                new_message += f"Cause: {outage['cause']}\n"
                
                # Add location if available
                if pd.notna(outage['center_lat']) and pd.notna(outage['center_lon']):
                    location_info = outage_utils.reverse_geocode(outage['center_lat'], outage['center_lon'], geocode_api_key)
                    new_message += f"Location: {location_info}\n"

                new_message += f"{current_time.astimezone(pytz.timezone('US/Pacific')).strftime('%Y-%m-%d %H:%M %Z')}\n"
                
                messages_to_send.append(('new', new_message, outage['outage_id']))

        if not active_outages.empty:
            for _, outage in active_outages.iterrows():
                
                elapsed_hours = outage['elapsed_time_minutes'] / 60
                
                new_message = f"🚨 ESCALATED OUTAGE 🚨\n\n"
                new_message += f"Utility/ID: {get_utility_display_name(outage['utility'])} / {outage['outage_id']}\n"
                new_message += f"Customers: {outage['customers_impacted']:,.0f} \n"
                
                # Add estimated duration if available
                if pd.notna(outage['expected_length_minutes']) and outage['expected_length_minutes'] is not None:
                    expected_hours_string = f"{outage['expected_length_minutes'] / 60:.1f}h"
                else:
                    expected_hours_string = "Unknown"

                new_message += f"Elapsed / Remaining Time: {elapsed_hours:.1f}h / {expected_hours_string} \n"
                new_message += f"Status: {outage['status']}\n"
                new_message += f"Cause: {outage['cause']}\n"
                
                # Add escalation reason if available
                if 'notification_reason' in outage and pd.notna(outage['notification_reason']):
                    escaped_reason = escape_markdown(outage['notification_reason'])
                    new_message += f"Reason: {escaped_reason}\n"

                # Add location if available
                if pd.notna(outage['center_lat']) and pd.notna(outage['center_lon']):
                    location_info = outage_utils.reverse_geocode(outage['center_lat'], outage['center_lon'], geocode_api_key)
                    new_message += f"Location: {location_info}\n"

                new_message += f"{current_time.astimezone(pytz.timezone('US/Pacific')).strftime('%Y-%m-%d %H:%M %Z')}\n"
                    
                messages_to_send.append(('escalated', new_message, outage['outage_id']))


        # Create individual notification for each resolved outage  
        if not resolved_outages.empty:
            for _, outage in resolved_outages.iterrows():
                resolved_message = f"😌 RESOLVED OUTAGE 😌\n\n"
                resolved_message += f"Utility/ID: {get_utility_display_name(outage['utility'])} / {outage['outage_id']}\n"
                resolved_message += f"Customers: {outage['customers_impacted']:,.0f}\n"
                
                # Add actual duration if available
                if pd.notna(outage['elapsed_time_minutes']) and outage['elapsed_time_minutes'] is not None:
                    actual_hours = outage['elapsed_time_minutes'] / 60
                    resolved_message += f"Actual Duration: {actual_hours:.1f}h\n"

                resolved_message += f"Cause: {outage['cause']}\n"
                
                # Add location if available
                if pd.notna(outage['center_lat']) and pd.notna(outage['center_lon']):
                    location_info = outage_utils.reverse_geocode(outage['center_lat'], outage['center_lon'], geocode_api_key)
                    resolved_message += f"Location: {location_info}\n"
                
                resolved_message += f"{current_time.astimezone(pytz.timezone('US/Pacific')).strftime('%Y-%m-%d %H:%M %Z')}\n"
                
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
            notification_path = os.path.join(notification_output_dir, notification_filename)
            with open(notification_path, 'w', encoding="utf-8") as f:
                f.write(message)
            print(f"{msg_type.capitalize()} outage notification for {outage_id} saved to: {notification_path}")
        
        if not messages_to_send:
            print("No outages meeting criteria - no notification sent.")
            
    except Exception as e:
        print(f"Error sending notification: {e}")

# print out the dataframe in a pretty format, including just the outageid, customers affected, expected length, and elapsed time
def print_dataframe_pretty(df):
    if not df.empty:
        print(df[['outage_id', 'customers_impacted', 'expected_length_minutes', 'elapsed_time_minutes']])
    else:
        print("DataFrame is empty")

def main():
    parser = argparse.ArgumentParser(description="Send notifications about outages based on a set of file updates.")

    parser.add_argument('-d', '--directory', type=str, default='.', help='Directory containing files that match the pattern')
    parser.add_argument('-r', '--remaining_expected_length_threshold', type=float, default=4.0, 
                       help='Minimum remaining expected length threshold in hours (default: 4.0)')
    parser.add_argument('-c', '--customer_threshold', type=int, default=100, 
                       help='Customers affected threshold  (default: 100)')
    parser.add_argument('-lc', '--large_outage_customer_threshold', type=int, default=1000, 
                       help='Customers affected threshold  (default: 1000)')
    parser.add_argument('-e', '--elapsed_time_threshold', type=float, default=0.25, 
                       help='Minimum elapsed time threshold in hours (default: 0.25)')
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
    parser.add_argument('--notification-output-dir', type=str, default=".",
                       help='Directory to save notification files for testing (default: current directory)')
    parser.add_argument('-zw', '--zip-whitelist-file', type=str,
                       help='File containing zip codes to filter (one per line, optional)')
    parser.add_argument('-zb', '--zip-boundaries-file', type=str,
                       help='File containing zip codes boundaries (required if zip whitelist is provided)')                       
    args = parser.parse_args()
    
    print(f"====== analyze_current_outages.py starting for utility {args.utility} =======")


    # Convert thresholds from hours to minutes
    expected_length_threshold_minutes = args.remaining_expected_length_threshold * 60
    elapsed_time_threshold_minutes = args.elapsed_time_threshold * 60

    print(f"Expected length threshold: {args.remaining_expected_length_threshold} hours ({expected_length_threshold_minutes} minutes)")
    print(f"Customer threshold: {args.customer_threshold}")
    print(f"Large outage customer threshold: {args.large_outage_customer_threshold}")
    print(f"Elapsed time threshold: {args.elapsed_time_threshold} hours ({elapsed_time_threshold_minutes} minutes)")

    filename_suffix = outage_utils.get_filename_suffix_for_utility(args.utility)
    file_pattern = os.path.join(args.directory, "*"+filename_suffix)
    print(f"file pattern {file_pattern}")
    all_files = sorted(glob.glob(file_pattern), reverse=False)

    if(len(all_files) < 2):
        print("Not enough files to compare. Exiting.")
        sys.exit(3)

    # Load zip code whitelist and boundaries if provided
    zip_code_whitelist = None
    if args.zip_whitelist_file:
        try:
            with open(args.zip_whitelist_file, 'r') as f:
                zip_code_whitelist = [line.strip() for line in f if line.strip()]
            print(f"Loaded {len(zip_code_whitelist)} zip codes from whitelist file")
                # Load zip code boundaries
            if args.zip_boundaries_file:
                zip_utils.load_zip_codes(args.zip_boundaries_file)
            else:
                print("Error: Zip whitelist provided without zip boundaries. Exiting.")
                sys.exit(4)
        except FileNotFoundError:
            print(f"Warning: Zip whitelist file not found: {args.zip_whitelist_file}")
        except Exception as e:
            print(f"Error loading zip whitelist file: {e}")


    is_first_file = True
    previous_file_df = pd.DataFrame()
    current_file_df = pd.DataFrame()
    for file_index, file in enumerate(all_files):
    # Extract date and time from filename
        print(f"====== starting processing for file =======")
        print(f"file: {file}")
        basename = os.path.basename(file)
        date_time_part = basename.split(filename_suffix)[0]
        # TODO: for some reason, the first file created by expand.py has a slightly different format. Figure out why and address there?
        # filenames are in GMT, stick with that throughout
        gmt_file_datetime = datetime.strptime(date_time_part, "%Y-%m-%dT%H%M%S%f")

        previous_file_df = current_file_df
        current_file_rows = []

        with open(file, "r", encoding="utf-8") as f:
            if(args.utility == "pse"):
                outage_utils.parse_pse_file(f, current_file_rows, gmt_file_datetime, False)
            elif (args.utility == "scl"):
                outage_utils.parse_scl_file(f, current_file_rows, gmt_file_datetime, False)
            elif (args.utility == "snopud"):
                outage_utils.parse_snopud_file(f, current_file_rows, gmt_file_datetime, False)
            elif (args.utility == "pge"):
                outage_utils.parse_pge_file(f, current_file_rows, gmt_file_datetime, False)
            else:
                print("no utility specified, will not parse")

        current_file_df = pd.DataFrame(current_file_rows)

        # filter outages by zipcode based on the whitelist of zipcodes
        if not current_file_df.empty and zip_code_whitelist is not None:
            # retrieve the zipcode for each outage based on the center_lon and center_lat
            current_file_df['zipcode'] = current_file_df.apply(
                lambda row: zip_utils.get_zip_code(row['center_lon'], row['center_lat']),
                axis=1
            )
            current_file_df = current_file_df[current_file_df['zipcode'].isin(zip_code_whitelist)]
        
        # add some calculated columns to the current file df
        if not current_file_df.empty:
            # Calculate expected length in minutes for latest outages
            current_file_df['expected_length_minutes'] = current_file_df.apply(
                lambda row: outage_utils.calculate_expected_length_minutes(gmt_file_datetime, row['est_restoration_time']), 
                axis=1
            )
            
            # Calculate active duration in minutes for latest outages
            current_file_df['elapsed_time_minutes'] = current_file_df.apply(
                lambda row: outage_utils.calculate_active_duration_minutes(row['start_time'], gmt_file_datetime), 
                axis=1
            )

        print(f"current_file_df after zip filtering and adding expected length and elapsed time:")
        print_dataframe_pretty(current_file_df)

        if is_first_file:
            is_first_file = False
            previous_file_df = current_file_df
            print(f"This was the first file, skipping comparisons")
            continue


        # compare the previous and current file rowsets to find notification-worthy changes
        # we need to look at:
        # outages in current that weren't in previous: we want to send a notification for these if they meet our thresholds
        # outages in previous that aren't in current: we want to send a notification for these if they meet our thresholds
        # outages in both: we want to send a notification for these if they didn't meet our thresholds in previous
        # but meet our thresholds in current

        # Handle empty DataFrames 
        if current_file_df.empty and previous_file_df.empty:
            # Both files are empty, no outages to compare
            new_outages = pd.DataFrame()
            resolved_outages = pd.DataFrame()
            active_outages = pd.DataFrame()
        elif current_file_df.empty:
            # Current file is empty, all previous outages are resolved
            new_outages = pd.DataFrame()
            resolved_outages = previous_file_df.copy()
            active_outages = pd.DataFrame()
        elif previous_file_df.empty:
            # Previous file is empty, all current outages are new
            new_outages = current_file_df.copy()
            resolved_outages = pd.DataFrame()
            active_outages = pd.DataFrame()
        else:
            # Both DataFrames have data, perform normal comparison
            new_outages = current_file_df[~current_file_df['outage_id'].isin(previous_file_df['outage_id'])]
            resolved_outages = previous_file_df[~previous_file_df['outage_id'].isin(current_file_df['outage_id'])]
            active_outages = current_file_df[current_file_df['outage_id'].isin(previous_file_df['outage_id'])]

        notifiable_new_outages = pd.DataFrame()
        if not new_outages.empty:
            notifiable_new_outages = new_outages[
                (((new_outages['expected_length_minutes'] >= expected_length_threshold_minutes) &
                (new_outages['customers_impacted'] >= args.customer_threshold) &
                (new_outages['elapsed_time_minutes'] >= elapsed_time_threshold_minutes)) |
                (new_outages['customers_impacted'] >= args.large_outage_customer_threshold))
            ]

        notifiable_resolved_outages = pd.DataFrame()
        if not resolved_outages.empty:
            notifiable_resolved_outages = resolved_outages[
                ((resolved_outages['customers_impacted'] >= args.customer_threshold) &
                (resolved_outages['expected_length_minutes'] >= expected_length_threshold_minutes) &
                (resolved_outages['elapsed_time_minutes'] >= elapsed_time_threshold_minutes)) |
                (resolved_outages['customers_impacted'] >= args.large_outage_customer_threshold)
            ]

        # Check active outages (outages that exist in both previous and current files)
        notifiable_active_outages = pd.DataFrame()
        if not active_outages.empty:
            # Get the corresponding previous data for active outages
            active_previous = previous_file_df[previous_file_df['outage_id'].isin(active_outages['outage_id'])]
            
            # Merge current and previous data for active outages
            active_merged = active_outages.merge(
                active_previous[['outage_id', 'expected_length_minutes', 'elapsed_time_minutes', 'customers_impacted']], 
                on='outage_id', 
                suffixes=('_current', '_previous')
            )
            
            # Check which active outages meet thresholds now but didn't before
            # Define the conditions for each type of notification
            primary_thresholds_met = (
                (active_merged['expected_length_minutes_current'] >= expected_length_threshold_minutes) &
                (active_merged['customers_impacted_current'] >= args.customer_threshold) &
                (active_merged['elapsed_time_minutes_current'] >= elapsed_time_threshold_minutes)
            )
            
            primary_thresholds_not_met_previously = (
                (pd.isna(active_merged['expected_length_minutes_previous']) | (active_merged['expected_length_minutes_previous'] < expected_length_threshold_minutes)) |
                (pd.isna(active_merged['customers_impacted_previous']) | (active_merged['customers_impacted_previous'] < args.customer_threshold)) |
                (pd.isna(active_merged['elapsed_time_minutes_previous']) | (active_merged['elapsed_time_minutes_previous'] < elapsed_time_threshold_minutes))
            )
            
            large_outage_escalation = (
                (active_merged['customers_impacted_current'] >= args.large_outage_customer_threshold) &
                (active_merged['customers_impacted_previous'] < args.large_outage_customer_threshold)
            )
            
            # Determine which outages are notifiable
            notifiable_active_outages = active_merged[
                (primary_thresholds_met & primary_thresholds_not_met_previously) |
                large_outage_escalation
            ]
            
            # Add "why" information for each notifiable outage
            if not notifiable_active_outages.empty:
                def determine_notification_reason(row):
                    reasons = []
                    
                    # Check for primary threshold escalation
                    if (primary_thresholds_met.loc[row.name] and 
                        primary_thresholds_not_met_previously.loc[row.name]):
                        
                        # Determine which specific thresholds were newly exceeded
                        if (pd.isna(row['expected_length_minutes_previous']) or 
                            row['expected_length_minutes_previous'] < expected_length_threshold_minutes):
                            reasons.append(f"expected_length ({row['expected_length_minutes_previous']:.0f}=>{row['expected_length_minutes_current']:.0f})")
                        
                        if (pd.isna(row['customers_impacted_previous']) or 
                            row['customers_impacted_previous'] < args.customer_threshold):
                            reasons.append(f"customers ({row['customers_impacted_previous']}=>{row['customers_impacted_current']})")
                        
                        if (pd.isna(row['elapsed_time_minutes_previous']) or 
                            row['elapsed_time_minutes_previous'] < elapsed_time_threshold_minutes):
                            reasons.append(f"elapsed_time ({row['elapsed_time_minutes_previous']:.0f}=>{row['elapsed_time_minutes_current']:.0f})")
                    
                    # Check for large outage escalation
                    if large_outage_escalation.loc[row.name]:
                        reasons.append(f"customers ({row['customers_impacted_previous']}=>{row['customers_impacted_current']})")
                    
                    return ", ".join(reasons) if reasons else "unknown reason"
                
                notifiable_active_outages = notifiable_active_outages.copy()
                notifiable_active_outages['notification_reason'] = notifiable_active_outages.apply(determine_notification_reason, axis=1)
            
            # Rename columns to match expected format
            if not notifiable_active_outages.empty:
                notifiable_active_outages = notifiable_active_outages.rename(columns={
                    'customers_impacted_current': 'customers_impacted',
                    'expected_length_minutes_current': 'expected_length_minutes',
                    'elapsed_time_minutes_current': 'elapsed_time_minutes'
                })

        print(f"notifiable_new_outages:")
        print_dataframe_pretty(notifiable_new_outages)
        print(f"notifiable_resolved_outages:")
        print_dataframe_pretty(notifiable_resolved_outages)
        print(f"notifiable_active_outages:")
        print_dataframe_pretty(notifiable_active_outages)
        
        # Print notification reasons for active outages
        if not notifiable_active_outages.empty and 'notification_reason' in notifiable_active_outages.columns:
            print(f"Active outage notification reasons:")
            for _, outage in notifiable_active_outages.iterrows():
                print(f"  Outage {outage['outage_id']}: {outage['notification_reason']}")

        print(f"====== completed processing for file =======")

        # Send notification if there are new outages or resolved outages
        print(f"sending notifications if there are new outages or resolved outages or notifiable active outages")
        if len(notifiable_new_outages) > 0 or len(notifiable_resolved_outages) > 0 or len(notifiable_active_outages) > 0:
            thresholds = {
                'length': args.remaining_expected_length_threshold,
                'customers': args.customer_threshold,
                'large_outage_customers': args.large_outage_customer_threshold,
                'elapsed': args.elapsed_time_threshold
            }
            # Pass both new and resolved outages to notification logic
            notification_data = {
                'new_outages': notifiable_new_outages,
                'resolved_outages': notifiable_resolved_outages,
                'active_outages': notifiable_active_outages
            }
            send_notification(notification_data, thresholds, args.telegram_token, args.telegram_chat_id, args.telegram_thread_id, args.geocode_api_key, args.notification_output_dir)

    print(f"====== outage_notifier.py completed =======")

if __name__ == "__main__":
    main()
    
    