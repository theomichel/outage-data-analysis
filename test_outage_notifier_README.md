# Outage Notifier Test Script

This script tests the `outage_notifier.py` functionality by running it with test data and validating the output against expected results.

## Usage

```bash
python test_outage_notifier.py -u <utility> -k <geocode_api_key> [-d test_dir] [-e expectations_file]
```

### Parameters:
- **-u, --utility** (required): Utility name (choices: pge, pse, scl, snopud)
- **-k, --geocode-api-key** (required): Geocode API key for testing
- **-d, --test-dir** (optional): Directory containing test JSON files (default: `./tests/notifier_test_files`)
- **-e, --expectations-file** (optional): CSV file with test expectations (default: `./tests/notifier_test_files/pge_outages_test_expectations.csv`)

### Examples:
```bash
# Basic usage with required parameters
python test_outage_notifier.py -u pge -k "your_geocode_api_key_here"

# Using long form flags
python test_outage_notifier.py --utility pge --geocode-api-key "your_geocode_api_key_here"

# Custom test directory
python test_outage_notifier.py -u pge -k "your_api_key" -d "./custom_test_dir"

# Custom test directory and expectations file
python test_outage_notifier.py -u pge -k "your_api_key" -d "./custom_test_dir" -e "./custom_expectations.csv"

# Test different utilities
python test_outage_notifier.py -u pse -k "your_api_key"
python test_outage_notifier.py -u scl -k "your_api_key"
python test_outage_notifier.py -u snopud -k "your_api_key"

# Get help
python test_outage_notifier.py --help
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
