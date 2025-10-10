#!/bin/bash
# Test runner script for Supabase Outage Monitor

set -e

echo "========================================="
echo "Supabase Outage Monitor Test Suite"
echo "========================================="

# Check if Supabase is running
if ! curl -s http://localhost:54321/rest/v1/ > /dev/null 2>&1; then
    echo "Error: Supabase is not running locally"
    echo "Please start it with: supabase start"
    exit 1
fi

echo "✓ Supabase local instance is running"
echo ""

# Set up environment variables for tests
export SUPABASE_URL="http://localhost:54321"
export SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"

# Run integration tests
echo "Running integration tests..."
deno test --allow-net --allow-read --allow-env tests/integration/

echo ""
echo "========================================="
echo "All tests complete!"
echo "========================================="
