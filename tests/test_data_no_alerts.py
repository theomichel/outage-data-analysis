"""
No Alerts Test Data - Small Outages Below Thresholds Scenario  
Provides test data for testing when no alerts should be triggered
"""

import json

def get_default_mock_data():
    """No alerts test scenario: All outages below thresholds"""
    
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
