import pandas as pd
from datetime import datetime
import argparse
import json
import math
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
        # Convert to datetime if it's a string
        start_time = pd.to_datetime(start_time)
        current_time = pd.to_datetime(current_time)
        
        # Calculate difference in minutes
        time_diff = current_time - start_time
        return int(time_diff.total_seconds() / 60)
    except Exception as e:
        print(f"Error calculating active duration: {e}")
        return None

def send_notification(notification_data, file_input, thresholds):
    """
    Send email notification about outages that meet the threshold criteria.
    notification_data contains: new_outages, resolved_outages, new_customers, resolved_customers
    """
    try:
        # Email configuration - using environment variables for security
        # smtp_server = os.getenv('SMTP_SERVER', 'localhost')
        # smtp_port = int(os.getenv('SMTP_PORT', '587'))
        # smtp_user = os.getenv('SMTP_USER', '')
        # smtp_password = os.getenv('SMTP_PASSWORD', '')
        # from_email = os.getenv('FROM_EMAIL', smtp_user)
        
        new_outages = notification_data['new_outages']
        resolved_outages = notification_data['resolved_outages']
        new_customers = notification_data['new_customers']
        resolved_customers = notification_data['resolved_customers']
        
        if not new_outages.empty or not resolved_outages.empty:
            # Create email content
            # msg = MIMEMultipart()
            # msg['From'] = from_email
            # msg['To'] = ', '.join(email_addresses)
            # msg['Subject'] = f"Outage Alert: {len(outages_df)} outages meeting threshold criteria"
            
                        # Create notification body
            total_new = len(new_outages)
            total_resolved = len(resolved_outages)
            
            body = f"""
Outage Analysis Alert
====================

Analysis of: {file_input}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Summary:
- New outages meeting criteria: {total_new}
- New customers affected: {new_customers:,.0f}
- Resolved outages: {total_resolved}
- Customers restored: {resolved_customers:,.0f}

Thresholds Applied:
- Expected length: {thresholds['length']} hours
- Customer impact: {thresholds['customers']} customers
- Elapsed time: {thresholds['elapsed']} hours

"""
            
            # Add details for new outages
            if not new_outages.empty:
                body += "\nNEW OUTAGES:\n"
                for _, outage in new_outages.iterrows():
                    elapsed_hours = outage['elapsed_time_minutes'] / 60
                    expected_hours = outage['expected_length_minutes'] / 60 if pd.notna(outage['expected_length_minutes']) else 'N/A'
                    
                    body += f"""
- Outage ID: {outage['outage_id']}
  Customers: {outage['customers_impacted']:,.0f}
  Started: {outage['start_time']}
  Elapsed: {elapsed_hours:.1f} hours
  Expected Duration: {expected_hours} hours
  Location: ({outage['center_lat']:.4f}, {outage['center_lon']:.4f})
"""

            # Add details for resolved outages
            if not resolved_outages.empty:
                body += "\nRESOLVED OUTAGES:\n"
                for _, outage in resolved_outages.iterrows():
                    body += f"""
- Outage ID: {outage['outage_id']}
  Customers: {outage['customers_impacted']:,.0f}
  Started: {outage['start_time']}
  Location: ({outage['center_lat']:.4f}, {outage['center_lon']:.4f})
"""
            # msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            # if smtp_user and smtp_password:
            #     server = smtplib.SMTP(smtp_server, smtp_port)
            #     server.starttls()
            #     server.login(smtp_user, smtp_password)
            #     text = msg.as_string()
            #     server.sendmail(from_email, email_addresses, text)
            #     server.quit()
            #     print(f"Email notification sent to: {', '.join(email_addresses)}")
            # else:
            #     print("Email credentials not configured. Set SMTP_USER and SMTP_PASSWORD environment variables.")
                
            # Save notification to timestamped file
            notification_filename = f"notification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(notification_filename, 'w') as f:
                f.write(body)
            print(f"Notification saved to: {notification_filename}")
        else:
            print("No outages meeting criteria - no email sent.")
            
    except Exception as e:
        print(f"Error sending email notification: {e}")

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
    parser.add_argument('--email', nargs='+', 
                       help='Email addresses to notify if outages meet threshold criteria (space-separated)')
    parser.add_argument('-u', '--utility', type=str, required=True,
                       help='utility, for now only used in output file naming')
    args = parser.parse_args()
    
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
        
        # Filter latest outages that exceed the thresholds
        significant_latest = latest_outages_df[latest_outages_df['expected_length_minutes'] > threshold_minutes]
        significant_latest = significant_latest[significant_latest['customers_impacted'] > args.customer_threshold]
        significant_latest = significant_latest[significant_latest['elapsed_time_minutes'] > elapsed_time_threshold_minutes]
        
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

    # Send email notification if there are new outages or resolved outages
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
        send_notification(notification_data, args.file_input, thresholds)

if __name__ == "__main__":
    main()
    
    