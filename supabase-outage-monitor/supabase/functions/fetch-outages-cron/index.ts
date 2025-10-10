// Cron trigger for fetch-outages edge function
// Runs every 10 minutes

import { createClient } from 'jsr:@supabase/supabase-js@2';

Deno.serve(async () => {
  try {
    // Get Supabase credentials from environment
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

    // Call the fetch-outages function
    const response = await fetch(`${supabaseUrl}/functions/v1/fetch-outages`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${supabaseKey}`,
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();

    if (!response.ok) {
      console.error(`Failed to trigger fetch-outages: ${response.status}`, data);
      return new Response(
        JSON.stringify({ error: 'Failed to trigger fetch-outages', details: data }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    console.log('Successfully triggered fetch-outages:', data);
    return new Response(
      JSON.stringify({ success: true, result: data }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    console.error('Error in cron job:', error);
    return new Response(
      JSON.stringify({ error: 'Internal error', message: error.message }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
});
