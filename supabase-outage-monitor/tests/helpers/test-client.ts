// Test database client helper

import { createClient, SupabaseClient } from 'jsr:@supabase/supabase-js@2';

export function getTestSupabaseClient(): SupabaseClient {
  // Use local Supabase instance for testing
  const supabaseUrl = Deno.env.get('SUPABASE_URL') || 'http://localhost:54321';
  const supabaseKey = Deno.env.get('SUPABASE_ANON_KEY') || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0';

  return createClient(supabaseUrl, supabaseKey);
}

export async function clearTestData(client: SupabaseClient): Promise<void> {
  // Clear tables in reverse order of dependencies
  await client.from('notification_log').delete().neq('id', '00000000-0000-0000-0000-000000000000');
  await client.from('outage_records').delete().neq('id', '00000000-0000-0000-0000-000000000000');
  await client.from('outage_snapshots').delete().neq('id', '00000000-0000-0000-0000-000000000000');
}

export async function setupTestZipCodes(client: SupabaseClient, zipCodes: string[]): Promise<void> {
  // Clear existing zip codes
  await client.from('zip_code_whitelist').delete().neq('id', '00000000-0000-0000-0000-000000000000');

  // Insert test zip codes
  if (zipCodes.length > 0) {
    const records = zipCodes.map(zip => ({ zipcode: zip, enabled: true }));
    await client.from('zip_code_whitelist').insert(records);
  }
}
