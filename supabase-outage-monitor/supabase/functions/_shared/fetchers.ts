// Data fetchers for each utility

import type { Utility, OutageRecord } from './types.ts';
import { smallestEnclosingCircle, calculateExpectedLengthMinutes, calculateElapsedMinutes } from './geometry.ts';

// Utility URLs - configurable via environment variables for testing
const UTILITY_URLS = {
  snopud: Deno.env.get('SNOPUD_URL') || 'https://outagemap.snopud.com/Home/KMLOutageAreas',
  scl: Deno.env.get('SCL_URL') || 'https://utilisocial.io/datacapable/v2/p/scl/map/events',
  pse: Deno.env.get('PSE_URL') || 'https://www.pse.com/api/sitecore/OutageMap/AnonymoussMapListView',
  pge: Deno.env.get('PGE_URL') || 'https://ags.pge.esriemcs.com/arcgis/rest/services/43/outages/MapServer/4/query?where=1%3D1&outFields=OUTAGE_ID%2CCURRENT_ETOR%2COUTAGE_START%2CEST_CUSTOMERS%2COUTAGE_CAUSE%2CCREW_CURRENT_STATUS%2CLAST_UPDATE%2COUTAGE_START_TEXT%2CLAST_UPDATE_TEXT%2CCURRENT_ETOR_TEXT&f=pjson',
};

function formatDate(date: Date): string {
  return date.toISOString().replace('T', ' ').substring(0, 19);
}

function getAttr(attributes: any[], attributeName: string): any {
  for (const attr of attributes) {
    if (attr.RefName === attributeName || attr.Name === attributeName) {
      return attr.Value;
    }
  }
  return null;
}

function parsePseDateTime(dateStr: string, fileYear: number): Date {
  // Format: "2025/02/24 06:30 PM" or "02/24 06:30 PM"
  const match = dateStr.match(/(?:(\d{4})\/)?(\d{2})\/(\d{2})\s+(\d{1,2}):(\d{2})\s+(AM|PM)/);
  if (!match) throw new Error(`Invalid PSE date format: ${dateStr}`);

  const [, year, month, day, hour, minute, ampm] = match;
  const actualYear = year ? parseInt(year) : fileYear;
  let hours = parseInt(hour);
  if (ampm === 'PM' && hours !== 12) hours += 12;
  if (ampm === 'AM' && hours === 12) hours = 0;

  // PSE times are in Pacific time, convert to UTC (simplified - adds 8 hours for PST)
  const localDate = new Date(actualYear, parseInt(month) - 1, parseInt(day), hours, parseInt(minute));
  return new Date(localDate.getTime() + 8 * 60 * 60 * 1000);
}

export async function fetchPseOutages(snapshotTime: Date): Promise<OutageRecord[]> {
  const response = await fetch(UTILITY_URLS.pse);
  const data = await response.json();
  const records: OutageRecord[] = [];

  for (const outage of data.PseMap || []) {
    const provider = outage.DataProvider || {};
    const attributes = provider.Attributes || [];

    let outage_id = getAttr(attributes, 'OutageEventId') ||
                     getAttr(attributes, 'Outage ID') ||
                     getAttr(attributes, 'Outage ID:') ||
                     getAttr(attributes, '');

    if (!outage_id || !outage_id.startsWith('INC')) {
      console.warn(`PSE outage id '${outage_id}' missing or invalid, skipping`);
      continue;
    }

    let startTimeJson = getAttr(attributes, 'StartDate') || getAttr(attributes, 'Start time');
    if (startTimeJson.length <= 14) {
      startTimeJson = String(snapshotTime.getUTCFullYear()) + '/' + startTimeJson;
    }
    const startTime = parsePseDateTime(startTimeJson, snapshotTime.getUTCFullYear());

    let estRestorationTimeJson = getAttr(attributes, 'Est. Restoration time') ||
                                  getAttr(attributes, 'Est. restoration time');
    let estRestorationTime: Date | null = null;
    try {
      if (estRestorationTimeJson && estRestorationTimeJson.length <= 14) {
        estRestorationTimeJson = String(snapshotTime.getUTCFullYear()) + '/' + estRestorationTimeJson;
      }
      if (estRestorationTimeJson) {
        estRestorationTime = parsePseDateTime(estRestorationTimeJson, snapshotTime.getUTCFullYear());
      }
    } catch (e) {
      console.warn(`Error parsing PSE restoration time: ${e}`);
    }

    const customersImpacted = parseInt(getAttr(attributes, 'Customers impacted') || '0');
    const status = getAttr(attributes, 'Status') || '';
    const cause = getAttr(attributes, 'Cause') || '';
    const jsonPolygon = outage.Polygon || [];

    const polygons: [number, number][][] = [[]];
    for (const point of jsonPolygon) {
      polygons[0].push([point.Longitude, point.Latitude]);
    }

    const [centerLon, centerLat, radius] = smallestEnclosingCircle(polygons);

    records.push({
      utility: 'pse',
      outage_id,
      snapshot_time: formatDate(snapshotTime),
      start_time: formatDate(startTime),
      customers_impacted: customersImpacted,
      status,
      cause,
      est_restoration_time: estRestorationTime ? formatDate(estRestorationTime) : null,
      center_lon: centerLon,
      center_lat: centerLat,
      radius,
      polygon: polygons,
      elapsed_time_minutes: calculateElapsedMinutes(startTime, snapshotTime),
      expected_length_minutes: calculateExpectedLengthMinutes(snapshotTime, estRestorationTime),
    });
  }

  return records;
}

export async function fetchSclOutages(snapshotTime: Date): Promise<OutageRecord[]> {
  const response = await fetch(UTILITY_URLS.scl);
  const data = await response.json();
  const records: OutageRecord[] = [];

  for (const outage of data) {
    const outageId = outage.id;
    const startTime = new Date(outage.startTime);
    const customersImpacted = parseInt(outage.numPeople);
    const status = outage.status;
    const cause = outage.cause;
    const estRestorationTime = new Date(outage.etrTime);
    const rings = outage.polygons?.rings || [];

    const [centerLon, centerLat, radius] = smallestEnclosingCircle(rings);

    records.push({
      utility: 'scl',
      outage_id: outageId,
      snapshot_time: formatDate(snapshotTime),
      start_time: formatDate(startTime),
      customers_impacted: customersImpacted,
      status,
      cause,
      est_restoration_time: formatDate(estRestorationTime),
      center_lon: centerLon,
      center_lat: centerLat,
      radius,
      polygon: rings,
      elapsed_time_minutes: calculateElapsedMinutes(startTime, snapshotTime),
      expected_length_minutes: calculateExpectedLengthMinutes(snapshotTime, estRestorationTime),
    });
  }

  return records;
}

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
        if (!isNaN(lon) && !isNaN(lat)) {
          points.push([lon, lat]);
        }
      } catch {
        continue;
      }
    }
  }
  return points;
}

export async function fetchSnopudOutages(snapshotTime: Date): Promise<OutageRecord[]> {
  const response = await fetch(UTILITY_URLS.snopud);
  const xmlText = await response.text();

  // Simple XML parsing for KML (could use a library but keeping dependencies minimal)
  const placemark_matches = xmlText.matchAll(/<Placemark>[\s\S]*?<\/Placemark>/g);
  const placemarkData: any[] = [];

  for (const match of placemark_matches) {
    const placemarkXml = match[0];

    const getName = (xml: string, tag: string) => {
      const match = xml.match(new RegExp(`<${tag}>([^<]*)<\/${tag}>`));
      return match ? match[1] : null;
    };

    const getExtendedData = (xml: string, name: string) => {
      const regex = new RegExp(`<Data name="${name}">\\s*<value>([^<]*)<\\/value>`, 'i');
      const match = xml.match(regex);
      return match ? match[1] : null;
    };

    const startTime = getExtendedData(placemarkXml, 'StartUTC');
    const customersImpacted = parseInt(getExtendedData(placemarkXml, 'EstCustomersOut') || '-1');
    const status = getExtendedData(placemarkXml, 'OutageStatus');
    const cause = getExtendedData(placemarkXml, 'Cause');
    const estRestorationTime = getExtendedData(placemarkXml, 'EstimatedRestorationUTC');
    const coordinates = getName(placemarkXml, 'coordinates');

    if (customersImpacted === -1) continue;

    const startTimeParsed = new Date(startTime!);
    const polygonPoints = parseKmlCoordinateString(coordinates);

    placemarkData.push({
      start_time_parsed: startTimeParsed,
      start_time_key: startTimeParsed.toISOString(),
      customers_impacted: customersImpacted,
      status,
      cause,
      est_restoration_time: estRestorationTime,
      polygon_points: polygonPoints,
    });
  }

  // Group by start time
  const grouped = new Map<string, any>();
  for (const data of placemarkData) {
    const key = data.start_time_key;
    if (!grouped.has(key)) {
      grouped.set(key, {
        start_time_parsed: data.start_time_parsed,
        customers_impacted: 0,
        status: data.status,
        cause: data.cause,
        est_restoration_time: data.est_restoration_time,
        polygon_points: [],
      });
    }
    const group = grouped.get(key)!;
    group.customers_impacted += data.customers_impacted;
    group.polygon_points.push(data.polygon_points);
  }

  const records: OutageRecord[] = [];
  for (const [, row] of grouped) {
    const outageId = row.start_time_parsed.toISOString().replace(/[-:]/g, '').replace('T', '').split('.')[0];
    const [centerLon, centerLat, radius] = smallestEnclosingCircle(row.polygon_points);

    let estRestorationTime: Date | null = null;
    try {
      if (row.est_restoration_time) {
        estRestorationTime = new Date(row.est_restoration_time);
      }
    } catch (e) {
      console.warn(`Error parsing SnoPUD restoration time: ${e}`);
    }

    records.push({
      utility: 'snopud',
      outage_id: outageId,
      snapshot_time: formatDate(snapshotTime),
      start_time: formatDate(row.start_time_parsed),
      customers_impacted: row.customers_impacted,
      status: row.status,
      cause: row.cause,
      est_restoration_time: estRestorationTime ? formatDate(estRestorationTime) : null,
      center_lon: centerLon,
      center_lat: centerLat,
      radius,
      polygon: row.polygon_points,
      elapsed_time_minutes: calculateElapsedMinutes(row.start_time_parsed, snapshotTime),
      expected_length_minutes: calculateExpectedLengthMinutes(snapshotTime, estRestorationTime),
    });
  }

  return records;
}

export async function fetchPgeOutages(snapshotTime: Date): Promise<OutageRecord[]> {
  // Add unique ID to prevent caching
  const url = UTILITY_URLS.pge + `&_=${Date.now()}`;
  const response = await fetch(url);
  const data = await response.json();
  const records: OutageRecord[] = [];

  // Simple coordinate transformation from EPSG:3857 to EPSG:4326
  function epsg3857ToWgs84(x: number, y: number): [number, number] {
    const lon = (x * 180) / 20037508.34;
    let lat = (y * 180) / 20037508.34;
    lat = (Math.atan(Math.exp((lat * Math.PI) / 180)) * 360) / Math.PI - 90;
    return [lon, lat];
  }

  for (const outage of data.features || []) {
    const attr = outage.attributes || {};
    const outageId = attr.OUTAGE_ID;
    const startTimeMs = attr.OUTAGE_START;
    const customersImpacted = attr.EST_CUSTOMERS || 0;
    const status = attr.CREW_CURRENT_STATUS;
    const cause = attr.OUTAGE_CAUSE;
    const estRestorationTimeMs = attr.CURRENT_ETOR;
    const geometry = outage.geometry || {};
    const x = geometry.x;
    const y = geometry.y;

    let lon: number | null = null;
    let lat: number | null = null;

    if (x !== null && x !== undefined && y !== null && y !== undefined) {
      [lon, lat] = epsg3857ToWgs84(x, y);
    }

    if (!outageId || !startTimeMs || lat === null || lon === null) {
      console.warn(`PG&E outage ${outageId} missing essential data, skipping`);
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
      const angle = (2 * Math.PI * i) / numPoints;
      const deltaLon = radiusDegrees * Math.cos(angle);
      const deltaLat = radiusDegrees * Math.sin(angle);
      polygonPoints.push([lon + deltaLon, lat + deltaLat]);
    }
    polygonPoints.push(polygonPoints[0]);

    records.push({
      utility: 'pge',
      outage_id: String(outageId),
      snapshot_time: formatDate(snapshotTime),
      start_time: formatDate(startTime),
      customers_impacted: customersImpacted,
      status: status || '',
      cause: cause || '',
      est_restoration_time: estRestorationTime ? formatDate(estRestorationTime) : null,
      center_lon: lon,
      center_lat: lat,
      radius: 0.05,
      polygon: [polygonPoints],
      elapsed_time_minutes: calculateElapsedMinutes(startTime, snapshotTime),
      expected_length_minutes: calculateExpectedLengthMinutes(snapshotTime, estRestorationTime),
    });
  }

  return records;
}

export async function fetchUtilityOutages(utility: Utility, snapshotTime: Date): Promise<OutageRecord[]> {
  switch (utility) {
    case 'pse':
      return fetchPseOutages(snapshotTime);
    case 'scl':
      return fetchSclOutages(snapshotTime);
    case 'snopud':
      return fetchSnopudOutages(snapshotTime);
    case 'pge':
      return fetchPgeOutages(snapshotTime);
    default:
      throw new Error(`Unknown utility: ${utility}`);
  }
}
