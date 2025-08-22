"""
SNOPUD Separate Outages Test Data
Provides test data for testing SNOPUD outage processing when placemarks have different start times.
Two placemarks with different start times should remain as separate outages.
"""

import json

def get_default_mock_data():
    """Separate outages test scenario: Two placemarks with different start times"""
    
    # Mock Git commit data with two SNOPUD KML files
    return {
        "commits": [
            {
                "hash": "abc123",
                "author": "Test User",
                "datetime": "2025-01-15T18:00:00+00:00",
                "message": "Add SNOPUD outage data",
                "files": {
                    "KMLOutageAreas.xml": """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
<Folder>
<name>Outage Areas</name>

<Placemark>
<name>6207</name>
<ExtendedData>
<Data name="StartUTC"><value>2025-01-15T13:26:42.0000000+00:00</value></Data>
<Data name="Cause"><value>Equipment Failure</value></Data>
<Data name="EstCustomersOut"><value>5</value></Data>
<Data name="UploadTimestampUTC"><value>2025-01-15T14:40:03.0000000+00:00</value></Data>
<Data name="EstimatedRestorationUTC"><value>2025-01-15T15:45:00.0000000+00:00</value></Data>
<Data name="OutageStatus"><value>We're investigating</value></Data>
<Data name="IsStormModeData"><value>False</value></Data>
<Data name="DistrictBroadcastMessages"><value>[]</value></Data>
<Data name="RegionBroadcastMessages"><value>[]</value></Data>
<Data name="IncidentBroadcastMessages"><value>[]</value></Data>
</ExtendedData>
<Polygon xmlns="http://www.opengis.net/kml/2.2">
<outerBoundaryIs>
<LinearRing>
<coordinates>-121.893142092459,48.1090976513446,0 -121.887738391831,48.1090806645585,0 -121.882334694792,48.1090634236574,0 -121.882350762292,48.1126891721402,0 -121.893142092459,48.1090976513446,0</coordinates>
</LinearRing>
</outerBoundaryIs>
</Polygon>
</Placemark>

<Placemark>
<name>8431</name>
<ExtendedData>
<Data name="StartUTC"><value>2025-01-15T14:30:15.0000000+00:00</value></Data>
<Data name="Cause"><value>Weather Related</value></Data>
<Data name="EstCustomersOut"><value>3</value></Data>
<Data name="UploadTimestampUTC"><value>2025-01-15T14:40:03.0000000+00:00</value></Data>
<Data name="EstimatedRestorationUTC"><value>2025-01-15T16:30:00.0000000+00:00</value></Data>
<Data name="OutageStatus"><value>We're investigating</value></Data>
<Data name="IsStormModeData"><value>False</value></Data>
<Data name="DistrictBroadcastMessages"><value>[]</value></Data>
<Data name="RegionBroadcastMessages"><value>[]</value></Data>
<Data name="IncidentBroadcastMessages"><value>[]</value></Data>
</ExtendedData>
<Polygon xmlns="http://www.opengis.net/kml/2.2">
<outerBoundaryIs>
<LinearRing>
<coordinates>-121.893222356868,48.1163345809062,0 -121.887794593426,48.1163248777979,0 -121.882366832054,48.1163149183427,0 -121.882502092514,48.1197901896091,0 -121.893222356868,48.1163345809062,0</coordinates>
</LinearRing>
</outerBoundaryIs>
</Polygon>
</Placemark>

</Folder>
</Document>
</kml>"""
                }
            }
        ]
    }
