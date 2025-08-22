"""
Test Data Scenarios for Outage Processing Pipeline
Provides various test scenarios for different testing needs
"""

import json


def get_golden_path_scenario():
    """
    Golden path test scenario: Large outage that should trigger alerts
    
    Returns test data with:
    - Previous snapshot: Small outage (50 customers, below threshold)
    - Current snapshot: Large outage (1500 customers, above threshold)
    
    Expected result: Should detect INC123456 as a new significant outage
    """
    
    # Small outage for previous snapshot (below alert thresholds)
    small_outage_content = json.dumps({
        "UnplannedOutageSummary": {"CustomerAfftectedCount": 50, "OutageCount": 1, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "PlannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "PSPSSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "CustomerProfile": None,
        "PseMap": [{
            "DataProvider": {
                "Attributes": [
                    {"Name": "Outage ID", "RefName": "OutageEventId", "Value": "INC000001"},
                    {"Name": "Customers impacted", "RefName": "Customers impacted", "Value": "50"},
                    {"Name": "Start time", "RefName": "StartDate", "Value": "01/15 8:00 AM"},
                    {"Name": "Est. restoration time", "RefName": "Est. Restoration time", "Value": "01/15 12:00 PM"},
                    {"Name": "Status", "RefName": "Status", "Value": "Crew assigned"},
                    {"Name": "Cause", "RefName": "Cause", "Value": "Equipment failure"},
                    {"Name": "Last update", "RefName": "LastUpdated", "Value": "01/15 17:45 PM"}
                ],
                "PointOfInterest": {
                    "Latitude": "47.5000", "Longitude": "-122.4000", 
                    "Id": "INC000001", "PlannedOutage": False, "FilterType": "Outage"
                }
            },
            "Polygon": [{"Latitude": "47.5000", "Longitude": "-122.4000"}],
            "BoundingBox": {"Min": {"Latitude": "47.5000", "Longitude": "-122.4000"}, "Max": {"Latitude": "47.5000", "Longitude": "-122.4000"}}
        }],
        "LastUpdated": "2024-01-15T17:45:00+00:00"
    }, indent=2)
    
    # Large outage for current snapshot (above alert thresholds)
    large_outage_content = json.dumps({
        "UnplannedOutageSummary": {"CustomerAfftectedCount": 1500, "OutageCount": 1, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "PlannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "PSPSSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "CustomerProfile": None,
        "PseMap": [{
            "DataProvider": {
                "Attributes": [
                    {"Name": "Outage ID", "RefName": "OutageEventId", "Value": "INC123456"},
                    {"Name": "Customers impacted", "RefName": "Customers impacted", "Value": "1500"},
                    {"Name": "Start time", "RefName": "StartDate", "Value": "01/15 9:30 AM"},
                    {"Name": "Est. restoration time", "RefName": "Est. Restoration time", "Value": "01/15 9:00 PM"},
                    {"Name": "Status", "RefName": "Status", "Value": "Crew assigned"},
                    {"Name": "Cause", "RefName": "Cause", "Value": "Equipment failure"},
                    {"Name": "Last update", "RefName": "LastUpdated", "Value": "01/15 18:00 PM"}
                ],
                "PointOfInterest": {
                    "Latitude": "47.6062", "Longitude": "-122.3321",
                    "Id": "INC123456", "PlannedOutage": False, "FilterType": "Outage"
                }
            },
            "Polygon": [{"Latitude": "47.6062", "Longitude": "-122.3321"}],
            "BoundingBox": {"Min": {"Latitude": "47.6062", "Longitude": "-122.3321"}, "Max": {"Latitude": "47.6062", "Longitude": "-122.3321"}}
        }],
        "LastUpdated": "2024-01-15T18:00:00+00:00"
    }, indent=2)
    
    return {
        'commits': [
            {
                'hash': 'abc123456789',
                'message': 'Updated outage data - large outage detected',
                'datetime': '2024-01-15T18:00:00+00:00',
                'files': {
                    'pse-events.json': large_outage_content
                }
            },
            {
                'hash': 'def987654321', 
                'message': 'Updated outage data - small outage',
                'datetime': '2024-01-15T17:45:00+00:00',
                'files': {
                    'pse-events.json': small_outage_content
                }
            }
        ]
    }


def get_no_alerts_scenario():
    """
    No alerts scenario: All outages below thresholds
    
    Returns test data with:
    - Previous snapshot: Very small outage (25 customers)
    - Current snapshot: Small outage (75 customers, still below 100 threshold)
    
    Expected result: No alerts should be triggered
    """
    
    # Very small outage for previous snapshot
    tiny_outage_content = json.dumps({
        "UnplannedOutageSummary": {"CustomerAfftectedCount": 25, "OutageCount": 1, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "PlannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "PSPSSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "CustomerProfile": None,
        "PseMap": [{
            "DataProvider": {
                "Attributes": [
                    {"Name": "Outage ID", "RefName": "OutageEventId", "Value": "INC000001"},
                    {"Name": "Customers impacted", "RefName": "Customers impacted", "Value": "25"},
                    {"Name": "Start time", "RefName": "StartDate", "Value": "01/15 8:00 AM"},
                    {"Name": "Est. restoration time", "RefName": "Est. Restoration time", "Value": "01/15 12:00 PM"},
                    {"Name": "Status", "RefName": "Status", "Value": "Crew assigned"},
                    {"Name": "Cause", "RefName": "Cause", "Value": "Equipment failure"},
                    {"Name": "Last update", "RefName": "LastUpdated", "Value": "01/15 17:45 PM"}
                ],
                "PointOfInterest": {
                    "Latitude": "47.5000", "Longitude": "-122.4000", 
                    "Id": "INC000001", "PlannedOutage": False, "FilterType": "Outage"
                }
            },
            "Polygon": [{"Latitude": "47.5000", "Longitude": "-122.4000"}],
            "BoundingBox": {"Min": {"Latitude": "47.5000", "Longitude": "-122.4000"}, "Max": {"Latitude": "47.5000", "Longitude": "-122.4000"}}
        }],
        "LastUpdated": "2024-01-15T17:45:00+00:00"
    }, indent=2)
    
    # Small outage for current snapshot (still below threshold)
    small_outage_content = json.dumps({
        "UnplannedOutageSummary": {"CustomerAfftectedCount": 75, "OutageCount": 1, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "PlannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "PSPSSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "CustomerProfile": None,
        "PseMap": [{
            "DataProvider": {
                "Attributes": [
                    {"Name": "Outage ID", "RefName": "OutageEventId", "Value": "INC000002"},
                    {"Name": "Customers impacted", "RefName": "Customers impacted", "Value": "75"},
                    {"Name": "Start time", "RefName": "StartDate", "Value": "01/15 9:30 AM"},
                    {"Name": "Est. restoration time", "RefName": "Est. Restoration time", "Value": "01/15 2:00 PM"},
                    {"Name": "Status", "RefName": "Status", "Value": "Crew assigned"},
                    {"Name": "Cause", "RefName": "Cause", "Value": "Tree on line"},
                    {"Name": "Last update", "RefName": "LastUpdated", "Value": "01/15 18:00 PM"}
                ],
                "PointOfInterest": {
                    "Latitude": "47.6062", "Longitude": "-122.3321",
                    "Id": "INC000002", "PlannedOutage": False, "FilterType": "Outage"
                }
            },
            "Polygon": [{"Latitude": "47.6062", "Longitude": "-122.3321"}],
            "BoundingBox": {"Min": {"Latitude": "47.6062", "Longitude": "-122.3321"}, "Max": {"Latitude": "47.6062", "Longitude": "-122.3321"}}
        }],
        "LastUpdated": "2024-01-15T18:00:00+00:00"
    }, indent=2)
    
    return {
        'commits': [
            {
                'hash': 'xyz789012345',
                'message': 'Updated outage data - small outage growth',
                'datetime': '2024-01-15T18:00:00+00:00',
                'files': {
                    'pse-events.json': small_outage_content
                }
            },
            {
                'hash': 'uvw456789012', 
                'message': 'Updated outage data - tiny outage',
                'datetime': '2024-01-15T17:45:00+00:00',
                'files': {
                    'pse-events.json': tiny_outage_content
                }
            }
        ]
    }


def get_resolved_outage_scenario():
    """
    Resolved outage scenario: Large outage that gets resolved
    
    Returns test data with:
    - Previous snapshot: Large outage (2000 customers, above threshold)
    - Current snapshot: No outages (empty PseMap)
    
    Expected result: Should detect resolution of INC789012 
    """
    
    # Large outage for previous snapshot
    large_outage_content = json.dumps({
        "UnplannedOutageSummary": {"CustomerAfftectedCount": 2000, "OutageCount": 1, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "PlannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "PSPSSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 17:45 PM"},
        "CustomerProfile": None,
        "PseMap": [{
            "DataProvider": {
                "Attributes": [
                    {"Name": "Outage ID", "RefName": "OutageEventId", "Value": "INC789012"},
                    {"Name": "Customers impacted", "RefName": "Customers impacted", "Value": "2000"},
                    {"Name": "Start time", "RefName": "StartDate", "Value": "01/15 7:00 AM"},
                    {"Name": "Est. restoration time", "RefName": "Est. Restoration time", "Value": "01/15 6:00 PM"},
                    {"Name": "Status", "RefName": "Status", "Value": "Crew assigned"},
                    {"Name": "Cause", "RefName": "Cause", "Value": "Transformer failure"},
                    {"Name": "Last update", "RefName": "LastUpdated", "Value": "01/15 17:45 PM"}
                ],
                "PointOfInterest": {
                    "Latitude": "47.7000", "Longitude": "-122.2000", 
                    "Id": "INC789012", "PlannedOutage": False, "FilterType": "Outage"
                }
            },
            "Polygon": [{"Latitude": "47.7000", "Longitude": "-122.2000"}],
            "BoundingBox": {"Min": {"Latitude": "47.7000", "Longitude": "-122.2000"}, "Max": {"Latitude": "47.7000", "Longitude": "-122.2000"}}
        }],
        "LastUpdated": "2024-01-15T17:45:00+00:00"
    }, indent=2)
    
    # No outages for current snapshot (all resolved)
    no_outages_content = json.dumps({
        "UnplannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "PlannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "PSPSSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 18:00 PM"},
        "CustomerProfile": None,
        "PseMap": [],  # Empty - all outages resolved
        "LastUpdated": "2024-01-15T18:00:00+00:00"
    }, indent=2)
    
    return {
        'commits': [
            {
                'hash': 'rst345678901',
                'message': 'Updated outage data - all outages resolved',
                'datetime': '2024-01-15T18:00:00+00:00',
                'files': {
                    'pse-events.json': no_outages_content
                }
            },
            {
                'hash': 'mno012345678', 
                'message': 'Updated outage data - large outage ongoing',
                'datetime': '2024-01-15T17:45:00+00:00',
                'files': {
                    'pse-events.json': large_outage_content
                }
            }
        ]
    }


# Default scenario (backward compatibility)
def get_default_mock_data():
    """Default test scenario - same as golden path for backward compatibility"""
    return get_golden_path_scenario()


if __name__ == "__main__":
    # Example usage / test
    print("Available test scenarios:")
    print("1. Golden Path (new large outage):")
    golden = get_golden_path_scenario()
    print(f"   {len(golden['commits'])} commits")
    
    print("2. No Alerts (small outages only):")
    no_alerts = get_no_alerts_scenario()
    print(f"   {len(no_alerts['commits'])} commits")
    
    print("3. Resolved Outage (large outage gets resolved):")
    resolved = get_resolved_outage_scenario()
    print(f"   {len(resolved['commits'])} commits")
