// True end-to-end integration test - invokes the edge function directly
// Requires edge function to be running with: supabase functions serve --env-file .env.test

import { assertEquals } from 'https://deno.land/std@0.224.0/assert/mod.ts';
import { startHttpMockServer, mockPgeRoute, type HttpMockServer } from '../helpers/http-mock-server.ts';
import { getTestSupabaseClient, clearTestData } from '../helpers/test-client.ts';
import { parseExpectations, validateNotifications, printTestResults } from '../helpers/expectations.ts';

// Set to true to preserve test data for inspection
const SKIP_CLEANUP = Deno.env.get('SKIP_CLEANUP') === 'true';

Deno.test({
  name: 'PGE Outage E2E Test - Edge Function',
  sanitizeResources: false,
  sanitizeOps: false,
  fn: async (t) => {
    let httpMockServer: HttpMockServer | null = null;
    const client = getTestSupabaseClient();

    // Edge function endpoint
    const EDGE_FUNCTION_URL = 'http://localhost:54321/functions/v1/fetch-outages';
    // Local development service role key - safe to commit (not used in production)
    const SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ||
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU';

    await t.step('Setup: Start HTTP mock server', async () => {
      httpMockServer = await startHttpMockServer(9999);
      console.log('HTTP mock server started on port 9999');
    });

    await t.step('Setup: Clear test database', async () => {
      await clearTestData(client);
      console.log('Test database cleared');
    });

    await t.step('Snapshot 1: Invoke edge function with first fixture', async () => {
      // Configure mock server to return first test file
      const fixture1 = './tests/fixtures/2025-08-29T224647-pge-events.json';
      mockPgeRoute(httpMockServer!, fixture1);

      console.log('\nInvoking edge function for snapshot 1...');

      // Invoke the edge function
      const response = await fetch(EDGE_FUNCTION_URL, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${SERVICE_ROLE_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });

      const result = await response.json();
      console.log('Edge function response:', JSON.stringify(result, null, 2));

      assertEquals(response.status, 200, 'Edge function should return 200');
      assertEquals(result.success, true, 'Edge function should succeed');

      // First snapshot should have no comparison (no previous data)
      const pgeResult = result.results.find((r: any) => r.utility === 'pge');
      assertEquals(pgeResult !== undefined, true, 'Should have PGE result');
      assertEquals(pgeResult.status, 'success', 'PGE processing should succeed');
      assertEquals(pgeResult.current_outages > 0, true, 'Should have fetched outages');
    });

    await t.step('Snapshot 2: Invoke edge function with second fixture', async () => {
      // Configure mock server to return second test file
      const fixture2 = './tests/fixtures/2025-08-29T225732-pge-events.json';
      mockPgeRoute(httpMockServer!, fixture2);

      console.log('\nInvoking edge function for snapshot 2...');

      // Invoke the edge function again
      const response = await fetch(EDGE_FUNCTION_URL, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${SERVICE_ROLE_KEY}`,
          'Content-Type': 'application/json',
        },
      });

      const result = await response.json();
      console.log('Edge function response:', JSON.stringify(result, null, 2));

      assertEquals(response.status, 200, 'Edge function should return 200');
      assertEquals(result.success, true, 'Edge function should succeed');

      // Second snapshot should have comparison results
      const pgeResult = result.results.find((r: any) => r.utility === 'pge');
      assertEquals(pgeResult !== undefined, true, 'Should have PGE result');
      assertEquals(pgeResult.status, 'success', 'PGE processing should succeed');

      console.log(`\nComparison results from edge function:`);
      console.log(`  New outages: ${pgeResult.new_outages}`);
      console.log(`  Escalated outages: ${pgeResult.escalated_outages}`);
      console.log(`  Resolved outages: ${pgeResult.resolved_outages}`);
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

    await t.step('Cleanup: Shutdown mock server and clear test data', async () => {
      if (httpMockServer) {
        await httpMockServer.shutdown();
      }
      if (!SKIP_CLEANUP) {
        await clearTestData(client);
      }

      console.log(SKIP_CLEANUP ? '\nTest cleanup complete (data preserved for inspection)' : '\nTest cleanup complete');
    });
  },
});
