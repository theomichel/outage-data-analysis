"""
Extended Outage Test Data - Expected Resolution Time Increase Scenario
Provides test data for testing outage detection when expected resolution time increases
from below threshold to above threshold, making it a "new" outage.
"""

import json

def get_default_mock_data():
    """Extended outage test scenario: Outage with increasing expected resolution time"""
    
    # Previous snapshot: Outage with short expected resolution time (below threshold)
    # Expected resolution: 2 hours (120 minutes) - below typical 6-hour threshold
    # Customers: 2000 (above threshold)
    # Elapsed time: 1 hour (60 minutes) - above typical 15-minute threshold
    short_resolution_content = json.dumps({
        "UnplannedOutageSummary": {"CustomerAfftectedCount": 2000, "OutageCount": 1, "LastUpdatedDatetime": "01/15 10:00 AM"},
        "PlannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 10:00 AM"},
        "PSPSSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 10:00 AM"},
        "CustomerProfile": None,
        "PseMap": [{
            "DataProvider": {
                "Attributes": [
                    {"Name": "Outage ID", "RefName": "OutageEventId", "Value": "INC000789"},
                    {"Name": "Customers impacted", "RefName": "Customers impacted", "Value": "2000"},
                    {"Name": "Start time", "RefName": "StartDate", "Value": "01/15 9:45 AM"},
                    {"Name": "Est. restoration time", "RefName": "Est. Restoration time", "Value": "01/15 10:45 AM"},
                    {"Name": "Status", "RefName": "Status", "Value": "Crew assigned"},
                    {"Name": "Cause", "RefName": "Cause", "Value": "Equipment failure"},
                    {"Name": "Last update", "RefName": "LastUpdated", "Value": "01/15 10:00 AM"}
                ],
                "PointOfInterest": {
                    "Latitude": "47.6062", "Longitude": "-122.3321",
                    "Id": "INC000789", "PlannedOutage": False, "FilterType": "Outage"
                }
            },
            "Polygon": [{"Latitude": "47.6062", "Longitude": "-122.3321"}],
            "BoundingBox": {"Min": {"Latitude": "47.6062", "Longitude": "-122.3321"}, "Max": {"Latitude": "47.6062", "Longitude": "-122.3321"}}
        }],
        "LastUpdated": "2025-01-15T18:00:00+00:00"
    }, indent=2)
    
    # Latest snapshot: Same outage with extended expected resolution time (above threshold)
    # Expected resolution: 8 hours (480 minutes) - above typical 6-hour threshold
    # Customers: 2000 (above threshold)
    # Elapsed time: 1.25 hours (75 minutes) - above typical 15-minute threshold
    extended_resolution_content = json.dumps({
        "UnplannedOutageSummary": {"CustomerAfftectedCount": 2000, "OutageCount": 1, "LastUpdatedDatetime": "01/15 10:10 AM"},
        "PlannedOutageSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 10:10 AM"},
        "PSPSSummary": {"CustomerAfftectedCount": 0, "OutageCount": 0, "LastUpdatedDatetime": "01/15 10:10 AM"},
        "CustomerProfile": None,
        "PseMap": [{
            "DataProvider": {
                "Attributes": [
                    {"Name": "Outage ID", "RefName": "OutageEventId", "Value": "INC000789"},
                    {"Name": "Customers impacted", "RefName": "Customers impacted", "Value": "2000"},
                    {"Name": "Start time", "RefName": "StartDate", "Value": "01/15 9:45 AM"},
                    {"Name": "Est. restoration time", "RefName": "Est. Restoration time", "Value": "01/16 12:45 AM"},
                    {"Name": "Status", "RefName": "Status", "Value": "Crew assigned"},
                    {"Name": "Cause", "RefName": "Cause", "Value": "Equipment failure"},
                    {"Name": "Last update", "RefName": "LastUpdated", "Value": "01/15 10:10 AM"}
                ],
                "PointOfInterest": {
                    "Latitude": "47.6062", "Longitude": "-122.3321",
                    "Id": "INC000789", "PlannedOutage": False, "FilterType": "Outage"
                }
            },
            "Polygon": [{"Latitude": "47.6062", "Longitude": "-122.3321"}],
            "BoundingBox": {"Min": {"Latitude": "47.6062", "Longitude": "-122.3321"}, "Max": {"Latitude": "47.6062", "Longitude": "-122.3321"}}
        }],
        "LastUpdated": "2025-01-15T18:10:00+00:00"
    }, indent=2)
    
    return {
        'commits': [
            {
                'hash': 'abc123456789',
                'message': 'Updated outage data - extended resolution time',
                'datetime': '2025-01-15T18:10:00+00:00',
                'files': {
                    'pse-events.json': extended_resolution_content
                }
            },
            {
                'hash': 'def987654321', 
                'message': 'Updated outage data - short resolution time',
                'datetime': '2025-01-15T18:00:00+00:00',
                'files': {
                    'pse-events.json': short_resolution_content
                }
            }
        ]
    }
