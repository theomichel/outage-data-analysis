// Integration test for PGE outage notification flow

import { assertEquals } from 'https://deno.land/std@0.224.0/assert/mod.ts';
import { createMockServer, mockPgeApi } from '../helpers/mock-server.ts';
import { getTestSupabaseClient, clearTestData } from '../helpers/test-client.ts';
import { parseExpectations, validateNotifications, printTestResults } from '../helpers/expectations.ts';
import { fetchPgeOutages } from '../../supabase/functions/_shared/fetchers.ts';
import {
  saveSnapshot,
  saveOutageRecords,
  getPreviousSnapshot,
  getPreviousOutageRecords,
} from '../../supabase/functions/_shared/database.ts';
import { compareOutages } from '../../supabase/functions/_shared/comparison.ts';
import { sendNotifications } from '../../supabase/functions/_shared/notifications.ts';
import type { Config } from '../../supabase/functions/_shared/types.ts';

// Set to true to preserve test data for inspection
const SKIP_CLEANUP = Deno.env.get('SKIP_CLEANUP') === 'true';

Deno.test({
  name: 'PGE Outage Notification Integration Test',
  sanitizeResources: false,
  sanitizeOps: false,
  fn: async (t) => {
  const mockServer = createMockServer();
  const client = getTestSupabaseClient();

  // Test configuration
  const config: Config = {
    customer_threshold: 100,
    large_outage_threshold: 1000,
    elapsed_time_threshold_hours: 0.25,
    expected_length_threshold_hours: 4.0,
    enable_zip_filtering: true,
  };

  await t.step('Setup: Clear test database', async () => {
    await clearTestData(client);
    console.log('Test database cleared');
  });

  let snapshot1Id: string;
  let snapshot2Id: string;

  await t.step('Snapshot 1: Fetch and store initial outages', async () => {
    // Mock PGE API to return first test file
    const fixture1 = './tests/fixtures/2025-08-29T224647-pge-events.json';
    mockPgeApi(mockServer, fixture1);

    const snapshot1Time = new Date('2025-08-29T22:46:47Z');
    console.log(`\nFetching snapshot 1 at ${snapshot1Time.toISOString()}...`);

    // Fetch outages (this calls the mocked API)
    const outages1 = await fetchPgeOutages(snapshot1Time);
    console.log(`Fetched ${outages1.length} outages from snapshot 1`);

    // Save to database
    snapshot1Id = await saveSnapshot(client, 'pge', snapshot1Time, outages1, 100);
    await saveOutageRecords(client, snapshot1Id, outages1);
    console.log(`Saved snapshot 1 with ID: ${snapshot1Id}`);

    assertEquals(outages1.length > 0, true, 'Should have fetched outages from snapshot 1');
  });

  await t.step('Snapshot 2: Fetch and store updated outages', async () => {
    // Mock PGE API to return second test file
    const fixture2 = './tests/fixtures/2025-08-29T225732-pge-events.json';
    mockPgeApi(mockServer, fixture2);

    const snapshot2Time = new Date('2025-08-29T22:57:32Z');
    console.log(`\nFetching snapshot 2 at ${snapshot2Time.toISOString()}...`);

    // Fetch outages (this calls the mocked API)
    const outages2 = await fetchPgeOutages(snapshot2Time);
    console.log(`Fetched ${outages2.length} outages from snapshot 2`);

    // Save to database
    snapshot2Id = await saveSnapshot(client, 'pge', snapshot2Time, outages2, 100);
    await saveOutageRecords(client, snapshot2Id, outages2);
    console.log(`Saved snapshot 2 with ID: ${snapshot2Id}`);

    assertEquals(outages2.length > 0, true, 'Should have fetched outages from snapshot 2');
  });

  await t.step('Compare snapshots and generate notifications', async () => {
    console.log('\nComparing snapshots...');

    // Get previous and current outages from database
    const previousSnapshot = await getPreviousSnapshot(client, 'pge', new Date('2025-08-29T22:57:32Z'));
    assertEquals(previousSnapshot !== null, true, 'Should find previous snapshot');

    const previousOutages = await getPreviousOutageRecords(client, previousSnapshot!.id!, config.enable_zip_filtering);
    const currentOutages = await getPreviousOutageRecords(client, snapshot2Id, config.enable_zip_filtering);

    console.log(`Previous outages: ${previousOutages.length}`);
    console.log(`Current outages: ${currentOutages.length}`);

    // Run comparison logic
    const comparison = compareOutages(currentOutages, previousOutages, config);

    console.log(`\nComparison results:`);
    console.log(`  New outages: ${comparison.new_outages.length}`);
    console.log(`  Escalated outages: ${comparison.escalated_outages.length}`);
    console.log(`  Resolved outages: ${comparison.resolved_outages.length}`);

    // Mock Telegram API (we don't want to actually send messages)
    const originalFetch = globalThis.fetch;
    const telegramCalls: any[] = [];

    globalThis.fetch = async (input: string | URL | Request, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;

      if (url.includes('api.telegram.org')) {
        // Capture the call but don't actually send
        telegramCalls.push({ url, init });
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }

      return originalFetch(input, init);
    };

    // Send notifications (will be mocked)
    const notificationLogs = await sendNotifications(
      comparison.new_outages,
      comparison.escalated_outages,
      comparison.resolved_outages,
      config
    );

    globalThis.fetch = originalFetch;

    console.log(`\nGenerated ${notificationLogs.length} notifications`);

    // Save notification logs to database
    for (const log of notificationLogs) {
      const { error } = await client.from('notification_log').insert(log);
      if (error) {
        console.error('Error saving notification log:', error);
      }
    }
  });

  await t.step('Validate notifications against expectations', async () => {
    console.log('\nValidating notifications...');

    // Load expectations
    const expectations = await parseExpectations('./tests/fixtures/pge_outages_test_expectations.csv');
    console.log(`Loaded ${expectations.length} expectations`);

    // Query notification logs from database
    const { data: logs, error } = await client
      .from('notification_log')
      .select('outage_id, notification_type')
      .eq('utility', 'pge');

    if (error) {
      throw new Error(`Failed to query notification logs: ${error.message}`);
    }

    // Build map of outage_id -> notification_type
    const actualNotifications = new Map<number, string>();
    for (const log of logs || []) {
      const outageId = parseInt(log.outage_id);
      actualNotifications.set(outageId, log.notification_type);
    }

    console.log(`Found ${actualNotifications.size} actual notifications in database`);

    // Validate
    const { results, passedCount, failedCount } = validateNotifications(actualNotifications, expectations);

    // Print results
    printTestResults(results, passedCount, failedCount);

    // Assert all tests passed
    if (failedCount > 0) {
      throw new Error(`❌ ${failedCount} of ${passedCount + failedCount} notification validation(s) failed`);
    }

    console.log(`✅ All ${passedCount} notification validations passed`);
  });

  await t.step('Cleanup: Clear test data and restore mocks', async () => {
    if (!SKIP_CLEANUP) {
      await clearTestData(client);
    }
    mockServer.restore();
    console.log(SKIP_CLEANUP ? '\nTest cleanup complete (data preserved for inspection)' : '\nTest cleanup complete');
  });
  },
});
