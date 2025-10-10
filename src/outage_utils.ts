import * as fs from 'fs';
import axios from 'axios';
import { XMLParser } from 'fast-xml-parser';
import proj4 from 'proj4';

const OUTPUT_TIME_FORMAT = 'YYYY-MM-DD HH:mm:ss';

export interface OutageRow {
  utility: string;
  outage_id: string;
  file_datetime: string;
  start_time: string;
  customers_impacted: number;
  status: string;
  cause: string;
  est_restoration_time: string;
  polygon_json: string;
  center_lon: number;
  center_lat: number;
  radius: number;
  isFromMostRecent: boolean;
  elapsed_time_minutes?: number;
  expected_length_minutes?: number;
  zipcode?: string | null;
  notification_reason?: string;
}

// State abbreviation lookup table
const STATE_ABBREVIATIONS: { [key: string]: string } = {
  'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
  'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
  'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
  'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
  'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
  'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
  'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
  'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
  'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
  'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
  'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
  'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
  'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC',
  'american samoa': 'AS', 'guam': 'GU', 'northern mariana islands': 'MP',
  'puerto rico': 'PR', 'u.s. virgin islands': 'VI'
};

// Helper function to get attribute from PSE array
function getAttr(attributes: any[], attributeName: string): any {
  for (const attr of attributes) {
    if (attr.RefName === attributeName || attr.Name === attributeName) {
      return attr.Value;
    }
  }
  return null;
}

// Helper to find element in KML extended data
function findElementInKmlExtendedData(extendedData: any, elementName: string): any {
  if (!extendedData?.Data) return null;

  for (const dataElement of extendedData.Data) {
    if (dataElement['@_name'] === elementName) {
      return dataElement['#text'];
    }
  }
  throw new Error(`element not found in KML: ${elementName}`);
}

// Parse KML coordinate string
function parseKmlCoordinateString(coordinatesText: string | null | undefined): [number, number][] {
  if (!coordinatesText) return [];

  const tokens = coordinatesText.trim().split(/\s+/);
  const points: [number, number][] = [];

  for (const token of tokens) {
    const parts = token.split(',');
    if (parts.length >= 2) {
      try {
        const lon = parseFloat(parts[0]);
        const lat = parseFloat(parts[1]);
        points.push([lon, lat]);
      } catch {
        continue;
      }
    }
  }

  return points;
}

// Distance between two points
function distance(a: [number, number], b: [number, number]): number {
  const dx = a[0] - b[0];
  const dy = a[1] - b[1];
  return Math.sqrt(dx * dx + dy * dy);
}

// Check if point is in circle
function isInCircle(point: [number, number], circle: [number, number, number] | null): boolean {
  if (!circle) return false;
  const [cx, cy, r] = circle;
  return distance(point, [cx, cy]) <= r + 1e-12;
}

// Circle from two points
function circleFromTwoPoints(a: [number, number], b: [number, number]): [number, number, number] {
  const cx = (a[0] + b[0]) / 2.0;
  const cy = (a[1] + b[1]) / 2.0;
  const r = distance(a, b) / 2.0;
  return [cx, cy, r];
}

// Circle from three points
function circleFromThreePoints(
  a: [number, number],
  b: [number, number],
  c: [number, number]
): [number, number, number] | null {
  const [ax, ay] = a;
  const [bx, by] = b;
  const [cx, cy] = c;

  const d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
  if (Math.abs(d) < 1e-18) return null;

  const ax2ay2 = ax * ax + ay * ay;
  const bx2by2 = bx * bx + by * by;
  const cx2cy2 = cx * cx + cy * cy;

  const ux = (ax2ay2 * (by - cy) + bx2by2 * (cy - ay) + cx2cy2 * (ay - by)) / d;
  const uy = (ax2ay2 * (cx - bx) + bx2by2 * (ax - cx) + cx2cy2 * (bx - ax)) / d;
  const r = distance([ux, uy], a);

  return [ux, uy, r];
}

// Smallest enclosing circle
export function smallestEnclosingCircle(arrayOfArraysOfPoints: [number, number][][]): [number, number, number] {
  const normalized: [number, number][] = [];

  for (const pointsLonLat of arrayOfArraysOfPoints) {
    for (const p of pointsLonLat || []) {
      if (p === null || p === undefined) continue;
      try {
        const lon = p[0];
        const lat = p[1];
        if (typeof lon === 'number' && typeof lat === 'number' && !isNaN(lon) && !isNaN(lat)) {
          normalized.push([lon, lat]);
        }
      } catch {
        continue;
      }
    }
  }

  // De-duplicate
  const seen = new Set<string>();
  const points: [number, number][] = [];
  for (const pt of normalized) {
    const key = `${pt[0]},${pt[1]}`;
    if (!seen.has(key)) {
      seen.add(key);
      points.push(pt);
    }
  }

  if (points.length === 0) return [0.0, 0.0, 0.0];
  if (points.length === 1) return [points[0][0], points[0][1], 0.0];

  // Incremental algorithm
  let c: [number, number, number] | null = null;
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    if (c === null || !isInCircle(p, c)) {
      c = [p[0], p[1], 0.0];
      for (let j = 0; j < i; j++) {
        const q = points[j];
        if (!isInCircle(q, c)) {
          c = circleFromTwoPoints(p, q);
          for (let k = 0; k < j; k++) {
            const r = points[k];
            if (!isInCircle(r, c)) {
              const c3 = circleFromThreePoints(p, q, r);
              if (c3 !== null) {
                c = c3;
              }
            }
          }
        }
      }
    }
  }

  return c || [0.0, 0.0, 0.0];
}

// Format date to OUTPUT_TIME_FORMAT
function formatDate(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  const hours = String(date.getUTCHours()).padStart(2, '0');
  const minutes = String(date.getUTCMinutes()).padStart(2, '0');
  const seconds = String(date.getUTCSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

// Parse PSE file
export function parsePseFile(filePath: string, rows: OutageRow[], fileDateTime: Date, isFromMostRecent = true): void {
  const pseLocalTimeformat = 'YYYY/MM/DD hh:mm A'; // e.g. "2025/02/24 06:30 PM"

  let data: any;
  try {
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    data = JSON.parse(fileContent);
  } catch (e) {
    console.log(`error parsing pse file: ${filePath}. Defaulting to empty list. Exception: ${e}`);
    return;
  }

  for (const outage of data.PseMap || []) {
    const provider = outage.DataProvider || {};
    const attributes = provider.Attributes || [];

    let outage_id = getAttr(attributes, 'OutageEventId');
    if (!outage_id) outage_id = getAttr(attributes, 'Outage ID');
    if (!outage_id) outage_id = getAttr(attributes, 'Outage ID:');
    if (!outage_id) outage_id = getAttr(attributes, '');

    if (!outage_id || !outage_id.startsWith('INC')) {
      console.log(`outage id '${outage_id}' missing or does not start with INC, skipping`);
      continue;
    }

    let startTimeJson = getAttr(attributes, 'StartDate');
    if (!startTimeJson) startTimeJson = getAttr(attributes, 'Start time');

    if (startTimeJson.length <= 14) {
      startTimeJson = String(fileDateTime.getUTCFullYear()) + '/' + startTimeJson;
    }

    const startTime = parsePseDateTime(startTimeJson);

    let estRestorationTimeJson = getAttr(attributes, 'Est. Restoration time');
    if (!estRestorationTimeJson) estRestorationTimeJson = getAttr(attributes, 'Est. restoration time');

    let estRestorationTime: Date | null = null;
    try {
      if (estRestorationTimeJson.length <= 14) {
        estRestorationTimeJson = String(fileDateTime.getUTCFullYear()) + '/' + estRestorationTimeJson;
      }
      estRestorationTime = parsePseDateTime(estRestorationTimeJson);
    } catch (e) {
      console.log(`error parsing est restoration time: ${estRestorationTimeJson}. Exception: ${e}. Defaulting to None`);
    }

    const customersImpacted = parseInt(getAttr(attributes, 'Customers impacted'));
    const status = getAttr(attributes, 'Status');
    const cause = getAttr(attributes, 'Cause');
    const jsonPolygon = outage.Polygon || [];

    const polygons: [number, number][][] = [[]];
    for (const point of jsonPolygon) {
      polygons[0].push([point.Longitude, point.Latitude]);
    }

    const [centerLon, centerLat, radius] = smallestEnclosingCircle(polygons);

    rows.push({
      utility: 'pse',
      outage_id,
      file_datetime: formatDate(fileDateTime),
      start_time: formatDate(startTime),
      customers_impacted: customersImpacted,
      status,
      cause,
      est_restoration_time: estRestorationTime === null ? 'none' : formatDate(estRestorationTime),
      polygon_json: JSON.stringify(polygons),
      center_lon: centerLon,
      center_lat: centerLat,
      radius,
      isFromMostRecent
    });
  }
}

// Parse PSE datetime format
function parsePseDateTime(dateStr: string): Date {
  // Format: "2025/02/24 06:30 PM"
  const match = dateStr.match(/(\d{4})\/(\d{2})\/(\d{2})\s+(\d{1,2}):(\d{2})\s+(AM|PM)/);
  if (!match) throw new Error(`Invalid PSE date format: ${dateStr}`);

  const [, year, month, day, hour, minute, ampm] = match;
  let hours = parseInt(hour);
  if (ampm === 'PM' && hours !== 12) hours += 12;
  if (ampm === 'AM' && hours === 12) hours = 0;

  // PSE times are in Pacific time, convert to UTC
  const localDate = new Date(parseInt(year), parseInt(month) - 1, parseInt(day), hours, parseInt(minute));
  // Add 8 hours for PST (simplified - doesn't handle DST)
  return new Date(localDate.getTime() + 8 * 60 * 60 * 1000);
}

// Parse SCL file
export function parseSclFile(filePath: string, rows: OutageRow[], fileDateTime: Date, isFromMostRecent = true): void {
  const fileContent = fs.readFileSync(filePath, 'utf-8');
  const data = JSON.parse(fileContent);

  for (const outage of data) {
    const outageId = outage.id;
    const startTime = new Date(outage.startTime);
    const customersImpacted = parseInt(outage.numPeople);
    const status = outage.status;
    const cause = outage.cause;
    const estRestorationTime = new Date(outage.etrTime);
    const rings = outage.polygons?.rings || [];

    const polygons = rings;
    const [centerLon, centerLat, radius] = smallestEnclosingCircle(polygons);

    rows.push({
      utility: 'scl',
      outage_id: outageId,
      file_datetime: formatDate(fileDateTime),
      start_time: formatDate(startTime),
      customers_impacted: customersImpacted,
      status,
      cause,
      est_restoration_time: formatDate(estRestorationTime),
      polygon_json: JSON.stringify(polygons),
      center_lon: centerLon,
      center_lat: centerLat,
      radius,
      isFromMostRecent
    });
  }
}

// Parse SnoPUD file
export function parseSnopudFile(filePath: string, rows: OutageRow[], fileDateTime: Date, isFromMostRecent = true): void {
  const parser = new XMLParser({
    ignoreAttributes: false,
    attributeNamePrefix: '@_'
  });

  let root: any;
  try {
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const parsed = parser.parse(fileContent);
    root = parsed.kml?.Document || parsed.Document;
  } catch (e) {
    if (String(e).includes('Document is empty')) {
      console.log('Empty XML document detected, skipping file.');
      return;
    }
    throw e;
  }

  const placemarkData: any[] = [];
  const placemarks = root?.Folder?.Placemark;
  if (!placemarks) return;

  const placemarksArray = Array.isArray(placemarks) ? placemarks : [placemarks];

  for (const pm of placemarksArray) {
    const startTime = findElementInKmlExtendedData(pm.ExtendedData, 'StartUTC');
    const customersImpacted = parseInt(findElementInKmlExtendedData(pm.ExtendedData, 'EstCustomersOut'));
    const status = findElementInKmlExtendedData(pm.ExtendedData, 'OutageStatus');
    const cause = findElementInKmlExtendedData(pm.ExtendedData, 'Cause');
    const estRestorationTime = findElementInKmlExtendedData(pm.ExtendedData, 'EstimatedRestorationUTC');
    const polygon = pm.Polygon?.outerBoundaryIs?.LinearRing?.coordinates;

    if (customersImpacted === -1) {
      console.log(`skipping outage ${pm.name} because it has -1 for customers impacted`);
      continue;
    }

    const startTimeParsed = new Date(startTime);
    const startTimeKey = formatDate(startTimeParsed).replace(/[:\s-]/g, '');
    const polygonPoints = parseKmlCoordinateString(polygon);

    placemarkData.push({
      placemark_name: pm.name,
      start_time_parsed: startTimeParsed,
      start_time_key: startTimeKey,
      customers_impacted: customersImpacted,
      status,
      cause,
      est_restoration_time: estRestorationTime,
      polygon_points: polygonPoints
    });
  }

  if (placemarkData.length === 0) return;

  // Group by start time
  const grouped = new Map<string, any>();
  for (const data of placemarkData) {
    const key = data.start_time_key;
    if (!grouped.has(key)) {
      grouped.set(key, {
        placemark_name: data.placemark_name,
        start_time_parsed: data.start_time_parsed,
        start_time_key: data.start_time_key,
        customers_impacted: 0,
        status: data.status,
        cause: data.cause,
        est_restoration_time: data.est_restoration_time,
        polygon_points: []
      });
    }
    const group = grouped.get(key)!;
    group.customers_impacted += data.customers_impacted;
    group.polygon_points.push(data.polygon_points);
  }

  // Process each group
  for (const [, row] of grouped) {
    const outageId = formatDate(row.start_time_parsed).replace(/[:\s-]/g, '');
    const allPolygons = row.polygon_points;
    const [centerLon, centerLat, radius] = smallestEnclosingCircle(allPolygons);

    let estRestorationTimeString: string;
    try {
      const estTime = new Date(row.est_restoration_time);
      estRestorationTimeString = formatDate(estTime);
    } catch (e) {
      console.log(`error parsing est restoration time: ${row.est_restoration_time}. Exception: ${e}. Defaulting to None`);
      estRestorationTimeString = 'None';
    }

    if (allPolygons.length > 1) {
      console.log(`Combining ${allPolygons.length} placemarks with start time ${row.start_time_key}`);
    }

    rows.push({
      utility: 'snopud',
      outage_id: outageId,
      file_datetime: formatDate(fileDateTime),
      start_time: formatDate(row.start_time_parsed),
      customers_impacted: row.customers_impacted,
      status: row.status,
      cause: row.cause,
      est_restoration_time: estRestorationTimeString,
      polygon_json: JSON.stringify(allPolygons),
      center_lon: centerLon,
      center_lat: centerLat,
      radius,
      isFromMostRecent
    });
  }
}

// Parse PG&E file
export function parsePgeFile(filePath: string, rows: OutageRow[], fileDateTime: Date, isFromMostRecent = true): void {
  let data: any;
  try {
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    data = JSON.parse(fileContent);
  } catch (e) {
    console.log(`error parsing pge file: ${filePath}. Defaulting to empty list. Exception: ${e}`);
    return;
  }

  for (const outage of data.features || []) {
    const outageAttributes = outage.attributes || {};
    const outageId = outageAttributes.OUTAGE_ID;
    const startTimeMs = outageAttributes.OUTAGE_START;
    const customersImpacted = outageAttributes.EST_CUSTOMERS || 0;
    const status = outageAttributes.CREW_CURRENT_STATUS;
    const cause = outageAttributes.OUTAGE_CAUSE;
    const estRestorationTimeMs = outageAttributes.CURRENT_ETOR;
    const outageGeometry = outage.geometry || {};
    let x = outageGeometry.x;
    let y = outageGeometry.y;

    let lon: number | null = null;
    let lat: number | null = null;

    // Convert from EPSG:3857 to EPSG:4326
    if (x !== null && x !== undefined && y !== null && y !== undefined) {
      const transformed = proj4('EPSG:3857', 'EPSG:4326', [x, y]);
      lon = transformed[0];
      lat = transformed[1];
    }

    if (!outageId || !startTimeMs || lat === null || lon === null) {
      console.log(`ALERT: skipping outage ${outageId} because it is missing essential data`);
      console.log(`outage properties: ${JSON.stringify(outageAttributes)}`);
      continue;
    }

    const startTime = new Date(startTimeMs);
    let estRestorationTime: Date | null = null;
    if (estRestorationTimeMs) {
      estRestorationTime = new Date(estRestorationTimeMs);
    }

    // Create a small circular polygon
    const radiusDegrees = 0.001;
    const numPoints = 8;
    const polygonPoints: [number, number][] = [];

    for (let i = 0; i < numPoints; i++) {
      const angle = 2 * Math.PI * i / numPoints;
      const deltaLon = radiusDegrees * Math.cos(angle);
      const deltaLat = radiusDegrees * Math.sin(angle);
      polygonPoints.push([lon + deltaLon, lat + deltaLat]);
    }
    polygonPoints.push(polygonPoints[0]);

    const polygons = [polygonPoints];
    const centerLon = lon;
    const centerLat = lat;
    const radius = 0.05;

    rows.push({
      utility: 'pge',
      outage_id: outageId,
      file_datetime: formatDate(fileDateTime),
      start_time: formatDate(startTime),
      customers_impacted: customersImpacted,
      status,
      cause,
      est_restoration_time: estRestorationTime === null ? 'none' : formatDate(estRestorationTime),
      polygon_json: JSON.stringify(polygons),
      center_lon: centerLon,
      center_lat: centerLat,
      radius,
      isFromMostRecent
    });
  }
}

// Calculate expected length in minutes
export function calculateExpectedLengthMinutes(updateTime: string | Date | null, estRestorationTime: string | Date | null): number | null {
  try {
    if (!updateTime || !estRestorationTime) return null;

    let updateDate: Date;
    let restDate: Date;

    if (typeof updateTime === 'string') {
      if (updateTime === 'none') return null;
      updateDate = new Date(updateTime);
    } else {
      updateDate = updateTime;
    }

    if (typeof estRestorationTime === 'string') {
      if (estRestorationTime === 'none') return null;
      restDate = new Date(estRestorationTime);
    } else {
      restDate = estRestorationTime;
    }

    const timeDiff = restDate.getTime() - updateDate.getTime();
    return Math.floor(timeDiff / 60000);
  } catch (e) {
    console.log(`Error calculating expected length: ${e}`);
    console.log(`   update_time: ${updateTime}`);
    console.log(`   est_restoration_time: ${estRestorationTime}`);
    return null;
  }
}

// Calculate active duration in minutes
export function calculateActiveDurationMinutes(startTime: string | Date, currentTime: string | Date): number | null {
  try {
    const startDate = typeof startTime === 'string' ? new Date(startTime) : startTime;
    const currentDate = typeof currentTime === 'string' ? new Date(currentTime) : currentTime;

    const timeDiff = currentDate.getTime() - startDate.getTime();
    return Math.floor(timeDiff / 60000);
  } catch (e) {
    console.log(`Error calculating active duration: ${e}`);
    return null;
  }
}

// Reverse geocode
export async function reverseGeocode(lat: number, lon: number, apiKey?: string): Promise<string> {
  const mapsUrl = `https://maps.google.com/maps?q=${lat.toFixed(6)},${lon.toFixed(6)}`;

  try {
    if (!apiKey) {
      return mapsUrl;
    }

    const url = `https://geocode.maps.co/reverse?lat=${lat}&lon=${lon}&api_key=${apiKey}`;
    const response = await axios.get(url);
    await new Promise(resolve => setTimeout(resolve, 1000)); // Rate limiting

    const data = response.data;
    const address = data.address || {};

    const suburb = address.suburb || '';
    const city = address.city || address.town || '';
    const county = address.county || '';
    const state = address.state || '';

    const stateAbbr = state ? STATE_ABBREVIATIONS[state.toLowerCase()] || '' : '';

    if (suburb && city && stateAbbr) {
      return `[${suburb}, ${city}, ${stateAbbr}](${mapsUrl})`;
    } else if (city && stateAbbr) {
      return `[${city}, ${stateAbbr}](${mapsUrl})`;
    } else if (county && stateAbbr) {
      return `[${county}, ${stateAbbr}](${mapsUrl})`;
    } else if (stateAbbr) {
      return `[${stateAbbr}](${mapsUrl})`;
    }

    return mapsUrl;
  } catch (e) {
    console.log(`Error reverse geocoding coordinates ${lat}, ${lon}: ${e}`);
    return mapsUrl;
  }
}

// Get filename suffix for utility
export function getFilenameSuffixForUtility(utility: string): string {
  const suffixes: { [key: string]: string } = {
    'pse': '-pse-events.json',
    'scl': '-scl-events.json',
    'snopud': '-KMLOutageAreas.xml',
    'pge': '-pge-events.json'
  };
  return suffixes[utility] || '';
}
