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

def parse_pse_file(input_file, rows, file_datetime):
    pse_local_timeformat = "%m/%d %I:%M %p" # e.g. "02/24 06:30 PM"

    try:
        data = json.load(input_file)
    except Exception as e:
        print(f"error parsing pse file: {input_file}. Defaulting to empty list")
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
        start_time = datetime.strptime(start_time_json, pse_local_timeformat)
        # PSE omits the year from the start time, so we have to pick one. Assume it's the same year as the file
        start_time = start_time.replace(year=file_datetime.year)

        est_restoration_time_json = get_attr(attributes, "Est. Restoration time")
        if(not est_restoration_time_json):
            est_restoration_time_json = get_attr(attributes, "Est. restoration time")

        try:
            est_restoration_time = datetime.strptime(est_restoration_time_json, pse_local_timeformat)
            # PSE omits the year from the restoration time, so we have to pick one. Assume it's the same year as the file
            est_restoration_time = est_restoration_time.replace(year=file_datetime.year)
        except Exception as e:    
            print(f"error parsing est restoration time: {est_restoration_time_json}. Exception: {e}Defaulting to None")
            est_restoration_time = None

        customers_impacted = get_attr(attributes, "Customers impacted")
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
            "radius": radius
        }
        rows.append(row)


def parse_scl_file(input_file, rows, file_datetime):
    data = json.load(input_file)

    for outage in data:
        outage_id = outage.get("id")
        start_time = outage.get("startTime")
        customers_impacted = outage.get("numPeople")
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
            # SCL times are in PST as epoch time, so they need to be converted to UTC
            "start_time": local_timezone.localize(datetime.fromtimestamp(start_time/1000)).astimezone(pytz.utc).strftime(OUTPUT_TIME_FORMAT),
            "customers_impacted": customers_impacted,
            "status": status,
            "cause": cause,
            "est_restoration_time": local_timezone.localize(datetime.fromtimestamp(est_restoration_time/1000)).astimezone(pytz.utc).strftime(OUTPUT_TIME_FORMAT),
            "polygon_json": json.dumps(polygons),
            "center_lon": center_lon,
            "center_lat": center_lat,
            "radius": radius
        }
        rows.append(row)

def parse_snopud_file(input_file, rows, file_datetime):
    try:
        root = parser.parse(input_file).getroot()
    except Exception as e:
        if "Document is empty" in str(e):
            print(f"Empty XML document detected, skipping file.")
            return
        else:
            # Re-raise other exceptions to see what's actually going wrong
            raise e
    
    for pm in root.Document.Folder.Placemark:
        # first get the raw data from the file
        start_time = find_element_in_kml_extended_data(pm.ExtendedData, "StartUTC")
        customers_impacted = find_element_in_kml_extended_data(pm.ExtendedData, "EstCustomersOut")
        status = find_element_in_kml_extended_data(pm.ExtendedData, "OutageStatus")
        cause = find_element_in_kml_extended_data(pm.ExtendedData, "Cause")
        est_restoration_time = find_element_in_kml_extended_data(pm.ExtendedData, "EstimatedRestorationUTC")
        polygon = pm.Polygon.outerBoundaryIs.LinearRing.coordinates

        # snopud doesn't have a unique id for each outage, so we'll use the place + start datetime
        outage_id = str(pm.name) + datetime.fromisoformat(start_time.text).replace(tzinfo=None).strftime("%Y%m%d%H%M%S")

        # snopud sometimes leaves entries with -1 for customers impacted and invalid dates and other fields
        # I assume this either means they're still investigating, or they're just using placeholder data for some 
        # other reason. We'll just skip them
        if customers_impacted == -1:
            print(f"skipping outage {outage_id} because it has -1 for customers impacted")
            continue

        # then mold it into a row within the dataframe
   
        # snopud uses KML, in which a polygon is a single "island" which can have multiple cut-outs within it
        # (https://developers.google.com/kml/documentation/kmlreference#outerboundaryis)
        # but snopud doesn't seem to use cut-outs, so we can just use the outer boundary
        # However, the KML points have an altitude, which we don't care about so we'll strip out
        polygon_points = parse_kml_coordinate_string(polygon.text if hasattr(polygon, 'text') else str(polygon))
        polygons = []
        polygons.append(polygon_points)

        # Compute smallest enclosing circle center as point of interest from JSON array
        center_lon, center_lat, radius = smallest_enclosing_circle(polygons)
   
        pacific_timezone = pytz.timezone('US/Pacific')

        # snopud sometimes puts placeholder text in the est restoration time field, in which case we convert to none
        try:
            # otherwise, snopud times are TZ-aware UTC, and we want unaware UTC, so naivify!
            est_restoration_time_string = datetime.fromisoformat(est_restoration_time.text).replace(tzinfo=None).strftime(OUTPUT_TIME_FORMAT)
            logging.info(f"est restoration time: {est_restoration_time_string}")
        except Exception as e:    
            print(f"error parsing est restoration time: {est_restoration_time.text}. Exception: {e}. \n Defaulting to None")
            est_restoration_time_string = "None"

        row = {
            "utility": "snopud",
            "outage_id": outage_id,
            "file_datetime": file_datetime.strftime(OUTPUT_TIME_FORMAT),
            "start_time": datetime.fromisoformat(start_time.text).replace(tzinfo=None).strftime(OUTPUT_TIME_FORMAT),
            "customers_impacted": customers_impacted,
            "status": status,
            "cause": cause,
            "est_restoration_time": est_restoration_time_string,
            "polygon_json": json.dumps(polygons),
            "center_lon": center_lon,
            "center_lat": center_lat,
            "radius": radius
        }
        rows.append(row)
    
def main():
    parser = argparse.ArgumentParser(description="Collect PSE outage updates from JSON files into a CSV. Can also be run on a single file. Assumes that input file names start with the date that the file was created, in %Y-%m-%dT%H%M%S%f form.")
    parser.add_argument('-d', '--directory', type=str, default='.', help='Directory containing files that match the pattern')
    parser.add_argument('-u', '--utility', type=str, required=True, help='Utility that the input came from. Values are pse, scl, or snopud')
    parser.add_argument('-s', '--singlefile', type=str, help='Special case for loading a single file. If provided, will ignore the directory argument.')
    parser.add_argument('-l', '--latestfiles', action='store_true', help='Process the two most recent files in the directory. Can only be used with --directory.')
    parser.add_argument('-o', '--output_file', type=str, help='output file name. If not provided, will default to outage_updates.csv')
    args = parser.parse_args()

    # Validation: --latestfiles can only be used with --directory (not with --singlefile)
    if args.latestfiles and args.singlefile:
        print("Error: --latestfiles cannot be used with --singlefile")
        return

    # set up the filename suffix based on utility. We'll use this to help parse the date/time of
    # the update out of the file name
    if (args.utility == "pse"):
        filename_suffix = "-pse-events.json"
    elif (args.utility == "scl"):
        filename_suffix = "-scl-events.json"
    elif (args.utility == "snopud"):
        filename_suffix = "-KMLOutageAreas.xml"

    # pattern used to find all the files
    if (args.singlefile):
        PATTERN = args.singlefile
        files = [PATTERN]
    else:
        PATTERN = os.path.join(args.directory, "*"+filename_suffix)
        print(f"file pattern {PATTERN}")
        all_files = sorted(glob.glob(PATTERN), reverse=True)
        
        if args.latestfiles:
            # Find the two most recent files by datetime embedded in filename
            if len(all_files) >= 2:
                files = all_files[:2]
                print(f"Processing the 2 most recent files (by filename datetime):")
                for i, file in enumerate(files, 1):
                    print(f"{i}. {os.path.basename(file)}")
            elif len(all_files) == 1:
                files = all_files
                print(f"Only 1 file found, processing: {os.path.basename(all_files[0])}")
            else:
                files = []
                print("No files found matching pattern")
        else:
            files = all_files
    rows = []

    for file in files:
        # Extract date and time from filename
        print(f"==============================================================================")
        print(f"processing file {file}")
        basename = os.path.basename(file)
        date_time_part = basename.split(filename_suffix)[0]
        # TODO: for some reason, the first file created by expand.py has a slightly different format. Figure out why and address there?
        # filenames are in GMT, stick with that throughout
        gmt_file_datetime = datetime.strptime(date_time_part, "%Y-%m-%dT%H%M%S%f")


        with open(file, "r", encoding="utf-8") as f:
            if(args.utility == "pse"):
                parse_pse_file(f, rows, gmt_file_datetime)
            elif (args.utility == "scl"):
                parse_scl_file(f, rows, gmt_file_datetime)
            elif (args.utility == "snopud"):
                parse_snopud_file(f, rows, gmt_file_datetime)
            else:
                print("no utility specified, will not parse")

    # Create DataFrame
    if rows:
        df = pd.DataFrame(rows)
        out_csv = args.output_file if args.output_file else "outage_updates.csv"
        df.to_csv(out_csv, index=False)
        print(f"Aggregated {len(df)} outage updates into {out_csv}")
    else:
        print("No outage data found to aggregate.")

if __name__ == "__main__":
    main()
