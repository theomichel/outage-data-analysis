// Outage comparison logic

import type { OutageRecord, ComparisonResult, Config } from './types.ts';

export function compareOutages(
  currentOutages: OutageRecord[],
  previousOutages: OutageRecord[],
  config: Config
): ComparisonResult {
  const { customer_threshold, large_outage_threshold, elapsed_time_threshold_hours, expected_length_threshold_hours } =
    config;

  const elapsedTimeThresholdMinutes = elapsed_time_threshold_hours * 60;
  const expectedLengthThresholdMinutes = expected_length_threshold_hours * 60;

  // Handle empty cases
  if (currentOutages.length === 0 && previousOutages.length === 0) {
    return { new_outages: [], resolved_outages: [], escalated_outages: [], active_outages: [] };
  }

  if (currentOutages.length === 0) {
    const resolvedOutages = filterNotifiable(previousOutages, config);
    return { new_outages: [], resolved_outages: resolvedOutages, escalated_outages: [], active_outages: [] };
  }

  if (previousOutages.length === 0) {
    const newOutages = filterNotifiable(currentOutages, config);
    return { new_outages: newOutages, resolved_outages: [], escalated_outages: [], active_outages: [] };
  }

  // Build maps for quick lookup
  const previousIds = new Set(previousOutages.map((o) => o.outage_id));
  const currentIds = new Set(currentOutages.map((o) => o.outage_id));
  const previousMap = new Map(previousOutages.map((o) => [o.outage_id, o]));

  // Find new, resolved, and active outages
  const newOutages = currentOutages.filter((o) => !previousIds.has(o.outage_id));
  const resolvedOutages = previousOutages.filter((o) => !currentIds.has(o.outage_id));
  const activeOutages = currentOutages.filter((o) => previousIds.has(o.outage_id));

  // Filter notifiable new outages
  const notifiableNewOutages = filterNotifiable(newOutages, config);

  // Filter notifiable resolved outages
  const notifiableResolvedOutages = filterNotifiable(resolvedOutages, config);

  // Find escalated outages (active outages that now meet thresholds but didn't before)
  const escalatedOutages: OutageRecord[] = [];

  for (const current of activeOutages) {
    const previous = previousMap.get(current.outage_id);
    if (!previous) continue;

    const primaryThresholdsMet =
      (current.expected_length_minutes || 0) >= expectedLengthThresholdMinutes &&
      current.customers_impacted >= customer_threshold &&
      (current.elapsed_time_minutes || 0) >= elapsedTimeThresholdMinutes;

    const primaryThresholdsNotMetPreviously =
      (previous.expected_length_minutes === null ||
        previous.expected_length_minutes === undefined ||
        previous.expected_length_minutes < expectedLengthThresholdMinutes) ||
      previous.customers_impacted < customer_threshold ||
      (previous.elapsed_time_minutes === null ||
        previous.elapsed_time_minutes === undefined ||
        previous.elapsed_time_minutes < elapsedTimeThresholdMinutes);

    const largeOutageEscalation =
      current.customers_impacted >= large_outage_threshold && previous.customers_impacted < large_outage_threshold;

    if ((primaryThresholdsMet && primaryThresholdsNotMetPreviously) || largeOutageEscalation) {
      const reasons: string[] = [];

      if (primaryThresholdsMet && primaryThresholdsNotMetPreviously) {
        if (
          previous.expected_length_minutes === null ||
          previous.expected_length_minutes === undefined ||
          previous.expected_length_minutes < expectedLengthThresholdMinutes
        ) {
          const prevExpected =
            previous.expected_length_minutes !== null && previous.expected_length_minutes !== undefined
              ? `${(previous.expected_length_minutes / 60).toFixed(1)}h`
              : 'na';
          const currExpected =
            current.expected_length_minutes !== null && current.expected_length_minutes !== undefined
              ? `${(current.expected_length_minutes / 60).toFixed(1)}h`
              : 'na';
          reasons.push(`expected_length (${prevExpected}=>${currExpected})`);
        }

        if (previous.customers_impacted < customer_threshold) {
          reasons.push(`customers (${previous.customers_impacted}=>${current.customers_impacted})`);
        }

        if (
          previous.elapsed_time_minutes === null ||
          previous.elapsed_time_minutes === undefined ||
          previous.elapsed_time_minutes < elapsedTimeThresholdMinutes
        ) {
          const prevElapsed =
            previous.elapsed_time_minutes !== null && previous.elapsed_time_minutes !== undefined
              ? `${(previous.elapsed_time_minutes / 60).toFixed(1)}h`
              : 'na';
          const currElapsed =
            current.elapsed_time_minutes !== null && current.elapsed_time_minutes !== undefined
              ? `${(current.elapsed_time_minutes / 60).toFixed(1)}h`
              : 'na';
          reasons.push(`elapsed_time (${prevElapsed}=>${currElapsed})`);
        }
      }

      if (largeOutageEscalation) {
        reasons.push(`customers (${previous.customers_impacted}=>${current.customers_impacted})`);
      }

      // Create a copy with notification_reason added
      const escalatedOutage = { ...current };
      (escalatedOutage as any).notification_reason = reasons.length > 0 ? reasons.join(', ') : 'unknown reason';
      escalatedOutages.push(escalatedOutage);
    }
  }

  return {
    new_outages: notifiableNewOutages,
    resolved_outages: notifiableResolvedOutages,
    escalated_outages: escalatedOutages,
    active_outages: activeOutages,
  };
}

function filterNotifiable(outages: OutageRecord[], config: Config): OutageRecord[] {
  const { customer_threshold, large_outage_threshold, elapsed_time_threshold_hours, expected_length_threshold_hours } =
    config;

  const elapsedTimeThresholdMinutes = elapsed_time_threshold_hours * 60;
  const expectedLengthThresholdMinutes = expected_length_threshold_hours * 60;

  return outages.filter((o) => {
    const meetsThresholds =
      ((o.expected_length_minutes || 0) >= expectedLengthThresholdMinutes &&
        o.customers_impacted >= customer_threshold &&
        (o.elapsed_time_minutes || 0) >= elapsedTimeThresholdMinutes) ||
      o.customers_impacted >= large_outage_threshold;
    return meetsThresholds;
  });
}
