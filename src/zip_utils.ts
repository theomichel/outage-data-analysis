import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import booleanPointInPolygon from '@turf/boolean-point-in-polygon';
import { point } from '@turf/helpers';

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Default file paths
const DEFAULT_ZIP_GEO_FILE = path.join(__dirname, '..', 'constant_data', 'wa_washington_zip_codes_geo.min.json');
const DEFAULT_ZIP_POPULATION_FILE = path.join(__dirname, '..', 'constant_data', 'washington_zip_populations.csv');

interface ZipCodeFeature {
  type: 'Feature';
  properties: {
    ZCTA5CE10: string;
    [key: string]: any;
  };
  geometry: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: any;
  };
}

interface ZipGeoData {
  type: 'FeatureCollection';
  features: ZipCodeFeature[];
}

let _zipGeoData: ZipGeoData | null = null;

/**
 * Load zip code boundaries from GeoJSON file.
 * Returns zip code data with polygons.
 */
export function loadZipCodes(zipFilePath?: string): ZipGeoData | null {
  if (_zipGeoData !== null) {
    return _zipGeoData;
  }

  const filePath = zipFilePath || DEFAULT_ZIP_GEO_FILE;

  if (!fs.existsSync(filePath)) {
    console.log(`Warning: Zip code file not found at ${filePath}`);
    return null;
  }

  try {
    console.log(`Loading zip code boundaries from ${filePath}...`);
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    _zipGeoData = JSON.parse(fileContent) as ZipGeoData;
    console.log(`Loaded ${_zipGeoData.features.length} zip code boundaries`);
    return _zipGeoData;
  } catch (e) {
    console.log(`Error loading zip code file: ${e}`);
    return null;
  }
}

/**
 * Get zip code for a given longitude and latitude using point-in-polygon.
 */
export function getZipCode(lon: number | null | undefined, lat: number | null | undefined): string | null {
  // Handle missing coordinates
  if (lon === null || lon === undefined || lat === null || lat === undefined) {
    return null;
  }

  if (isNaN(lon) || isNaN(lat)) {
    return null;
  }

  // Load zip code boundaries
  if (_zipGeoData === null) {
    throw new Error('Zip code boundaries not loaded. Load first with loadZipCodes().');
  }

  try {
    // Create a Point for the coordinates
    const pt = point([lon, lat]);

    // Find which zip code contains the point
    for (const feature of _zipGeoData.features) {
      if (booleanPointInPolygon(pt, feature as any)) {
        const zipCode = feature.properties.ZCTA5CE10;
        return zipCode ? String(zipCode) : null;
      }
    }

    return null;
  } catch (e) {
    console.log(`Error getting zip code for coordinates (${lon}, ${lat}): ${e}`);
    return null;
  }
}
