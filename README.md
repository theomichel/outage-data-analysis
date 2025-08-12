# Outage Processing Tools

This directory contains Python scripts for processing and analyzing power outage data from multiple utilities (PSE, SCL, and SNO PUD). The tools parse various data formats, calculate geometric properties of outage areas, and provide analysis capabilities.

## Python Files

### `expand.py`
Git-based file versioning tool that extracts historical versions of data files from repository commits. Iterates through commit history to export file snapshots at different points in time, enabling temporal analysis of data evolution. Useful for understanding how outage data changes over time and tracking data quality improvements. Supports export of multiple file versions with timestamp-based naming.

### `create_outages_dataframe.py`
Main data processing script that converts utility-specific outage data into a standardized CSV format. Supports PSE (JSON), SCL (JSON), and SNO PUD (KML) data sources. Parses polygon coordinates, calculates smallest enclosing circles for outage areas, and extracts metadata like outage IDs, customer counts, and timestamps. Handles timezone conversions and normalizes data structures across different utility formats. Outputs `outage_updates.csv` with consistent schema for downstream analysis.

### `analyze_current_outages.py`
Filters and analyzes the most recent outage data snapshot. Identifies current outages by finding the latest timestamp in the dataset, then applies configurable thresholds for outage duration and customer impact. Calculates expected outage lengths and creates a filtered subset of active outages. Useful for real-time monitoring and identifying outages that meet specific criteria for response prioritization.

### `analyze_historical_outages.py`
Performs longitudinal analysis of outage data across multiple time points. Tracks changes in outage properties over time, including polygon modifications, start time updates, and restoration time adjustments. Generates summary statistics and identifies outages with evolving characteristics. Excludes edge cases where outages span the entire dataset timeframe to focus on complete outage lifecycles.


## Data Files

- `outage_updates.csv`: Standardized outage data from all utilities
- `current_outages.csv`: Filtered current outage snapshot
- `outage_summary.csv`: Historical analysis results
- `pse-events.json`: Raw PSE outage data
- `files/`: Directory containing historical data snapshots

## Usage examples

```bash
# Extract file versions from git history
py expand.py -r ..\pse-outage -o .\output_files -l 100 "..\pse-outage\pse-events.json"

# Process data to create a dataframe
py create_outages_dataframe.py -d output_files -u pse -o pse_outages_dataframe.csv

# Analyze current outages with thresholds
 py analyze_current_outages.py -f pse_outages_dataframe.csv -l 0 -c 1

# Generate historical analysis
py analyze_historical_outages.py -f pse_outages_dataframe.csv

```
