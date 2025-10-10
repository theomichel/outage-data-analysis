# Supabase Outage Monitor

Real-time power outage monitoring system using Supabase Edge Functions and PostgreSQL.

## Architecture

This system replaces the file-based outage notifier with a cloud-based solution:

1. **Data Fetching**: Edge functions fetch outage data directly from utility websites (PSE, SCL, SnoPUD, PG&E)
2. **Storage**: Snapshots stored in Supabase PostgreSQL database
3. **Comparison**: Automatic comparison of latest vs previous snapshots using the same logic as the original implementation
4. **Notifications**: Telegram alerts for new, resolved, and escalated outages
5. **Scheduling**: Runs automatically every 10 minutes via Supabase Cron
6. **Zip Code Filtering**: Optional filtering by whitelisted zip codes

## Quick Start

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

```bash
# 1. Link to your Supabase project
supabase link --project-ref jsruenplxmemdlilactp

# 2. Deploy database migrations
supabase db push

# 3. Set environment variables in Supabase dashboard
# (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, etc.)

# 4. Deploy edge function
supabase functions deploy fetch-outages

# 5. Set up cron job in Supabase dashboard to run every 10 minutes
```

## Database Schema

### `outage_snapshots` table
Stores raw outage data at each collection time:
- `id` (uuid, primary key)
- `utility` (text) - pse, scl, snopud, pge
- `snapshot_time` (timestamptz) - when data was fetched
- `outages` (jsonb) - array of outage records
- `created_at` (timestamptz)

### `outage_records` table
Individual outage records with calculated fields:
- `id` (uuid, primary key)
- `snapshot_id` (uuid, foreign key to outage_snapshots)
- `utility` (text)
- `outage_id` (text) - utility's outage identifier
- `snapshot_time` (timestamptz)
- `start_time` (timestamptz)
- `customers_impacted` (integer)
- `status` (text)
- `cause` (text)
- `est_restoration_time` (timestamptz)
- `center_lon` (double precision)
- `center_lat` (double precision)
- `polygon` (jsonb)
- `elapsed_time_minutes` (integer) - calculated
- `expected_length_minutes` (integer) - calculated
- `created_at` (timestamptz)

### Indexes
- `idx_outage_records_utility_snapshot` on (utility, snapshot_time)
- `idx_outage_records_outage_id` on (utility, outage_id, snapshot_time)

## Edge Functions

### `fetch-outages`
Scheduled cron function that:
1. Fetches data from all configured utilities
2. Stores raw snapshot in `outage_snapshots`
3. Parses and stores individual records in `outage_records`
4. Compares with previous snapshot
5. Sends notifications for changes

## Local Development

```bash
# Install Supabase CLI
npm install -g supabase

# Initialize Supabase project (if not done)
supabase init

# Start local Supabase
supabase start

# Deploy functions locally
supabase functions serve

# Deploy to production
supabase functions deploy fetch-outages
```

## Configuration

Set environment variables in Supabase dashboard:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token (required)
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID (required)
- `TELEGRAM_THREAD_ID` - Telegram thread ID (optional)
- `GEOCODE_API_KEY` - API key for geocode.maps.co (optional, for human-readable locations)
- `CUSTOMER_THRESHOLD` - Minimum customers affected (default: 100)
- `LARGE_OUTAGE_THRESHOLD` - Large outage threshold (default: 1000)
- `ELAPSED_TIME_THRESHOLD_HOURS` - Minimum elapsed time (default: 0.25)
- `EXPECTED_LENGTH_THRESHOLD_HOURS` - Minimum expected duration (default: 4.0)
- `ENABLE_ZIP_FILTERING` - Set to "true" to enable zip code filtering (default: false)
- `UTILITIES` - Comma-separated list (default: "pse,scl,snopud,pge")

## Data Sources

The system fetches data directly from utility APIs:
- **SnoPUD**: https://outagemap.snopud.com/Home/KMLOutageAreas
- **SCL**: https://utilisocial.io/datacapable/v2/p/scl/map/events
- **PSE**: https://www.pse.com/api/sitecore/OutageMap/AnonymoussMapListView
- **PG&E**: https://ags.pge.esriemcs.com/arcgis/rest/services/43/outages/MapServer/4/query

## Features

✅ Real-time outage monitoring from 4 utility companies
✅ Automatic comparison with previous snapshots
✅ Telegram notifications for new, escalated, and resolved outages
✅ Zip code filtering support
✅ Geolocation with reverse geocoding
✅ EPSG:3857 to WGS84 coordinate transformation (for PG&E)
✅ Smallest enclosing circle calculation for outage areas
✅ Complete notification logging and audit trail
✅ Runs automatically every 10 minutes
