import os
import glob
import json
import pandas as pd
import pytz
from datetime import datetime
import argparse
from dateutil.parser import parse as parse_dt
from pykml import parser
import math
import logging 
import requests
import geopandas as gpd
import time

OUTPUT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
local_timezone = pytz.timezone('US/Pacific')

# grab attributes from an array of attributes, because PSE's json does it that way
def get_attr(attributes, attribute_name):
    for attr in attributes:
        if attr.get("RefName") == attribute_name:
            return attr.get("Value")
        elif attr.get("Name") == attribute_name:
            return attr.get("Value")
    return None

def find_element_in_kml_extended_data(extended_data, element_name):
    for data_element in extended_data.Data:
        if(data_element.attrib['name'] == element_name):
            return data_element.value
    raise Exception("element not found in KML")

def parse_kml_coordinate_string(coordinates_text):
    """Parse a KML coordinates string into a list of (lon, lat) float tuples.

    Coordinates come as space-separated triplets: "lon,lat,alt lon,lat,alt ...".
    Altitude is ignored.
    """
    if coordinates_text is None:
        return []
    tokens = coordinates_text.strip().split()
    points = []
    for token in tokens:
        parts = token.split(',')
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                points.append((lon, lat))
            except ValueError:
                # Skip malformed entries
                continue
    return points

# ----- Smallest enclosing circle (minimum bounding circle) over 2D points -----
# implemented from https://www.cs.princeton.edu/~rs/AlgsDS07/18MinDisc.pdf 
# entirely by the AI (GPT-5)<-------

def _distance(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.hypot(dx, dy)

def _is_in_circle(point, circle):
    if circle is None:
        return False
    (cx, cy, r) = circle
    return _distance(point, (cx, cy)) <= r + 1e-12

def _circle_from_two_points(a, b):
    cx = (a[0] + b[0]) / 2.0
    cy = (a[1] + b[1]) / 2.0
    r = _distance(a, b) / 2.0
    return (cx, cy, r)

def _circle_from_three_points(a, b, c):
    # Compute circumcenter of triangle ABC
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-18:
        return None  # Collinear or nearly so
    ax2ay2 = ax * ax + ay * ay
    bx2by2 = bx * bx + by * by
    cx2cy2 = cx * cx + cy * cy
    ux = (ax2ay2 * (by - cy) + bx2by2 * (cy - ay) + cx2cy2 * (ay - by)) / d
    uy = (ax2ay2 * (cx - bx) + bx2by2 * (ax - cx) + cx2cy2 * (bx - ax)) / d
    r = _distance((ux, uy), a)
    return (ux, uy, r)

def smallest_enclosing_circle(array_of_arrays_of_points):
    """Compute the smallest enclosing circle of the union of all points in the input array of arrays of points

    Accepts list of arrays of points, each of which is a lon, lat. Returns (lon, lat, r).
    """
    # Normalize to list of tuples of floats
    normalized = []
    for points_lon_lat in array_of_arrays_of_points:
        for p in points_lon_lat or []:
            if p is None:
                continue
            try:
                lon = float(p[0])
                lat = float(p[1])
            except (ValueError, TypeError, IndexError):
                continue
            normalized.append((lon, lat))

    # De-duplicate while preserving order
    seen = set()
    points = []
    for pt in normalized:
        if pt not in seen:
            seen.add(pt)
            points.append(pt)

    if not points:
        return (0.0, 0.0, 0.0)

    # Trivial cases
    if len(points) == 1:
        lon, lat = points[0]
        return (lon, lat, 0.0)

    # Incremental algorithm (Welzl-style without randomization; fine for small n)
    c = None
    for i, p in enumerate(points):
        if c is None or not _is_in_circle(p, c):
            c = (p[0], p[1], 0.0)
            for j in range(i):
                q = points[j]
                if not _is_in_circle(q, c):
                    c = _circle_from_two_points(p, q)
                    for k in range(j):
                        r = points[k]
                        if not _is_in_circle(r, c):
                            c3 = _circle_from_three_points(p, q, r)
                            if c3 is not None:
                                c = c3
    return c

def parse_pse_file(input_file, rows, file_datetime, is_from_most_recent=True):
    pse_local_timeformat = "%Y/%m/%d %I:%M %p" # e.g. "2025/02/24 06:30 PM"

    try:
        data = json.load(input_file)
    except Exception as e:
        print(f"error parsing pse file: {input_file}. Defaulting to empty list. Exception: {e}")
        data = []
        return

    for outage in data.get("PseMap", []):
        provider = outage.get("DataProvider", {})
        attributes = provider.get("Attributes", [])

        # PSE has a few different attribute names for outage id, so we have to check for all of them
        outage_id = get_attr(attributes, "OutageEventId")
        if(not outage_id):
            outage_id = get_attr(attributes, "Outage ID")
        if(not outage_id):
            outage_id = get_attr(attributes, "Outage ID:")
        if(not outage_id):
            # for a while, PSE used a blank attribute name for outage id
            outage_id = get_attr(attributes, "")
        if(not outage_id or not outage_id.startswith("INC")):
            print(f"outage id '{outage_id}' missing or does not start with INC, skipping")
            # TODO: decide on a consistent way to handle these types of things. Ignore the outage, ignore the file, neither?
            continue

        start_time_json = get_attr(attributes, "StartDate")

        # pse changed the attribute name when introducing the refname field, so we have to 
        # check for both names for start time, est restoration time, and last updated
        if(not start_time_json):
            start_time_json = get_attr(attributes, "Start time")
        # PSE omits the year from the start time, and strptime is threatening to not support that in future
        # so we'll just use the file's year if the datetime string is short enough that it couldn't have the year
        # (in case PSE adds the year later) 
        if(len(start_time_json) <= 14):
            start_time_json = str(file_datetime.year) + "/" + start_time_json # e.g. "01/15 08:00 AM" -> "2025/01/15 08:00 AM"

        start_time = datetime.strptime(start_time_json, pse_local_timeformat)

        est_restoration_time_json = get_attr(attributes, "Est. Restoration time")
        if(not est_restoration_time_json):
            est_restoration_time_json = get_attr(attributes, "Est. restoration time")

        try:
            if(len(est_restoration_time_json) <= 14):
                est_restoration_time_json = str(file_datetime.year) + "/" + est_restoration_time_json # e.g. "01/15 08:00 AM" -> "2025/01/15 08:00 AM
            est_restoration_time = datetime.strptime(est_restoration_time_json, pse_local_timeformat)
        except Exception as e:    
            print(f"error parsing est restoration time: {est_restoration_time_json}. Exception: {e}Defaulting to None")
            est_restoration_time = None

        customers_impacted = int(get_attr(attributes, "Customers impacted"))
        status = get_attr(attributes, "Status")
        cause = get_attr(attributes, "Cause")
        json_polygon = outage.get("Polygon", [])

        # PSE appears to always use a single polygon for each outage
        polygons = []
        polygons.append([])
        for point in json_polygon:
            polygons[0].append([point.get("Longitude"), point.get("Latitude")])
        center_lon, center_lat, radius = smallest_enclosing_circle(polygons)
        
        row = {
            "utility": "pse",
            "outage_id": outage_id,
            "file_datetime": file_datetime.strftime(OUTPUT_TIME_FORMAT),
            "start_time": local_timezone.localize(start_time).astimezone(pytz.utc).strftime(OUTPUT_TIME_FORMAT),
            "customers_impacted": customers_impacted,
            "status": status,
            "cause": cause,
            "est_restoration_time": "none" if est_restoration_time is None else local_timezone.localize(est_restoration_time).astimezone(pytz.utc).strftime(OUTPUT_TIME_FORMAT),
            "polygon_json": json.dumps(polygons),
            "center_lon": center_lon,
            "center_lat": center_lat,
            "radius": radius,
            "isFromMostRecent": is_from_most_recent
        }
        rows.append(row)


def parse_scl_file(input_file, rows, file_datetime, is_from_most_recent=True):
    data = json.load(input_file)

    for outage in data:
        outage_id = outage.get("id")
        start_time = outage.get("startTime")
        customers_impacted = int(outage.get("numPeople"))
        status = outage.get("status")
        cause = outage.get("cause")
        est_restoration_time = outage.get("etrTime")
        rings = outage.get("polygons", {}).get("rings", [])

        # SCL appears to sometimes use multiple polygons (rings) for each outage. 
        # I believe "ring" is a polygon that doesn't have any holes
        polygons = rings
        center_lon, center_lat, radius = smallest_enclosing_circle(polygons)

        row = {
            "utility": "scl",
            "outage_id": outage_id,
            "file_datetime": file_datetime,
            # SCL times are already in UTC as epoch time
            "start_time": datetime.fromtimestamp(start_time/1000, tz=pytz.utc).strftime(OUTPUT_TIME_FORMAT),
            "customers_impacted": customers_impacted,
            "status": status,
            "cause": cause,
            "est_restoration_time": datetime.fromtimestamp(est_restoration_time/1000, tz=pytz.utc).strftime(OUTPUT_TIME_FORMAT),
            "polygon_json": json.dumps(polygons),
            "center_lon": center_lon,
            "center_lat": center_lat,
            "radius": radius,
            "isFromMostRecent": is_from_most_recent
        }
        rows.append(row)

def parse_snopud_file(input_file, rows, file_datetime, is_from_most_recent=True):
    try:
        root = parser.parse(input_file).getroot()
    except Exception as e:
        if "Document is empty" in str(e):
            print(f"Empty XML document detected, skipping file.")
            return
        else:
            # Re-raise other exceptions to see what's actually going wrong
            raise e
    
    # Collect all placemark data into a list for DataFrame creation
    placemark_data = []
    
    for pm in root.Document.Folder.Placemark:
        # first get the raw data from the file
        start_time = find_element_in_kml_extended_data(pm.ExtendedData, "StartUTC")
        customers_impacted = find_element_in_kml_extended_data(pm.ExtendedData, "EstCustomersOut")
        status = find_element_in_kml_extended_data(pm.ExtendedData, "OutageStatus")
        cause = find_element_in_kml_extended_data(pm.ExtendedData, "Cause")
        est_restoration_time = find_element_in_kml_extended_data(pm.ExtendedData, "EstimatedRestorationUTC")
        polygon = pm.Polygon.outerBoundaryIs.LinearRing.coordinates

        # snopud sometimes leaves entries with -1 for customers impacted and invalid dates and other fields
        # I assume this either means they're still investigating, or they're just using placeholder data for some 
        # other reason. We'll just skip them
        if customers_impacted == -1:
            print(f"skipping outage {pm.name} because it has -1 for customers impacted")
            continue

        # Parse start time for grouping
        start_time_parsed = datetime.fromisoformat(start_time.text).replace(tzinfo=None)
        
        # Parse polygon coordinates
        polygon_points = parse_kml_coordinate_string(polygon.text if hasattr(polygon, 'text') else str(polygon))
        
        placemark_data.append({
            'placemark_name': pm.name,
            'start_time_parsed': start_time_parsed,
            'start_time_key': start_time_parsed.strftime("%Y%m%d%H%M%S"),
            'customers_impacted': int(customers_impacted),
            'status': status,
            'cause': cause,
            'est_restoration_time': est_restoration_time,
            'polygon_points': polygon_points
        })
    
    if not placemark_data:
        return
    
    # Convert to DataFrame and group by start time
    df = pd.DataFrame(placemark_data)
    
    # Group by start time and aggregate
    grouped = df.groupby('start_time_key').agg({
        'placemark_name': 'first',  # Use first name for outage ID
        'start_time_parsed': 'first',  # All should be the same
        'customers_impacted': 'sum',  # Sum customers across all placemarks
        'status': 'first',  # Should be same for all
        'cause': 'first',   # Should be same for all
        'est_restoration_time': 'first',  # Should be same for all
        'polygon_points': lambda x: list(x)  # Collect all polygons
    }).reset_index()
    
    # Process each group to create combined outages
    for _, row in grouped.iterrows():
        # Create outage ID from the start time
        outage_id = row['start_time_parsed'].strftime("%Y%m%d%H%M%S")
        
        # Get all polygons for this group
        all_polygons = row['polygon_points']
        
        # Compute smallest enclosing circle for all polygons combined
        center_lon, center_lat, radius = smallest_enclosing_circle(all_polygons)
        
        # Handle restoration time
        try:
            est_restoration_time_string = datetime.fromisoformat(row['est_restoration_time'].text).replace(tzinfo=None).strftime(OUTPUT_TIME_FORMAT)
            logging.info(f"est restoration time: {est_restoration_time_string}")
        except Exception as e:    
            print(f"error parsing est restoration time: {row['est_restoration_time'].text}. Exception: {e}. \n Defaulting to None")
            est_restoration_time_string = "None"
        
        # Log combination info if multiple placemarks
        if len(all_polygons) > 1:
            print(f"Combining {len(all_polygons)} placemarks with start time {row['start_time_key']}")
        
        row_data = {
            "utility": "snopud",
            "outage_id": outage_id,
            "file_datetime": file_datetime.strftime(OUTPUT_TIME_FORMAT),
            "start_time": row['start_time_parsed'].strftime(OUTPUT_TIME_FORMAT),
            "customers_impacted": row['customers_impacted'],
            "status": row['status'],
            "cause": row['cause'],
            "est_restoration_time": est_restoration_time_string,
            "polygon_json": json.dumps(all_polygons),
            "center_lon": center_lon,
            "center_lat": center_lat,
            "radius": radius,
            "isFromMostRecent": is_from_most_recent
        }
        rows.append(row_data)

def parse_pge_file(input_file, rows, file_datetime, is_from_most_recent=True):
    """Parse PG&E outage data from JSON files.
    
    PG&E data contains point coordinates rather than polygons, so we create a small
    circular polygon around each point for consistency with other utilities.
    """
    try:
        data = json.load(input_file)
    except Exception as e:
        print(f"error parsing pge file: {input_file}. Defaulting to empty list. Exception: {e}")
        data = []

    for outage in data.get("features", []):
        outage_attributes = outage.get("attributes", {})
        outage_id = outage_attributes.get("OUTAGE_ID")
        start_time_ms = outage_attributes.get("OUTAGE_START")
        customers_impacted = outage_attributes.get("EST_CUSTOMERS", 0)
        status = outage_attributes.get("CREW_CURRENT_STATUS")
        cause = outage_attributes.get("OUTAGE_CAUSE")
        est_restoration_time_ms = outage_attributes.get("CURRENT_ETOR")
        outage_geometry = outage.get("geometry", {})
        x = outage_geometry.get("x")
        y = outage_geometry.get("y")
        
        # Convert from EPSG:3857 (Web Mercator) to EPSG:4326 (WGS84 lat/long)
        # TODO: consider doing this on the larger dataframe so it's more natural/efficient
        if x is not None and y is not None:
            # Create a GeoDataFrame with the point in EPSG:3857
            point_gdf = gpd.GeoDataFrame([1], geometry=[gpd.points_from_xy([x], [y])[0]], crs='EPSG:3857')
            # Transform to EPSG:4326 (WGS84)
            point_gdf = point_gdf.to_crs('EPSG:4326')
            # Extract the transformed coordinates
            lon = point_gdf.geometry.x.iloc[0]
            lat = point_gdf.geometry.y.iloc[0]
            # print(f"before EPSG conversion: {x}, {y}")
            # print(f"after EPSG conversion: {lon}, {lat}")
        else:
            lat = None
            lon = None

        # Skip outages with missing essential data
        # TODO: add log levels and logging that's saved to the end
        if not outage_id or not start_time_ms or lat is None or lon is None:
            print(f"ALERT: skipping outage {outage_id} because it is missing essential data")
            print(f"outage properties: {outage_attributes}")
            continue

        # Convert epoch milliseconds to datetime
        start_time = datetime.fromtimestamp(start_time_ms / 1000, tz=pytz.utc)
        est_restoration_time = None
        if est_restoration_time_ms:
            est_restoration_time = datetime.fromtimestamp(est_restoration_time_ms / 1000, tz=pytz.utc)

        # Create a small circular polygon around the point coordinates
        # Use a radius of approximately 0.001 degrees (roughly 100 meters)
        # TODO: do we really need this? Or just have polygon-less outages?
        radius_degrees = 0.001
        num_points = 8  # Create an 8-sided polygon
        
        polygon_points = []
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            delta_lon = radius_degrees * math.cos(angle)
            delta_lat = radius_degrees * math.sin(angle)
            polygon_points.append([lon + delta_lon, lat + delta_lat])
        
        # Close the polygon by adding the first point again
        polygon_points.append(polygon_points[0])
        
        polygons = [polygon_points]
        center_lon = lon
        center_lat = lat
        radius = .05 # a twentieth of a mile, very roughly the same 100 meters as our fake polygon

        row = {
            "utility": "pge",
            "outage_id": outage_id,
            "file_datetime": file_datetime.strftime(OUTPUT_TIME_FORMAT),
            "start_time": start_time.strftime(OUTPUT_TIME_FORMAT),
            "customers_impacted": customers_impacted,
            "status": status,
            "cause": cause,
            "est_restoration_time": "none" if est_restoration_time is None else est_restoration_time.strftime(OUTPUT_TIME_FORMAT),
            "polygon_json": json.dumps(polygons),
            "center_lon": center_lon,
            "center_lat": center_lat,
            "radius": radius,
            "isFromMostRecent": is_from_most_recent
        }
        rows.append(row)

def calculate_expected_length_minutes(update_time, est_restoration_time):
    """
    Calculate the expected length of an outage in minutes.
    Returns the difference between estimated restoration time and most recent update time.
    """

    try:
        if pd.isna(update_time) or pd.isna(est_restoration_time):
            return None
        
        # Convert to datetime if they're strings
        # temporarily handle the none case. But long term, these shouldn't be strings
        # TODO: make them datetime objects
        if isinstance(update_time, str):
            if update_time == "none":
                return None
            else:
                update_time = pd.to_datetime(update_time)
        if isinstance(est_restoration_time, str):
            if est_restoration_time == "none":
                return None
            else:
                est_restoration_time = pd.to_datetime(est_restoration_time)
        
        # Calculate difference in minutes
        time_diff = est_restoration_time - update_time
        return int(time_diff.total_seconds() / 60)
    except Exception as e:
        print(f"Error calculating expected length: {e}")
        print(f"   update_time: {update_time}")
        print(f"   est_restoration_time: {est_restoration_time}")
        return None

def calculate_active_duration_minutes(start_time, current_time):
    """
    Calculate how long an outage has been active in minutes.
    Returns the difference between current time and start time.
    """
    try:        
        # Convert to datetime if it's a string
        start_time = pd.to_datetime(start_time)
        current_time = pd.to_datetime(current_time)
        
        # Calculate difference in minutes
        time_diff = current_time - start_time
        return int(time_diff.total_seconds() / 60)
    except Exception as e:
        print(f"Error calculating active duration: {e}")
        return None

def reverse_geocode(lat, lon, api_key=None):
    """Reverse geocode coordinates to get formatted location information."""

    # State abbreviation lookup table (lowercase for case-insensitive comparison)
    STATE_ABBREVIATIONS = {
        "alabama": "AL",
        "alaska": "AK",
        "arizona": "AZ",
        "arkansas": "AR",
        "california": "CA",
        "colorado": "CO",
        "connecticut": "CT",
        "delaware": "DE",
        "florida": "FL",
        "georgia": "GA",
        "hawaii": "HI",
        "idaho": "ID",
        "illinois": "IL",
        "indiana": "IN",
        "iowa": "IA",
        "kansas": "KS",
        "kentucky": "KY",
        "louisiana": "LA",
        "maine": "ME",
        "maryland": "MD",
        "massachusetts": "MA",
        "michigan": "MI",
        "minnesota": "MN",
        "mississippi": "MS",
        "missouri": "MO",
        "montana": "MT",
        "nebraska": "NE",
        "nevada": "NV",
        "new hampshire": "NH",
        "new jersey": "NJ",
        "new mexico": "NM",
        "new york": "NY",
        "north carolina": "NC",
        "north dakota": "ND",
        "ohio": "OH",
        "oklahoma": "OK",
        "oregon": "OR",
        "pennsylvania": "PA",
        "rhode island": "RI",
        "south carolina": "SC",
        "south dakota": "SD",
        "tennessee": "TN",
        "texas": "TX",
        "utah": "UT",
        "vermont": "VT",
        "virginia": "VA",
        "washington": "WA",
        "west virginia": "WV",
        "wisconsin": "WI",
        "wyoming": "WY",
        "district of columbia": "DC",
        "american samoa": "AS",
        "guam": "GU",
        "northern mariana islands": "MP",
        "puerto rico": "PR",
        "u.s. virgin islands": "VI"
    }

    # Create Google Maps URL
    maps_url = f"https://maps.google.com/maps?q={lat:.6f},{lon:.6f}"

    try:
        if api_key:
            url = f"https://geocode.maps.co/reverse?lat={lat}&lon={lon}&api_key={api_key}"
        else:
            # Fallback to google URL if no API key provided
            return maps_url

        response = requests.get(url)
        # sleep for 1 second to avoid rate limiting
        time.sleep(1)
        response.raise_for_status()
        
        data = response.json()
        address = data.get('address', {})
        
        suburb = address.get('suburb', '')
        city = address.get('city', '') or address.get('town', '')
        county = address.get('county', '')
        state = address.get('state', '')
        
        # Convert state to abbreviation if available (case-insensitive)
        state_abbr = STATE_ABBREVIATIONS[state.lower()] if state else ''
  
        # Format location information
        if suburb and city and state_abbr:
            location_info = f"[{suburb}, {city}, {state_abbr}]({maps_url})"
        elif city and state_abbr:
            location_info = f"[{city}, {state_abbr}]({maps_url})"
        elif county and state_abbr:
            location_info = f"[{county}, {state_abbr}]({maps_url})"
        elif state_abbr:
            location_info = f"[{state_abbr}]({maps_url})"
        else:
            location_info = maps_url
        
        return location_info
    except Exception as e:
        print(f"Error reverse geocoding coordinates {lat}, {lon}: {e}")
        # Fallback to just the Google Maps URL
        return maps_url


def get_filename_suffix_for_utility(utility):
    # set up the filename suffix based on utility. We'll use this to help parse the date/time of
    # the update out of the file name
    if (utility == "pse"):
        filename_suffix = "-pse-events.json"
    elif (utility == "scl"):
        filename_suffix = "-scl-events.json"
    elif (utility == "snopud"):
        filename_suffix = "-KMLOutageAreas.xml"
    elif (utility == "pge"):
        filename_suffix = "-pge-events.json"
    else:
        filename_suffix = ""
    return filename_suffix
