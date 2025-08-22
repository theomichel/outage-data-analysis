"""
Resolved Outage Test Data - Large Outage Gets Resolved Scenario
Provides test data for testing resolved outage detection
"""

import json

def get_default_mock_data():
    """Resolved outage test scenario: Large outage that gets resolved"""
    
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
