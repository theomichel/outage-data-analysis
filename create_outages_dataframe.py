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
import outage_utils


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

def main():
    parser = argparse.ArgumentParser(description="Collect PSE outage updates from JSON files into a CSV. Can also be run on a single file. Assumes that input file names start with the date that the file was created, in %Y-%m-%dT%H%M%S%f form.")
    parser.add_argument('-d', '--directory', type=str, default='.', help='Directory containing files that match the pattern')
    parser.add_argument('-u', '--utility', type=str, required=True, help='Utility that the input came from. Values are pse, scl, or snopud')
    parser.add_argument('-s', '--singlefile', type=str, help='Special case for loading a single file. If provided, will ignore the directory argument.')
    parser.add_argument('-l', '--latestfiles', action='store_true', help='Process the two most recent files in the directory. Can only be used with --directory.')
    parser.add_argument('-o', '--output_file', type=str, help='output file name. If not provided, will default to outage_updates.csv')
    args = parser.parse_args()

    print(f"====== create_outages_dataframe.py starting =======")

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
    elif (args.utility == "pge"):
        filename_suffix = "-pge-events.json"

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
                files = []
                print(f"Only 1 file found ({os.path.basename(all_files[0])}) and latest files requested. Skipping processing.")
            else:
                files = []
                print("No files found matching pattern")
        else:
            files = all_files
    rows = []

    for file_index, file in enumerate(files):
        # Extract date and time from filename
        print(f"====== starting processing for file =======")
        print(f"file: {file}")
        basename = os.path.basename(file)
        date_time_part = basename.split(filename_suffix)[0]
        # TODO: for some reason, the first file created by expand.py has a slightly different format. Figure out why and address there?
        # filenames are in GMT, stick with that throughout
        gmt_file_datetime = datetime.strptime(date_time_part, "%Y-%m-%dT%H%M%S%f")

        # Determine if this is the most recent file (files are sorted in reverse order, so index 0 is most recent)
        is_from_most_recent = (file_index == 0)

        with open(file, "r", encoding="utf-8") as f:
            if(args.utility == "pse"):
                outage_utils.parse_pse_file(f, rows, gmt_file_datetime, is_from_most_recent)
            elif (args.utility == "scl"):
                outage_utils.parse_scl_file(f, rows, gmt_file_datetime, is_from_most_recent)
            elif (args.utility == "snopud"):
                outage_utils.parse_snopud_file(f, rows, gmt_file_datetime, is_from_most_recent)
            elif (args.utility == "pge"):
                outage_utils.parse_pge_file(f, rows, gmt_file_datetime, is_from_most_recent)
            else:
                print("no utility specified, will not parse")

        print(f"====== completed processing for file =======")


    # Create DataFrame
    if rows:
        df = pd.DataFrame(rows)
        out_csv = args.output_file if args.output_file else "outage_updates.csv"
        df.to_csv(out_csv, index=False)
        print(f"Aggregated {len(df)} outage updates into {out_csv}")
    else:
        print("No outage data found to aggregate.")
        # Create empty CSV file with correct columns
        out_csv = args.output_file if args.output_file else "outage_updates.csv"
        empty_df = pd.DataFrame(columns=[
            "utility",
            "outage_id", 
            "file_datetime",
            "start_time",
            "customers_impacted",
            "status",
            "cause",
            "est_restoration_time",
            "polygon_json",
            "center_lon",
            "center_lat",
            "radius",
            "isFromMostRecent"
        ])
        empty_df.to_csv(out_csv, index=False)
        print(f"Created empty CSV file with correct columns: {out_csv}")

    print(f"====== create_outages_dataframe.py completed =======")

if __name__ == "__main__":
    main()
