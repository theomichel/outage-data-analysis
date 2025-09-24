# Outage Notifier Test Script

This script tests the `outage_notifier.py` functionality by running it with test data and validating the output against expected results.

## Usage

```bash
python test_outage_notifier.py <geocode_api_key> [test_dir] [expectations_file]
```

### Parameters:
- **geocode_api_key** (required): Geocode API key for testing
- **test_dir** (optional): Directory containing test JSON files (default: `./tests/notifier_test_files`)
- **expectations_file** (optional): CSV file with test expectations (default: `./tests/notifier_test_files/pge_outages_test_expectations.csv`)

### Examples:
```bash
# Basic usage with required geocode API key
python test_outage_notifier.py "your_geocode_api_key_here"

# Custom test directory
python test_outage_notifier.py "your_geocode_api_key_here" "./custom_test_dir"

# Custom test directory and expectations file
python test_outage_notifier.py "your_geocode_api_key_here" "./custom_test_dir" "./custom_expectations.csv"
```

## What it does

1. **Runs the outage notifier** with test data from `./tests/notifier_test_files/`
2. **Parses notification files** created by the notifier
3. **Validates results** against expectations in `pge_outages_test_expectations.csv`
4. **Reports test results** with detailed pass/fail information

## Test Data

- **Input files**: JSON files in `./tests/notifier_test_files/`
- **Expectations**: Defined in `pge_outages_test_expectations.csv`
- **Output**: Notification files saved to a temporary directory

## Exit Codes

- **0**: All tests passed
- **1**: One or more tests failed or script error occurred
