# Testing Guide

This guide covers the different types of tests and how to run them.

## Test Types

### 1. Component Integration Tests

**Purpose:** Test individual components work together correctly with mocked data

**Location:** `tests/integration/pge-component.test.ts`

**What it tests:**
- Data fetching and parsing
- Database operations
- Comparison logic
- Notification generation

**How to run:**
```powershell
# Reset database and load zip boundaries
supabase db reset
deno run --allow-read --allow-net --allow-env scripts/load-zip-boundaries.ts

# Run tests
deno test --allow-net --allow-read --allow-env tests/integration/pge-component.test.ts
```

**Advantages:**
- Fast execution (< 1 second)
- Easy to debug
- No external dependencies
- Good for development

### 2. End-to-End (E2E) Tests

**Purpose:** Test the entire system as it runs in production

**Location:** `tests/integration/pge-e2e.test.ts`

**What it tests:**
- Edge function invocation
- HTTP requests to mock servers
- Full data pipeline (fetch → parse → store → compare → notify)
- Environment variable configuration

**How to run:**

```powershell
# Step 1: Reset database and load zip boundaries
supabase db reset
deno run --allow-read --allow-net --allow-env scripts/load-zip-boundaries.ts

# Step 2: Start edge function with test configuration
supabase functions serve --env-file .env.test

# Step 3: In another terminal, run the E2E test
deno test --allow-net --allow-read --allow-env --allow-write tests/integration/pge-e2e.test.ts
```

**Note:** The E2E test:
1. Starts an HTTP mock server on port 9999 that serves test fixtures
2. Uses `.env.test` configuration (checked into repo) to point edge function to localhost:9999
3. Invokes the edge function via HTTP
4. Validates the complete data pipeline

**Advantages:**
- Tests production code path
- Validates HTTP layer
- True black-box testing
- Simple setup with pre-configured `.env.test`

**Disadvantages:**
- Requires edge function to be running
- Slower execution (2-3 seconds)

## Test Configuration

### Environment Variables

**Component tests:**
- `SKIP_CLEANUP=true` - Preserves test data for inspection

**E2E tests:**
- `SKIP_CLEANUP=true` - Preserves test data for inspection

### Database Inspection

To inspect the database during/after tests:

1. **Skip cleanup:**
   ```powershell
   $env:SKIP_CLEANUP='true'; deno test --allow-net --allow-read --allow-env tests/integration/pge-component.test.ts
   ```

2. **Open Supabase Studio:**
   ```powershell
   supabase db studio
   # Or visit: http://localhost:54323
   ```

3. **Query tables:**
   - `outage_records` - Individual outage records with zip codes
   - `outage_snapshots` - Snapshot metadata
   - `notification_log` - Sent notifications
   - `zip_code_whitelist` - Whitelisted zip codes
   - `zip_boundaries` - PostGIS geometries

## Running All Tests

```powershell
# Run all integration tests
deno test --allow-net --allow-read --allow-env --allow-write tests/integration/
```

## Continuous Integration

For CI environments, you can automate the E2E test:

```yaml
# Example GitHub Actions workflow
- name: Setup Supabase
  run: |
    supabase db reset
    deno run --allow-read --allow-net --allow-env scripts/load-zip-boundaries.ts

- name: Start edge function
  run: supabase functions serve --env-file .env.test &

- name: Wait for edge function
  run: sleep 5

- name: Run E2E tests
  run: deno test --allow-net --allow-read --allow-env --allow-write tests/integration/pge-e2e.test.ts
```

## Troubleshooting

### "Zip boundaries table is empty"

**Solution:** Load zip boundaries:
```powershell
deno run --allow-read --allow-net --allow-env scripts/load-zip-boundaries.ts
```

### "Edge function returns 401 Invalid JWT"

**Solution:** E2E test uses service role key. Make sure edge function is running.

### "No mock configured for <url>"

**Solution:** The edge function isn't using the mock URLs. Make sure:
1. `.env.test` was created
2. You restarted the edge function with `--env-file .env.test`

### "All zip codes are null in outage_records"

**Cause:** Zip boundaries weren't loaded before running tests.

**Solution:**
```powershell
supabase db reset
deno run --allow-read --allow-net --allow-env scripts/load-zip-boundaries.ts
```

### "Tests fail with resource leaks"

**Cause:** Supabase client maintains connection pools that may trigger Deno's resource sanitizer.

**Solution:** Tests already have `sanitizeResources: false` configured. This is expected and safe.

## Test Data

### Fixtures

Test fixtures are located in `tests/fixtures/`:
- `2025-08-29T224647-pge-events.json` - First snapshot (9 outages)
- `2025-08-29T225732-pge-events.json` - Second snapshot (13 outages)
- `pge_outages_test_expectations.csv` - Expected notifications

### Expectations Format

CSV format with columns:
```
outage_id,notification_type,elapsed_time_minutes,expected_length_minutes,customers_impacted,large_outage_threshold,customer_threshold,reason,test_case
```

Example:
```csv
8859,new,,,500,,100,,new notifiable normal outage: in current file, not in previous file
9234,,,,140,500,99,none,geo outside of bay area
```

- Empty `notification_type` means outage should be filtered
- `reason` can be "none" for filtered outages
- `test_case` is a human-readable description

## Writing New Tests

### Adding a new utility test

1. Create fixtures in `tests/fixtures/`
2. Create expectations CSV
3. Copy `pge-component.test.ts` and modify for new utility
4. Update mock server to handle new utility URL

### Adding test cases

1. Add row to expectations CSV
2. Ensure fixture data contains the outage
3. Run test to validate

## Best Practices

1. **Always reset database before tests** - Ensures clean state
2. **Use component tests for development** - Faster feedback
3. **Use E2E tests for regression** - Validates production behavior
4. **Inspect database when debugging** - Use `SKIP_CLEANUP=true`
5. **Keep fixtures realistic** - Use actual API responses when possible
