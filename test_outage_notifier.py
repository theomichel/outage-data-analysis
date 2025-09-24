#!/usr/bin/env python3
"""
Test script for outage_notifier.py

This script runs the outage notifier with test data and validates the output
against expectations defined in a CSV file.
"""

import os
import sys
import subprocess
import pandas as pd
import glob
import re
from datetime import datetime
import tempfile
import shutil

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def supports_color():
    """Check if the terminal supports color output."""
    return (
        hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() and
        os.environ.get('TERM') != 'dumb' and
        os.environ.get('NO_COLOR') is None
    )

def get_colors():
    """Get color codes, with fallback to empty strings if colors are not supported."""
    if supports_color():
        return Colors()
    else:
        # Return a class with empty color strings
        class NoColors:
            GREEN = RED = YELLOW = BLUE = BOLD = END = ''
        return NoColors()


def run_outage_notifier(test_dir, geocode_api_key, output_dir):
    """
    Run the outage notifier with the specified parameters.
    
    Args:
        test_dir: Directory containing test JSON files
        geocode_api_key: Geocode API key (can be dummy for testing)
        output_dir: Directory to save notification files
    
    Returns:
        subprocess.CompletedProcess: Result of the command execution
    """
    cmd = [
        sys.executable,  # Use the same Python interpreter
        "outage_notifier.py",
        "-d", test_dir,
        "-u", "pge",
        "--geocode-api-key", geocode_api_key,
        "-zw", "./constant_data/bay_area_zip_codes.txt",
        "-zb", "./constant_data/ca_california_zip_codes_geo.min.json",
        "--notification-output-dir", output_dir
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        return result
    except Exception as e:
        print(f"Error running outage_notifier: {e}")
        return None


def parse_notification_files(output_dir):
    """
    Parse notification files created by the outage notifier.
    
    Args:
        output_dir: Directory containing notification files
    
    Returns:
        dict: Dictionary mapping outage_id to notification type
    """
    notifications = {}
    
    # Find all notification files
    pattern = os.path.join(output_dir, "notification_*.txt")
    notification_files = glob.glob(pattern)
    
    print(f"Found {len(notification_files)} notification files:")
    
    for file_path in notification_files:
        filename = os.path.basename(file_path)
        print(f"  - {filename}")
        
        # Parse filename: notification_{type}_{outage_id}_{timestamp}.txt
        match = re.match(r'notification_(\w+)_(\d+)_\d{8}_\d{6}\.txt', filename)
        if match:
            notification_type = match.group(1)
            outage_id = int(match.group(2))
            notifications[outage_id] = notification_type
        else:
            print(f"    Warning: Could not parse filename {filename}")
    
    return notifications


def load_expectations(expectations_file):
    """
    Load test expectations from CSV file.
    
    Args:
        expectations_file: Path to the expectations CSV file
    
    Returns:
        pandas.DataFrame: Expectations data
    """
    try:
        df = pd.read_csv(expectations_file)
        return df
    except Exception as e:
        print(f"Error loading expectations file: {e}")
        return None


def validate_notifications(notifications, expectations):
    """
    Validate actual notifications against expectations.
    
    Args:
        notifications: Dict mapping outage_id to notification type
        expectations: DataFrame with expected results
    
    Returns:
        tuple: (passed_count, failed_count, results)
    """
    results = []
    passed_count = 0
    failed_count = 0
    
    for _, row in expectations.iterrows():
        outage_id = int(row['outage_id'])
        expected_notification = row['notification_expected']
        why = row['why']
        
        actual_notification = notifications.get(outage_id, None)
        
        # Handle special case where 'none' means no notification should be sent
        if expected_notification == 'none':
            expected_notification = None
        
        if actual_notification == expected_notification:
            status = "PASS"
            passed_count += 1
        else:
            status = "FAIL"
            failed_count += 1
        
        result = {
            'outage_id': outage_id,
            'expected': expected_notification,
            'actual': actual_notification,
            'status': status,
            'why': why
        }
        results.append(result)
    
    return passed_count, failed_count, results


def print_results(results, passed_count, failed_count):
    """
    Print test results in a formatted way with color coding.
    
    Args:
        results: List of test results
        passed_count: Number of passed tests
        failed_count: Number of failed tests
    """
    colors = get_colors()
    
    print("\n" + "="*80)
    print(f"{colors.BOLD}TEST RESULTS{colors.END}")
    print("="*80)
    
    for result in results:
        if result['status'] == "PASS":
            status_symbol = f"{colors.GREEN}✓{colors.END}"
            status_text = f"{colors.GREEN}PASS{colors.END}"
        else:
            status_symbol = f"{colors.RED}✗{colors.END}"
            status_text = f"{colors.RED}FAIL{colors.END}"
        
        print(f"{status_symbol} Outage {result['outage_id']}: {status_text}")
        print(f"    Expected: {result['expected']}")
        print(f"    Actual:   {result['actual']}")
        print(f"    Test case:   {result['why']}")
        print()
    
    print("-"*80)
    
    # Color-coded summary
    if failed_count == 0:
        summary_text = f"{colors.GREEN}{colors.BOLD}SUMMARY: {passed_count} passed, {failed_count} failed{colors.END}"
    else:
        summary_text = f"{colors.RED}{colors.BOLD}SUMMARY: {passed_count} passed, {failed_count} failed{colors.END}"
    
    print(summary_text)
    print("="*80)
    
    if failed_count > 0:
        print(f"\n{colors.RED}{colors.BOLD}FAILED TESTS:{colors.END}")
        for result in results:
            if result['status'] == "FAIL":
                print(f"  {colors.RED}-{colors.END} Outage {result['outage_id']}: Expected {result['expected']}, got {result['actual']}")
                print(f"    Reason: {result['why']}")


def main():
    """Main test function."""
    colors = get_colors()
    print(f"{colors.BOLD}{colors.BLUE}Outage Notifier Test Script{colors.END}")
    print("="*50)
    
    # Configuration - can be overridden by command line arguments
    test_dir = "./tests/notifier_test_files"
    expectations_file = "./tests/notifier_test_files/pge_outages_test_expectations.csv"
    geocode_api_key = "dummy_geocode_key_for_testing"
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python test_outage_notifier.py <geocode_api_key> [test_dir] [expectations_file]")
        print("  geocode_api_key: Required - Geocode API key for testing")
        print("  test_dir: Optional - Directory containing test JSON files (default: ./tests/notifier_test_files)")
        print("  expectations_file: Optional - CSV file with test expectations (default: ./tests/notifier_test_files/pge_outages_test_expectations.csv)")
        return 1
    
    geocode_api_key = sys.argv[1]
    
    if len(sys.argv) > 2:
        test_dir = sys.argv[2]
    if len(sys.argv) > 3:
        expectations_file = sys.argv[3]
    
    # Create temporary directory for notification output
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory for notifications: {temp_dir}")
        
        # Check if test files exist
        if not os.path.exists(test_dir):
            print(f"Error: Test directory not found: {test_dir}")
            return 1
        
        if not os.path.exists(expectations_file):
            print(f"Error: Expectations file not found: {expectations_file}")
            return 1
        
        # Load expectations
        print("Loading test expectations...")
        expectations = load_expectations(expectations_file)
        if expectations is None:
            return 1
        
        print(f"Loaded {len(expectations)} test expectations")
        
        # Run outage notifier
        print("\nRunning outage notifier...")
        result = run_outage_notifier(test_dir, geocode_api_key, temp_dir)
        
        if result is None:
            print("Error: Failed to run outage notifier")
            return 1
        
        if result.returncode != 0:
            print(f"{colors.RED}Error: Outage notifier failed with return code {result.returncode}{colors.END}")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return 1
        
        print(f"{colors.GREEN}Outage notifier completed successfully{colors.END}")
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Parse notification files
        print("\nParsing notification files...")
        notifications = parse_notification_files(temp_dir)
        
        # Validate results
        print("\nValidating results...")
        passed_count, failed_count, results = validate_notifications(notifications, expectations)
        
        # Print results
        print_results(results, passed_count, failed_count)
        
        # Return appropriate exit code
        return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
