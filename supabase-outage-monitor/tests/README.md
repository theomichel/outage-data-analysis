# Supabase Outage Monitor Tests

Comprehensive test suite for the outage monitoring system.

## Test Strategy

The test suite uses **mocked API responses** to validate the entire notification pipeline:

1. **Mock utility APIs** to return test fixture data
2. **Fetch outages** using real fetcher functions (which hit the mocked APIs)
3. **Store snapshots** in the database using real database code
4. **Compare snapshots** using real comparison logic
5. **Generate notifications** using real notification code
6. **Validate results** against expectations CSV

This approach tests the complete pipeline while using your existing test data files.

## Directory Structure

```
tests/
├── fixtures/                           # Test data files
│   ├── 2025-08-29T224647-pge-events.json  # PGE snapshot 1
│   ├── 2025-08-29T225732-pge-events.json  # PGE snapshot 2
│   └── pge_outages_test_expectations.csv  # Expected results
├── helpers/                            # Test utilities
│   ├── mock-server.ts                  # HTTP mock server
│   ├── test-client.ts                  # Database test client
│   └── expectations.ts                 # CSV parser & validator
├── integration/                        # Integration tests
│   └── pge-notifications.test.ts       # Full PGE notification flow
├── run-tests.sh                        # Test runner script
└── README.md                           # This file
```

## Requirements

Before running tests, ensure you have the following installed:

### Required

1. **Docker Desktop**
   - Download: https://www.docker.com/products/docker-desktop/
   - Required for running Supabase local development environment
   - Must be running before starting Supabase

2. **Supabase CLI**
   ```bash
   npm install -g supabase
   ```

3. **Deno** (TypeScript runtime for running tests)
   ```bash
   # Windows (PowerShell)
   irm https://deno.land/setup.ps1 | iex

   # Or via Chocolatey
   choco install deno

   # Or via Scoop
   scoop install deno
   ```

### Verify Installation

```bash
# Check Docker is running
docker --version

# Check Supabase CLI
supabase --version

# Check Deno
deno --version
```

## Setup

### 1. Start Local Supabase

```bash
# From the project root
supabase start
```

This starts a local Supabase instance with:
- PostgreSQL database on port 54322
- API on port 54321
- Studio on port 54323

### 2. Apply Migrations

```bash
supabase db reset
```

This creates all the necessary tables (outage_snapshots, outage_records, etc.)

### 3. Install Dependencies

```bash
# From the project root
deno install
```

This downloads and caches all npm dependencies needed by the Supabase client library. This is a one-time step (unless dependencies change).

## Running Tests

### Run All Tests

```bash
# From the project root
./tests/run-tests.sh
```

Or manually:

```bash
deno test --allow-net --allow-read --allow-env tests/integration/
```

### Run Specific Test

```bash
deno test --allow-net --allow-read --allow-env tests/integration/pge-notifications.test.ts
```

### Watch Mode

```bash
deno test --allow-net --allow-read --allow-env --watch tests/integration/
```

## Test Output

The test will output:

1. **Fetching progress**: Shows data being fetched from mocked APIs
2. **Database operations**: Confirms snapshots are saved
3. **Comparison results**: Shows new/escalated/resolved outages detected
4. **Validation results**: Compares actual vs expected notifications

### Example Output

```
PGE Outage Notification Integration Test ...
  Setup: Clear test database ... ok (50ms)
  Snapshot 1: Fetch and store initial outages ... ok (120ms)
  Snapshot 2: Fetch and store updated outages ... ok (110ms)
  Compare snapshots and generate notifications ... ok (200ms)
  Validate notifications against expectations ...

================================================================================
TEST RESULTS
================================================================================
✓ Outage 8859: PASS
    Expected: new
    Actual:   new
    Test case: new notifiable normal outage: in current file, not in previous file

✓ Outage 8975: PASS
    Expected: new
    Actual:   new
    Test case: new notifiable large outage: in current file, not in previous file

...

--------------------------------------------------------------------------------
SUMMARY: 17 passed, 0 failed
================================================================================

ok (500ms)
```

## Expectations CSV Format

The expectations file defines what notifications should be generated:

```csv
outage_id,previous_customers_impacted,previous_expected_length_minutes,...,notification_expected,why
8859,,,,100,500,100,new,"new notifiable normal outage"
9119,2,500,100,100,500,100,escalated,"escalated small to large"
9112,160,500,100,,,,resolved,"resolved normal outage"
9237,,,,100,500,10,none,"doesn't meet elapsed time threshold"
```

## Adding New Tests

### For a New Utility

1. Add test fixtures to `tests/fixtures/`:
   - Two snapshot JSON files
   - One expectations CSV

2. Create a new test file in `tests/integration/`:

```typescript
import { createMockServer, mockPseApi } from '../helpers/mock-server.ts';
// ... rest of imports

Deno.test('PSE Outage Notification Test', async (t) => {
  const mockServer = createMockServer();

  await t.step('Setup', async () => {
    // Clear DB
  });

  await t.step('Snapshot 1', async () => {
    mockPseApi(mockServer, './tests/fixtures/pse-snapshot1.json');
    // ... fetch and save
  });

  // ... rest of test steps
});
```

### For New Test Cases

Add rows to the expectations CSV with:
- `outage_id` - The outage identifier
- Previous/current state values
- `notification_expected` - What notification should be sent (new/escalated/resolved/none)
- `why` - Description of the test case

## Troubleshooting

### Supabase not running

```
Error: Supabase is not running locally
```

**Solution**: Start Supabase with `supabase start`

### Database tables don't exist

```
Error: relation "outage_snapshots" does not exist
```

**Solution**: Apply migrations with `supabase db reset`

### Tests fail with connection errors

**Solution**: Check that ports aren't blocked:
- 54321 (API)
- 54322 (Database)

### Mock not intercepting requests

**Solution**: Check that the URL pattern in the mock matches the actual URL being fetched. Add debug logging to see what URLs are being requested.

## CI/CD Integration

To run tests in CI/CD:

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: supabase/setup-cli@v1
      - name: Start Supabase
        run: supabase start
      - name: Run Tests
        run: deno test --allow-net --allow-read --allow-env tests/
```

## Test Coverage

Current coverage:
- ✅ PGE fetcher and parser
- ✅ Database snapshot storage
- ✅ Outage comparison logic
- ✅ Notification generation
- ✅ All notification types (new, escalated, resolved)
- ✅ Threshold validation
- ⏳ PSE, SCL, SnoPUD (fixtures needed)
- ⏳ Zip code filtering (requires test setup)
