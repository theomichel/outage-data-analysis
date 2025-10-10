#!/usr/bin/env -S deno run --allow-read --allow-net --allow-env

// Script to load zip code boundaries from GeoJSON into Supabase

import { createClient } from 'jsr:@supabase/supabase-js@2';

const GEOJSON_FILE = '../constant_data/ca_california_zip_codes_geo.min.json';

async function main() {
  const supabaseUrl = Deno.env.get('SUPABASE_URL') || 'http://localhost:54321';
  const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || Deno.env.get('SUPABASE_ANON_KEY') ||
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0';

  console.log('Loading California zip code boundaries...');
  console.log(`Supabase URL: ${supabaseUrl}`);

  const client = createClient(supabaseUrl, supabaseKey);

  // Read GeoJSON file
  console.log(`Reading ${GEOJSON_FILE}...`);
  const fileContent = await Deno.readTextFile(GEOJSON_FILE);
  const geoJson = JSON.parse(fileContent);

  console.log(`Found ${geoJson.features.length} zip code features`);

  // Process in batches to avoid overwhelming the database
  const batchSize = 50;
  let inserted = 0;
  let failed = 0;

  for (let i = 0; i < geoJson.features.length; i += batchSize) {
    const batch = geoJson.features.slice(i, i + batchSize);

    const records = batch.map((feature: any) => {
      const zipcode = feature.properties.ZCTA5CE10 || feature.properties.zipcode;
      const geometry = feature.geometry;

      // Convert GeoJSON geometry to WKT (Well-Known Text) for PostGIS
      const wkt = geometryToWKT(geometry);

      return {
        zipcode: String(zipcode),
        state: 'CA',
        geometry: wkt,
      };
    });

    // Insert batch using raw SQL for PostGIS geometry
    for (const record of records) {
      try {
        const { error } = await client.rpc('insert_zip_boundary', {
          p_zipcode: record.zipcode,
          p_state: record.state,
          p_geometry_wkt: record.geometry,
        });

        if (error) {
          console.error(`Error inserting ${record.zipcode}:`, error.message);
          failed++;
        } else {
          inserted++;
        }
      } catch (e) {
        console.error(`Exception inserting ${record.zipcode}:`, e);
        failed++;
      }
    }

    console.log(`Processed ${Math.min(i + batchSize, geoJson.features.length)}/${geoJson.features.length}`);
  }

  console.log(`\nComplete! Inserted ${inserted} zip codes, ${failed} failed`);
}

function geometryToWKT(geometry: any): string {
  if (geometry.type === 'Polygon') {
    // Convert Polygon to MultiPolygon to match database column type
    const rings = geometry.coordinates.map((ring: number[][]) =>
      '(' + ring.map((coord: number[]) => `${coord[0]} ${coord[1]}`).join(', ') + ')'
    ).join(', ');
    return `MULTIPOLYGON((${rings}))`;
  } else if (geometry.type === 'MultiPolygon') {
    const polygons = geometry.coordinates.map((polygon: number[][][]) =>
      '(' + polygon.map((ring: number[][]) =>
        '(' + ring.map((coord: number[]) => `${coord[0]} ${coord[1]}`).join(', ') + ')'
      ).join(', ') + ')'
    ).join(', ');
    return `MULTIPOLYGON(${polygons})`;
  }
  throw new Error(`Unsupported geometry type: ${geometry.type}`);
}

main().catch(console.error);
