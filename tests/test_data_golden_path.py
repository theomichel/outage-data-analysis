"""
Golden Path Test Data - New Large Outage Scenario
Provides test data for testing new outage detection
"""

import json

def get_default_mock_data():
    """Golden path test scenario: Large outage that should trigger alerts"""
    
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
