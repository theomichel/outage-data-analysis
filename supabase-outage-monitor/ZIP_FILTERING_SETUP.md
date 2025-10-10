# Zip Code Filtering Setup

This guide explains how to set up zip code filtering for outage notifications.

## Overview

Zip code filtering allows you to only receive notifications for outages in specific geographic areas. This uses PostGIS for efficient point-in-polygon lookups.

## Prerequisites

- Supabase project with PostGIS enabled (done automatically by migrations)
- Zip code boundary GeoJSON file (included in `constant_data/`)

## Setup Steps

### 1. Apply Database Migrations

The migrations create the necessary PostGIS tables and functions:

```bash
# Local development
supabase db reset

# Production
supabase db push
```

This creates:
- `zip_boundaries` table with PostGIS geometry column
- `get_zipcode_for_point(lon, lat)` function for lookups
- Spatial index for fast queries

### 2. Load Zip Code Boundaries

Load the GeoJSON data into the database:

```bash
# For California (PG&E)
cd supabase-outage-monitor
deno run --allow-read --allow-net --allow-env scripts/load-zip-boundaries.ts

# The script will process ~1,700 CA zip codes
```

**Note**: This only needs to be done once per environment (local/production).

### 3. Add Zip Codes to Whitelist

Add the specific zip codes you want to monitor:

```sql
-- Example: Bay Area zip codes
INSERT INTO zip_code_whitelist (zipcode, enabled)
SELECT zipcode, true
FROM unnest(ARRAY[
  '94002', '94005', '94010', '94011', '94014', '94015', '94016', '94017',
  '94018', '94019', '94020', '94021', '94022', '94023', '94024', '94025',
  -- ... add more zip codes
]) AS zipcode
ON CONFLICT (zipcode) DO UPDATE SET enabled = true;
```

Or load from the bay_area_zip_codes.txt file:

```sql
-- Copy the zip codes from constant_data/bay_area_zip_codes.txt
-- and insert them
```

### 4. Enable Zip Filtering

Set the environment variable in Supabase:

```
ENABLE_ZIP_FILTERING=true
```

Go to: Project Settings → Edge Functions → Add secret

## Testing Locally

### 1. Reset database and apply migrations

```bash
supabase db reset
```

### 2. Load zip boundaries

```bash
deno run --allow-read --allow-net --allow-env scripts/load-zip-boundaries.ts
```

### 3. Load bay area zip codes into whitelist

```bash
# Connect to local database
psql postgresql://postgres:postgres@localhost:54322/postgres

# Then run:
\copy zip_code_whitelist(zipcode, enabled) FROM '../constant_data/bay_area_zip_codes.txt' WITH (FORMAT csv, HEADER false);
UPDATE zip_code_whitelist SET enabled = true;
```

Or use SQL:

```sql
-- Load from array
DO $$
DECLARE
  zips TEXT[];
  zip TEXT;
BEGIN
  -- Read from file would go here, but for now use array
  zips := ARRAY['94002', '94005', '94010']; -- etc

  FOREACH zip IN ARRAY zips
  LOOP
    INSERT INTO zip_code_whitelist (zipcode, enabled)
    VALUES (zip, true)
    ON CONFLICT (zipcode) DO NOTHING;
  END LOOP;
END $$;
```

### 4. Run tests with zip filtering enabled

```bash
# The test should now pass with outage 9234 filtered out
deno test --allow-net --allow-read --allow-env tests/integration/
```

## How It Works

1. **Outage detected**: Edge function fetches outage with lat/lon
2. **Zip lookup**: Calls `get_zipcode_for_point(lon, lat)` PostGIS function
3. **Point-in-polygon**: PostGIS checks which zip boundary contains the point
4. **Filtering**: If `ENABLE_ZIP_FILTERING=true`, only outages in whitelisted zips are processed
5. **Notification**: Only filtered outages trigger notifications

## Performance

- **PostGIS spatial index**: O(log n) lookup time
- **~1,700 CA zip codes**: < 10ms per lookup
- **Batch lookups**: Processed in parallel for each snapshot

## Troubleshooting

### Zip boundaries not loaded

```
Error: function get_zipcode_for_point does not exist
```

**Solution**: Run migrations: `supabase db reset`

### No zip code found for outage

Check if the coordinates are valid:

```sql
SELECT get_zipcode_for_point(-122.0856, 37.4224); -- Mountain View, CA
-- Should return: 94043
```

If NULL, the point may be outside loaded boundaries.

### All outages filtered out

Check whitelist:

```sql
SELECT * FROM zip_code_whitelist WHERE enabled = true;
```

Make sure the zip codes match your target area.

## Production Deployment

1. Apply migrations to production:
```bash
supabase link --project-ref jsruenplxmemdlilactp
supabase db push
```

2. Load zip boundaries to production:
```bash
# Set production credentials
export SUPABASE_URL=https://jsruenplxmemdlilactp.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

deno run --allow-read --allow-net --allow-env scripts/load-zip-boundaries.ts
```

3. Load whitelist via SQL editor in Supabase dashboard

4. Enable filtering in Edge Function settings:
```
ENABLE_ZIP_FILTERING=true
```

## Additional States

To add Washington State (for PSE/SCL/SnoPUD):

1. Update `scripts/load-zip-boundaries.ts` to use `wa_washington_zip_codes_geo.min.json`
2. Change `state: 'CA'` to `state: 'WA'`
3. Run the script again

The same `zip_boundaries` table can hold multiple states.
