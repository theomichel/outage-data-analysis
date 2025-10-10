// Database interaction layer

import { createClient, SupabaseClient } from 'jsr:@supabase/supabase-js@2';
import type { Utility, OutageRecord, OutageSnapshot, NotificationLog } from './types.ts';

export function getSupabaseClient(supabaseUrl: string, supabaseKey: string): SupabaseClient {
  return createClient(supabaseUrl, supabaseKey);
}

export async function saveSnapshot(
  client: SupabaseClient,
  utility: Utility,
  snapshotTime: Date,
  outages: OutageRecord[],
  fetchDurationMs: number
): Promise<string> {
  const { data, error } = await client
    .from('outage_snapshots')
    .insert({
      utility,
      snapshot_time: snapshotTime.toISOString(),
      outages: outages,
      fetch_duration_ms: fetchDurationMs,
    })
    .select('id')
    .single();

  if (error) {
    console.error('Error saving snapshot:', error);
    throw error;
  }

  return data.id;
}

export async function saveOutageRecords(
  client: SupabaseClient,
  snapshotId: string,
  records: OutageRecord[]
): Promise<void> {
  // Add zip codes to records before saving
  await addZipCodesToRecords(client, records);

  const recordsWithSnapshotId = records.map((r) => ({
    ...r,
    snapshot_id: snapshotId,
  }));

  const { error } = await client.from('outage_records').insert(recordsWithSnapshotId);

  if (error) {
    console.error('Error saving outage records:', error);
    throw error;
  }
}

export async function getPreviousSnapshot(
  client: SupabaseClient,
  utility: Utility,
  beforeTime: Date
): Promise<OutageSnapshot | null> {
  const { data, error } = await client
    .from('outage_snapshots')
    .select('*')
    .eq('utility', utility)
    .lt('snapshot_time', beforeTime.toISOString())
    .order('snapshot_time', { ascending: false })
    .limit(1)
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      // No rows found
      return null;
    }
    console.error('Error fetching previous snapshot:', error);
    throw error;
  }

  return data;
}

export async function getPreviousOutageRecords(
  client: SupabaseClient,
  snapshotId: string,
  enableZipFiltering: boolean = false
): Promise<OutageRecord[]> {
  // If zip filtering is enabled, get the whitelist first
  let whitelistedZips: string[] = [];
  if (enableZipFiltering) {
    whitelistedZips = await getZipCodeWhitelist(client);
    if (whitelistedZips.length === 0) {
      // No whitelisted zips, return empty array
      return [];
    }
  }

  let query = client
    .from('outage_records')
    .select('*')
    .eq('snapshot_id', snapshotId);

  // If zip filtering is enabled, only return records with zip codes in the whitelist
  if (enableZipFiltering && whitelistedZips.length > 0) {
    query = query
      .not('zipcode', 'is', null)
      .in('zipcode', whitelistedZips);
  }

  const { data, error } = await query;

  if (error) {
    console.error('Error fetching previous outage records:', error);
    throw error;
  }

  return data || [];
}

export async function getZipCodeWhitelist(client: SupabaseClient): Promise<string[]> {
  const { data, error } = await client
    .from('zip_code_whitelist')
    .select('zipcode')
    .eq('enabled', true);

  if (error) {
    console.error('Error fetching zip code whitelist:', error);
    throw error;
  }

  return (data || []).map((row) => row.zipcode);
}

export async function saveNotificationLog(
  client: SupabaseClient,
  log: NotificationLog
): Promise<void> {
  const { error } = await client.from('notification_log').insert(log);

  if (error) {
    console.error('Error saving notification log:', error);
    throw error;
  }
}

export async function filterByZipCodes(
  records: OutageRecord[],
  whitelist: string[]
): Promise<OutageRecord[]> {
  if (whitelist.length === 0) return records;

  // Filter records that have a zipcode in the whitelist
  return records.filter((r) => r.zipcode && whitelist.includes(r.zipcode));
}

export async function addZipCodesToRecords(
  client: SupabaseClient,
  records: OutageRecord[]
): Promise<void> {
  // Use PostGIS function to determine zip code for each outage
  for (const record of records) {
    try {
      const { data, error } = await client.rpc('get_zipcode_for_point', {
        lon: record.center_lon,
        lat: record.center_lat,
      });

      if (error) {
        console.warn(`Error getting zipcode for outage ${record.outage_id}:`, error.message);
        continue;
      }

      if (data) {
        record.zipcode = data;
      }
    } catch (e) {
      console.warn(`Could not determine zipcode for outage ${record.outage_id}:`, e);
    }
  }
}
