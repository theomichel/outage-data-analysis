# Deployment Guide

Step-by-step guide to deploy the Supabase Outage Monitor to your project.

## Prerequisites

1. Install Supabase CLI:
```bash
npm install -g supabase
```

2. Ensure you have access to your Supabase project: https://supabase.com/dashboard/project/jsruenplxmemdlilactp

## Step 1: Link to Your Supabase Project

```bash
cd supabase-outage-monitor
supabase link --project-ref jsruenplxmemdlilactp
```

You'll be prompted to enter your database password.

## Step 2: Deploy Database Migrations

This will create the necessary tables for storing outages and notifications.

```bash
supabase db push
```

This creates:
- `outage_snapshots` - Raw snapshot data from APIs
- `outage_records` - Individual parsed outage records
- `zip_code_whitelist` - Zip codes to filter by
- `notification_log` - Log of all notifications sent

## Step 3: (Optional) Add Zip Codes to Whitelist

If you want to enable zip code filtering, add zip codes to the whitelist table:

```sql
INSERT INTO zip_code_whitelist (zipcode, enabled) VALUES
  ('98101', true),
  ('98102', true),
  ('98103', true);
  -- Add more zip codes as needed
```

You can run this in the Supabase SQL Editor: https://supabase.com/dashboard/project/jsruenplxmemdlilactp/sql

## Step 4: Set Environment Variables

Go to Edge Functions settings: https://supabase.com/dashboard/project/jsruenplxmemdlilactp/settings/functions

Add these environment variables (secrets):

### Required:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

### Optional:
- `TELEGRAM_THREAD_ID` - Telegram thread ID (if using threads)
- `GEOCODE_API_KEY` - API key for geocode.maps.co (for location names)
- `CUSTOMER_THRESHOLD` - Minimum customers affected (default: 100)
- `LARGE_OUTAGE_THRESHOLD` - Large outage threshold (default: 1000)
- `ELAPSED_TIME_THRESHOLD_HOURS` - Minimum elapsed time (default: 0.25)
- `EXPECTED_LENGTH_THRESHOLD_HOURS` - Minimum expected duration (default: 4.0)
- `ENABLE_ZIP_FILTERING` - Set to "true" to enable zip code filtering
- `UTILITIES` - Comma-separated list of utilities to monitor (default: "pse,scl,snopud,pge")

## Step 5: Deploy Edge Function

```bash
supabase functions deploy fetch-outages
```

## Step 6: Set Up Cron Schedule

You have two options:

### Option A: Using Supabase Dashboard (Recommended)

1. Go to Database → Cron Jobs: https://supabase.com/dashboard/project/jsruenplxmemdlilactp/database/cron-jobs
2. Click "Create a new cron job"
3. Set the schedule to run every 10 minutes: `*/10 * * * *`
4. Use this SQL command:
```sql
SELECT
  net.http_post(
      url:='https://jsruenplxmemdlilactp.supabase.co/functions/v1/fetch-outages',
      headers:='{"Content-Type": "application/json", "Authorization": "Bearer YOUR_ANON_KEY"}'::jsonb
  ) as request_id;
```

Replace `YOUR_ANON_KEY` with your project's anon key from: https://supabase.com/dashboard/project/jsruenplxmemdlilactp/settings/api

### Option B: Using pg_cron Extension

If you prefer SQL-based setup:

```sql
-- Enable pg_cron extension
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule the function to run every 10 minutes
SELECT cron.schedule(
  'fetch-outages-every-10-min',
  '*/10 * * * *',
  $$
  SELECT
    net.http_post(
        url:='https://jsruenplxmemdlilactp.supabase.co/functions/v1/fetch-outages',
        headers:='{"Content-Type": "application/json", "Authorization": "Bearer YOUR_ANON_KEY"}'::jsonb
    ) as request_id;
  $$
);
```

## Step 7: Test the Function

You can manually trigger the function to test it:

```bash
curl -X POST 'https://jsruenplxmemdlilactp.supabase.co/functions/v1/fetch-outages' \
  -H 'Authorization: Bearer YOUR_ANON_KEY' \
  -H 'Content-Type: application/json'
```

Or use the Supabase dashboard to invoke it: https://supabase.com/dashboard/project/jsruenplxmemdlilactp/functions

## Step 8: Monitor Logs

View function logs in the dashboard: https://supabase.com/dashboard/project/jsruenplxmemdlilactp/functions/fetch-outages/logs

Or use the CLI:
```bash
supabase functions logs fetch-outages
```

## Verification

After deployment, verify everything is working:

1. Check that the cron job ran:
```sql
SELECT * FROM outage_snapshots ORDER BY created_at DESC LIMIT 5;
```

2. Check for any notifications sent:
```sql
SELECT * FROM notification_log ORDER BY sent_at DESC LIMIT 10;
```

3. View recent outages:
```sql
SELECT utility, COUNT(*) as outage_count, MAX(snapshot_time) as latest_snapshot
FROM outage_records
GROUP BY utility;
```

## Troubleshooting

### Function fails to deploy
- Ensure you have the correct project ref: `jsruenplxmemdlilactp`
- Check that you're authenticated: `supabase login`

### No notifications sent
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set correctly
- Check notification_log table for error messages
- View function logs for detailed error information

### Zip code filtering not working
- Ensure `ENABLE_ZIP_FILTERING` is set to "true"
- Verify zip codes are in the `zip_code_whitelist` table
- Check that the `get_zipcode_for_point` function is implemented (see next section)

## Advanced: Implementing Zip Code Lookup

For zip code filtering to work, you need to implement the `get_zipcode_for_point` function using PostGIS:

1. Enable PostGIS extension:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

2. Create a zip_boundaries table with geometry data (you'll need to import GeoJSON data)

3. Create the lookup function:
```sql
CREATE OR REPLACE FUNCTION get_zipcode_for_point(lon DOUBLE PRECISION, lat DOUBLE PRECISION)
RETURNS TEXT AS $$
  SELECT zipcode
  FROM zip_boundaries
  WHERE ST_Contains(geometry, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
  LIMIT 1;
$$ LANGUAGE SQL STABLE;
```

Alternatively, you can disable zip filtering by not setting `ENABLE_ZIP_FILTERING=true`.
