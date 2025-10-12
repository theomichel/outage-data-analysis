// Main edge function for fetching and monitoring outages

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import type { Utility, Config } from '../_shared/types.ts';
import { fetchUtilityOutages } from '../_shared/fetchers.ts';
import {
  getSupabaseClient,
  saveSnapshot,
  saveOutageRecords,
  getPreviousSnapshot,
  getPreviousOutageRecords,
  getZipCodeWhitelist,
  filterByZipCodes,
  addZipCodesToRecords,
  saveNotificationLog,
} from '../_shared/database.ts';
import { compareOutages } from '../_shared/comparison.ts';
import { sendNotifications } from '../_shared/notifications.ts';

serve(async (req) => {
  try {
    // Parse request body for parameters
    const body = await req.json().catch(() => ({}));
    const utility: Utility = body.utility;
    const enableZipFiltering: boolean = body.enable_zip_filtering ?? false;

    // Validate utility parameter
    if (!utility) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Missing required parameter: utility'
        }),
        { headers: { 'Content-Type': 'application/json' }, status: 400 }
      );
    }

    console.log(`Processing ${utility} with zip filtering: ${enableZipFiltering}`);

    // Get configuration from environment variables
    const config: Config = {
      telegram_bot_token: Deno.env.get('TELEGRAM_BOT_TOKEN'),
      telegram_chat_id: Deno.env.get('TELEGRAM_CHAT_ID'),
      telegram_thread_id: Deno.env.get('TELEGRAM_THREAD_ID'),
      geocode_api_key: Deno.env.get('GEOCODE_API_KEY'),
      customer_threshold: parseInt(Deno.env.get('CUSTOMER_THRESHOLD') || '100'),
      large_outage_threshold: parseInt(Deno.env.get('LARGE_OUTAGE_THRESHOLD') || '1000'),
      elapsed_time_threshold_hours: parseFloat(Deno.env.get('ELAPSED_TIME_THRESHOLD_HOURS') || '0.25'),
      expected_length_threshold_hours: parseFloat(Deno.env.get('EXPECTED_LENGTH_THRESHOLD_HOURS') || '4.0'),
      enable_zip_filtering: enableZipFiltering,
    };

    // Get Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const client = getSupabaseClient(supabaseUrl, supabaseKey);

    // Fetch current outages
    const snapshotTime = new Date();
    const startTime = Date.now();
    const currentOutages = await fetchUtilityOutages(utility, snapshotTime);
    const fetchDurationMs = Date.now() - startTime;

    console.log(`Fetched ${currentOutages.length} outages for ${utility} in ${fetchDurationMs}ms`);

    // Apply zip code filtering if enabled
    let filteredOutages = currentOutages;
    if (config.enable_zip_filtering) {
      const zipWhitelist = await getZipCodeWhitelist(client);
      if (zipWhitelist.length > 0) {
        // Add zip codes to records
        await addZipCodesToRecords(client, currentOutages);
        // Filter by whitelist
        filteredOutages = await filterByZipCodes(currentOutages, zipWhitelist);
        console.log(`Filtered to ${filteredOutages.length} outages within whitelisted zip codes`);
      }
    }

    // Save snapshot
    const snapshotId = await saveSnapshot(client, utility, snapshotTime, filteredOutages, fetchDurationMs);
    console.log(`Saved snapshot ${snapshotId} for ${utility}`);

    // Save individual outage records
    await saveOutageRecords(client, snapshotId, filteredOutages);
    console.log(`Saved ${filteredOutages.length} outage records`);

    // Get previous snapshot for comparison
    const previousSnapshot = await getPreviousSnapshot(client, utility, snapshotTime);

    if (!previousSnapshot) {
      console.log(`No previous snapshot found for ${utility}, skipping comparison`);
      return new Response(
        JSON.stringify({
          success: true,
          utility,
          status: 'success',
          current_outages: filteredOutages.length,
          message: 'First snapshot, no comparison performed',
        }),
        { headers: { 'Content-Type': 'application/json' }, status: 200 }
      );
    }

    // Get previous outage records (with zip filtering if enabled)
    const previousOutages = await getPreviousOutageRecords(client, previousSnapshot.id!, config.enable_zip_filtering);

    console.log('\nPrevious outages:');
    console.table(previousOutages.map(o => ({
      id: o.outage_id,
      zip: o.zipcode || 'null',
      cust: o.customers_impacted,
      elapsed: o.elapsed_time_minutes,
      expected: o.expected_length_minutes,
    })));

    console.log('\nCurrent outages:');
    console.table(filteredOutages.map(o => ({
      id: o.outage_id,
      zip: o.zipcode || 'null',
      cust: o.customers_impacted,
      elapsed: o.elapsed_time_minutes,
      expected: o.expected_length_minutes,
    })));

    // Compare outages
    const comparison = compareOutages(filteredOutages, previousOutages, config);

    console.log('\nNew outages:');
    console.table(comparison.new_outages.map(o => ({
      id: o.outage_id,
      zip: o.zipcode || 'null',
      cust: o.customers_impacted,
      elapsed: o.elapsed_time_minutes,
      expected: o.expected_length_minutes,
    })));

    console.log('\nEscalated outages:');
    console.table(comparison.escalated_outages.map(o => ({
      id: o.outage_id,
      zip: o.zipcode || 'null',
      cust: o.customers_impacted,
      elapsed: o.elapsed_time_minutes,
      expected: o.expected_length_minutes,
    })));

    console.log('\nResolved outages:');
    console.table(comparison.resolved_outages.map(o => ({
      id: o.outage_id,
      zip: o.zipcode || 'null',
      cust: o.customers_impacted,
      elapsed: o.elapsed_time_minutes,
      expected: o.expected_length_minutes,
    })));

    // Send notifications
    if (
      comparison.new_outages.length > 0 ||
      comparison.escalated_outages.length > 0 ||
      comparison.resolved_outages.length > 0
    ) {
      const notificationLogs = await sendNotifications(
        comparison.new_outages,
        comparison.escalated_outages,
        comparison.resolved_outages,
        config
      );

      // Save notification logs
      for (const log of notificationLogs) {
        await saveNotificationLog(client, log);
      }

      console.log(`Sent ${notificationLogs.length} notifications`);
    } else {
      console.log('No notifiable changes detected');
    }

    return new Response(
      JSON.stringify({
        success: true,
        utility,
        status: 'success',
        current_outages: filteredOutages.length,
        new_outages: comparison.new_outages.length,
        escalated_outages: comparison.escalated_outages.length,
        resolved_outages: comparison.resolved_outages.length,
        fetch_duration_ms: fetchDurationMs,
      }),
      { headers: { 'Content-Type': 'application/json' }, status: 200 }
    );
  } catch (error) {
    console.error('Error:', error);
    return new Response(
      JSON.stringify({ success: false, error: String(error) }),
      { headers: { 'Content-Type': 'application/json' }, status: 500 }
    );
  }
});
