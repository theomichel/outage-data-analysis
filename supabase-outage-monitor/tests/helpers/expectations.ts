// CSV expectations parser and validator

import { parse } from 'https://deno.land/std@0.224.0/csv/mod.ts';

export interface Expectation {
  outage_id: number;
  previous_customers_impacted: number | null;
  previous_expected_length_minutes: number | null;
  previous_elapsed_time_minutes: number | null;
  current_customers_impacted: number | null;
  current_expected_length_minutes: number | null;
  current_elapsed_time_minutes: number | null;
  notification_expected: 'new' | 'escalated' | 'resolved' | 'none' | null;
  why: string;
}

export interface TestResult {
  outage_id: number;
  expected: string | null;
  actual: string | null;
  status: 'PASS' | 'FAIL';
  why: string;
}

export async function parseExpectations(csvFile: string): Promise<Expectation[]> {
  const content = await Deno.readTextFile(csvFile);
  const records = parse(content, { skipFirstRow: true });

  return records.map((row: any) => ({
    outage_id: parseInt(row.outage_id),
    previous_customers_impacted: row.previous_customers_impacted ? parseInt(row.previous_customers_impacted) : null,
    previous_expected_length_minutes: row.previous_expected_length_minutes ? parseInt(row.previous_expected_length_minutes) : null,
    previous_elapsed_time_minutes: row.previous_elapsed_time_minutes ? parseInt(row.previous_elapsed_time_minutes) : null,
    current_customers_impacted: row.current_customers_impacted ? parseInt(row.current_customers_impacted) : null,
    current_expected_length_minutes: row.current_expected_length_minutes ? parseInt(row.current_expected_length_minutes) : null,
    current_elapsed_time_minutes: row.current_elapsed_time_minutes ? parseInt(row.current_elapsed_time_minutes) : null,
    notification_expected: row.notification_expected === 'none' ? null : row.notification_expected,
    why: row.why,
  }));
}

export function validateNotifications(
  actualNotifications: Map<number, string>,
  expectations: Expectation[]
): { results: TestResult[]; passedCount: number; failedCount: number } {
  const results: TestResult[] = [];
  let passedCount = 0;
  let failedCount = 0;

  for (const expectation of expectations) {
    const outageId = expectation.outage_id;
    const expected = expectation.notification_expected;
    const actual = actualNotifications.get(outageId) || null;

    const status = actual === expected ? 'PASS' : 'FAIL';

    if (status === 'PASS') {
      passedCount++;
    } else {
      failedCount++;
    }

    results.push({
      outage_id: outageId,
      expected,
      actual,
      status,
      why: expectation.why,
    });
  }

  return { results, passedCount, failedCount };
}

export function printTestResults(
  results: TestResult[],
  passedCount: number,
  failedCount: number
): void {
  console.log('\n' + '='.repeat(80));
  console.log('NOTIFICATION VALIDATION RESULTS');
  console.log('='.repeat(80));

  // Only show failed tests by default (show all with verbose flag if needed)
  const failedResults = results.filter(r => r.status === 'FAIL');

  if (failedResults.length > 0) {
    console.log('\nFAILED CASES:');
    for (const result of failedResults) {
      console.log(`\n✗ Outage ${result.outage_id}:`);
      console.log(`    Expected: ${result.expected}`);
      console.log(`    Actual:   ${result.actual}`);
      console.log(`    Test case: ${result.why}`);
    }
  }

  console.log('\n' + '-'.repeat(80));
  if (failedCount === 0) {
    console.log(`✓ ALL TESTS PASSED: ${passedCount}/${passedCount}`);
  } else {
    console.log(`RESULTS: ${passedCount} passed, ${failedCount} failed (${passedCount + failedCount} total)`);
  }
  console.log('='.repeat(80) + '\n');
}
