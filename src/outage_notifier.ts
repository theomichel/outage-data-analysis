import * as fs from 'fs';
import * as path from 'path';
import { glob } from 'glob';
import axios from 'axios';
import {
  OutageRow,
  parsePseFile,
  parseSclFile,
  parseSnopudFile,
  parsePgeFile,
  calculateExpectedLengthMinutes,
  calculateActiveDurationMinutes,
  reverseGeocode,
  getFilenameSuffixForUtility
} from './outage_utils.js';
import { loadZipCodes, getZipCode } from './zip_utils.js';

interface NotificationData {
  new_outages: OutageRow[];
  resolved_outages: OutageRow[];
  active_outages: OutageRow[];
}

interface Thresholds {
  length: number;
  customers: number;
  large_outage_customers: number;
  elapsed: number;
}

interface ProgramArgs {
  directory: string;
  remaining_expected_length_threshold: number;
  customer_threshold: number;
  large_outage_customer_threshold: number;
  elapsed_time_threshold: number;
  utility: string;
  telegram_token?: string;
  telegram_chat_id?: string;
  telegram_thread_id?: string;
  geocode_api_key?: string;
  notification_output_dir: string;
  zip_whitelist_file?: string;
  zip_boundaries_file?: string;
}

function getUtilityDisplayName(utility: string): string {
  if (utility === 'pge') {
    return 'PG&E';
  }
  return utility.toUpperCase();
}

function escapeMarkdown(text: string | null | undefined): string {
  if (text === null || text === undefined) {
    return '';
  }

  let result = String(text);
  result = result.replace(/\\/g, '\\\\');
  result = result.replace(/`/g, '\\`');
  result = result.replace(/\*/g, '\\*');
  result = result.replace(/_/g, '\\_');

  return result;
}

async function sendTelegramMessage(
  token: string,
  chatId: string,
  message: string,
  threadId?: string
): Promise<boolean> {
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  const data: any = {
    chat_id: chatId,
    text: message,
    link_preview_options: {
      is_disabled: true
    },
    parse_mode: 'Markdown'
  };

  if (threadId) {
    data.message_thread_id = threadId;
  }

  try {
    const response = await axios.post(url, data);

    if (response.status === 400) {
      console.log('HTTP 400 Bad Request from Telegram API:');
      console.log(`  URL: ${url}`);
      console.log(`  Chat ID: ${chatId}`);
      console.log(`  Thread ID: ${threadId}`);
      console.log(`  Message length: ${message.length} characters`);
      console.log(`  Message preview (first 200 chars): ${message.substring(0, 200)}...`);
      console.log(`  Request data: ${JSON.stringify(data)}`);
      console.log(`  Response status: ${response.status}`);
      console.log(`  Response headers: ${JSON.stringify(response.headers)}`);
      console.log(`  Response body: ${JSON.stringify(response.data)}`);

      try {
        const errorData = response.data;
        if (errorData.description) {
          console.log(`  Error description: ${errorData.description}`);
        }
        if (errorData.error_code) {
          console.log(`  Error code: ${errorData.error_code}`);
        }
        if (errorData.parameters) {
          console.log(`  Error parameters: ${JSON.stringify(errorData.parameters)}`);
        }

        const description = (errorData.description || '').toLowerCase();
        if (description.includes('message is too long')) {
          console.log("  → Message exceeds Telegram's 4096 character limit");
        } else if (description.includes('bad request: chat not found')) {
          console.log(`  → Chat ID ${chatId} not found or bot not added to chat`);
        } else if (description.includes('bad request: message thread not found')) {
          console.log(`  → Thread ID ${threadId} not found in chat ${chatId}`);
        } else if (description.includes('bad request: parse entities')) {
          console.log('  → Markdown parsing error in message content');
        } else if (description.includes('bad request: message to edit not found')) {
          console.log('  → Message to edit not found');
        } else if (description.includes('forbidden')) {
          console.log("  → Bot doesn't have permission to send messages to this chat");
        }
      } catch {
        console.log('  Could not parse error response as JSON');
      }

      return false;
    } else if (response.status >= 400) {
      console.log(`HTTP ${response.status} error from Telegram API:`);
      console.log(`  Response: ${JSON.stringify(response.data)}`);
      return false;
    }

    console.log('Telegram message sent successfully!');
    return true;
  } catch (e: any) {
    if (e.response) {
      console.log(`HTTP error sending Telegram message: ${e.response.status}`);
      console.log(`  Response: ${JSON.stringify(e.response.data)}`);
    } else if (e.request) {
      console.log(`Network error sending Telegram message: ${e.message}`);
    } else {
      console.log(`Unexpected error sending Telegram message: ${e}`);
    }
    return false;
  }
}

async function sendNotification(
  notificationData: NotificationData,
  thresholds: Thresholds,
  botToken?: string,
  chatId?: string,
  threadId?: string,
  geocodeApiKey?: string,
  notificationOutputDir: string = '.'
): Promise<void> {
  try {
    const { new_outages, resolved_outages, active_outages } = notificationData;
    const messagesToSend: Array<[string, string, string]> = [];
    const currentTime = new Date();

    // Create individual notification for each new outage
    for (const outage of new_outages) {
      const elapsedHours = (outage.elapsed_time_minutes || 0) / 60;

      let newMessage = '🚨 NEW OUTAGE 🚨\n\n';
      newMessage += `Utility/ID: ${getUtilityDisplayName(outage.utility)} / ${outage.outage_id}\n`;
      newMessage += `Customers: ${outage.customers_impacted.toLocaleString()} \n`;

      let expectedHoursString: string;
      if (outage.expected_length_minutes !== null && outage.expected_length_minutes !== undefined) {
        expectedHoursString = `${(outage.expected_length_minutes / 60).toFixed(1)}h`;
      } else {
        expectedHoursString = 'Unknown';
      }

      newMessage += `Elapsed / Remaining Time: ${elapsedHours.toFixed(1)}h / ${expectedHoursString} \n`;
      newMessage += `Status: ${outage.status}\n`;
      newMessage += `Cause: ${outage.cause}\n`;

      if (outage.center_lat !== null && outage.center_lon !== null) {
        const locationInfo = await reverseGeocode(outage.center_lat, outage.center_lon, geocodeApiKey);
        newMessage += `Location: ${locationInfo}\n`;
      }

      // Format time in Pacific timezone (simplified - doesn't handle DST perfectly)
      const pacificOffset = -8 * 60; // PST offset in minutes
      const pacificTime = new Date(currentTime.getTime() + pacificOffset * 60 * 1000);
      newMessage += `${pacificTime.toISOString().slice(0, 19).replace('T', ' ')} PST\n`;

      messagesToSend.push(['new', newMessage, outage.outage_id]);
    }

    // Create individual notification for each active (escalated) outage
    for (const outage of active_outages) {
      const elapsedHours = (outage.elapsed_time_minutes || 0) / 60;

      let escalatedMessage = '🚨 ESCALATED OUTAGE 🚨\n\n';
      escalatedMessage += `Utility/ID: ${getUtilityDisplayName(outage.utility)} / ${outage.outage_id}\n`;
      escalatedMessage += `Customers: ${outage.customers_impacted.toLocaleString()} \n`;

      let expectedHoursString: string;
      if (outage.expected_length_minutes !== null && outage.expected_length_minutes !== undefined) {
        expectedHoursString = `${(outage.expected_length_minutes / 60).toFixed(1)}h`;
      } else {
        expectedHoursString = 'Unknown';
      }

      escalatedMessage += `Elapsed / Remaining Time: ${elapsedHours.toFixed(1)}h / ${expectedHoursString} \n`;
      escalatedMessage += `Status: ${outage.status}\n`;
      escalatedMessage += `Cause: ${outage.cause}\n`;

      if (outage.notification_reason) {
        const escapedReason = escapeMarkdown(outage.notification_reason);
        escalatedMessage += `Reason: ${escapedReason}\n`;
      }

      if (outage.center_lat !== null && outage.center_lon !== null) {
        const locationInfo = await reverseGeocode(outage.center_lat, outage.center_lon, geocodeApiKey);
        escalatedMessage += `Location: ${locationInfo}\n`;
      }

      const pacificOffset = -8 * 60;
      const pacificTime = new Date(currentTime.getTime() + pacificOffset * 60 * 1000);
      escalatedMessage += `${pacificTime.toISOString().slice(0, 19).replace('T', ' ')} PST\n`;

      messagesToSend.push(['escalated', escalatedMessage, outage.outage_id]);
    }

    // Create individual notification for each resolved outage
    for (const outage of resolved_outages) {
      let resolvedMessage = '😌 RESOLVED OUTAGE 😌\n\n';
      resolvedMessage += `Utility/ID: ${getUtilityDisplayName(outage.utility)} / ${outage.outage_id}\n`;
      resolvedMessage += `Customers: ${outage.customers_impacted.toLocaleString()}\n`;

      if (outage.elapsed_time_minutes !== null && outage.elapsed_time_minutes !== undefined) {
        const actualHours = outage.elapsed_time_minutes / 60;
        resolvedMessage += `Actual Duration: ${actualHours.toFixed(1)}h\n`;
      }

      resolvedMessage += `Cause: ${outage.cause}\n`;

      if (outage.center_lat !== null && outage.center_lon !== null) {
        const locationInfo = await reverseGeocode(outage.center_lat, outage.center_lon, geocodeApiKey);
        resolvedMessage += `Location: ${locationInfo}\n`;
      }

      const pacificOffset = -8 * 60;
      const pacificTime = new Date(currentTime.getTime() + pacificOffset * 60 * 1000);
      resolvedMessage += `${pacificTime.toISOString().slice(0, 19).replace('T', ' ')} PST\n`;

      messagesToSend.push(['resolved', resolvedMessage, outage.outage_id]);
    }

    // Send each message separately
    for (const [msgType, message, outageId] of messagesToSend) {
      // Send Telegram notification if credentials provided
      if (botToken && chatId) {
        const success = await sendTelegramMessage(botToken, chatId, message, threadId);
        if (success) {
          const threadInfo = threadId ? ` (thread ${threadId})` : '';
          console.log(`Telegram ${msgType} outage notification sent for ${outageId} to chat ${chatId}${threadInfo}`);
        } else {
          console.log(`Failed to send Telegram ${msgType} outage notification for ${outageId}`);
        }
      } else {
        console.log(`Telegram credentials not provided, skipping ${msgType} notification for ${outageId}`);
      }

      // Save notification to timestamped file with outage ID
      const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace('T', '_').split('.')[0];
      const notificationFilename = `notification_${msgType}_${outageId}_${timestamp}.txt`;
      const notificationPath = path.join(notificationOutputDir, notificationFilename);
      fs.writeFileSync(notificationPath, message, 'utf-8');
      console.log(`${msgType.charAt(0).toUpperCase() + msgType.slice(1)} outage notification for ${outageId} saved to: ${notificationPath}`);
    }

    if (messagesToSend.length === 0) {
      console.log('No outages meeting criteria - no notification sent.');
    }
  } catch (e) {
    console.log(`Error sending notification: ${e}`);
  }
}

function printDataframePretty(outages: OutageRow[]): void {
  if (outages.length > 0) {
    console.log('outage_id\tcustomers_impacted\texpected_length_minutes\telapsed_time_minutes');
    for (const outage of outages) {
      console.log(
        `${outage.outage_id}\t${outage.customers_impacted}\t${outage.expected_length_minutes || 'N/A'}\t${outage.elapsed_time_minutes || 'N/A'}`
      );
    }
  } else {
    console.log('DataFrame is empty');
  }
}

function parseArgs(): ProgramArgs {
  const args = process.argv.slice(2);
  const parsed: any = {
    directory: '.',
    remaining_expected_length_threshold: 4.0,
    customer_threshold: 100,
    large_outage_customer_threshold: 1000,
    elapsed_time_threshold: 0.25,
    notification_output_dir: '.'
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '-d' || arg === '--directory') {
      parsed.directory = args[++i];
    } else if (arg === '-r' || arg === '--remaining_expected_length_threshold') {
      parsed.remaining_expected_length_threshold = parseFloat(args[++i]);
    } else if (arg === '-c' || arg === '--customer_threshold') {
      parsed.customer_threshold = parseInt(args[++i]);
    } else if (arg === '-lc' || arg === '--large_outage_customer_threshold') {
      parsed.large_outage_customer_threshold = parseInt(args[++i]);
    } else if (arg === '-e' || arg === '--elapsed_time_threshold') {
      parsed.elapsed_time_threshold = parseFloat(args[++i]);
    } else if (arg === '-u' || arg === '--utility') {
      parsed.utility = args[++i];
    } else if (arg === '--telegram-token') {
      parsed.telegram_token = args[++i];
    } else if (arg === '--telegram-chat-id') {
      parsed.telegram_chat_id = args[++i];
    } else if (arg === '--telegram-thread-id') {
      parsed.telegram_thread_id = args[++i];
    } else if (arg === '--geocode-api-key') {
      parsed.geocode_api_key = args[++i];
    } else if (arg === '--notification-output-dir') {
      parsed.notification_output_dir = args[++i];
    } else if (arg === '-zw' || arg === '--zip-whitelist-file') {
      parsed.zip_whitelist_file = args[++i];
    } else if (arg === '-zb' || arg === '--zip-boundaries-file') {
      parsed.zip_boundaries_file = args[++i];
    }
  }

  if (!parsed.utility) {
    console.error('Error: --utility (-u) is required');
    process.exit(1);
  }

  return parsed as ProgramArgs;
}

async function main() {
  const args = parseArgs();

  console.log(`====== analyze_current_outages.py starting for utility ${args.utility} =======`);

  // Convert thresholds from hours to minutes
  const expectedLengthThresholdMinutes = args.remaining_expected_length_threshold * 60;
  const elapsedTimeThresholdMinutes = args.elapsed_time_threshold * 60;

  console.log(`Expected length threshold: ${args.remaining_expected_length_threshold} hours (${expectedLengthThresholdMinutes} minutes)`);
  console.log(`Customer threshold: ${args.customer_threshold}`);
  console.log(`Large outage customer threshold: ${args.large_outage_customer_threshold}`);
  console.log(`Elapsed time threshold: ${args.elapsed_time_threshold} hours (${elapsedTimeThresholdMinutes} minutes)`);

  const filenameSuffix = getFilenameSuffixForUtility(args.utility);
  const filePattern = path.join(args.directory, '*' + filenameSuffix).replace(/\\/g, '/');
  console.log(`file pattern ${filePattern}`);
  const allFiles = (await glob(filePattern)).sort();

  if (allFiles.length < 2) {
    console.log('Not enough files to compare. Exiting.');
    process.exit(3);
  }

  // Load zip code whitelist and boundaries if provided
  let zipCodeWhitelist: string[] | null = null;
  if (args.zip_whitelist_file) {
    try {
      const content = fs.readFileSync(args.zip_whitelist_file, 'utf-8');
      zipCodeWhitelist = content.split('\n').map(line => line.trim()).filter(line => line.length > 0);
      console.log(`Loaded ${zipCodeWhitelist.length} zip codes from whitelist file`);

      if (args.zip_boundaries_file) {
        loadZipCodes(args.zip_boundaries_file);
      } else {
        console.log('Error: Zip whitelist provided without zip boundaries. Exiting.');
        process.exit(4);
      }
    } catch (e) {
      console.log(`Warning: Zip whitelist file not found: ${args.zip_whitelist_file}`);
    }
  }

  let isFirstFile = true;
  let previousFileOutages: OutageRow[] = [];
  let currentFileOutages: OutageRow[] = [];

  for (let fileIndex = 0; fileIndex < allFiles.length; fileIndex++) {
    const file = allFiles[fileIndex];
    console.log('====== starting processing for file =======');
    console.log(`file: ${file}`);

    const basename = path.basename(file);
    const dateTimePart = basename.split(filenameSuffix)[0];
    const gmtFileDateTime = new Date(dateTimePart.replace('T', ' ').replace(/(\d{2})(\d{2})(\d{2})$/, '$1:$2:$3'));

    previousFileOutages = currentFileOutages;
    const currentFileRows: OutageRow[] = [];

    if (args.utility === 'pse') {
      parsePseFile(file, currentFileRows, gmtFileDateTime, false);
    } else if (args.utility === 'scl') {
      parseSclFile(file, currentFileRows, gmtFileDateTime, false);
    } else if (args.utility === 'snopud') {
      parseSnopudFile(file, currentFileRows, gmtFileDateTime, false);
    } else if (args.utility === 'pge') {
      parsePgeFile(file, currentFileRows, gmtFileDateTime, false);
    } else {
      console.log('no utility specified, will not parse');
    }

    currentFileOutages = currentFileRows;

    // Filter outages by zipcode based on the whitelist
    if (currentFileOutages.length > 0 && zipCodeWhitelist !== null) {
      for (const outage of currentFileOutages) {
        outage.zipcode = getZipCode(outage.center_lon, outage.center_lat);
      }
      currentFileOutages = currentFileOutages.filter(o => zipCodeWhitelist!.includes(o.zipcode || ''));
    }

    // Add calculated columns
    if (currentFileOutages.length > 0) {
      for (const outage of currentFileOutages) {
        outage.expected_length_minutes = calculateExpectedLengthMinutes(gmtFileDateTime, outage.est_restoration_time) || undefined;
        outage.elapsed_time_minutes = calculateActiveDurationMinutes(outage.start_time, gmtFileDateTime) || undefined;
      }
    }

    console.log('current_file_df after zip filtering and adding expected length and elapsed time:');
    printDataframePretty(currentFileOutages);

    if (isFirstFile) {
      isFirstFile = false;
      previousFileOutages = currentFileOutages;
      console.log('This was the first file, skipping comparisons');
      continue;
    }

    // Compare previous and current file rowsets
    let newOutages: OutageRow[] = [];
    let resolvedOutages: OutageRow[] = [];
    let activeOutages: OutageRow[] = [];

    if (currentFileOutages.length === 0 && previousFileOutages.length === 0) {
      // Both empty
      newOutages = [];
      resolvedOutages = [];
      activeOutages = [];
    } else if (currentFileOutages.length === 0) {
      // All previous outages are resolved
      newOutages = [];
      resolvedOutages = [...previousFileOutages];
      activeOutages = [];
    } else if (previousFileOutages.length === 0) {
      // All current outages are new
      newOutages = [...currentFileOutages];
      resolvedOutages = [];
      activeOutages = [];
    } else {
      // Both have data
      const previousIds = new Set(previousFileOutages.map(o => o.outage_id));
      const currentIds = new Set(currentFileOutages.map(o => o.outage_id));

      newOutages = currentFileOutages.filter(o => !previousIds.has(o.outage_id));
      resolvedOutages = previousFileOutages.filter(o => !currentIds.has(o.outage_id));
      activeOutages = currentFileOutages.filter(o => previousIds.has(o.outage_id));
    }

    // Filter notifiable new outages
    const notifiableNewOutages = newOutages.filter(o => {
      const meetsThresholds =
        ((o.expected_length_minutes || 0) >= expectedLengthThresholdMinutes &&
          o.customers_impacted >= args.customer_threshold &&
          (o.elapsed_time_minutes || 0) >= elapsedTimeThresholdMinutes) ||
        o.customers_impacted >= args.large_outage_customer_threshold;
      return meetsThresholds;
    });

    // Filter notifiable resolved outages
    const notifiableResolvedOutages = resolvedOutages.filter(o => {
      const meetsThresholds =
        (o.customers_impacted >= args.customer_threshold &&
          (o.expected_length_minutes || 0) >= expectedLengthThresholdMinutes &&
          (o.elapsed_time_minutes || 0) >= elapsedTimeThresholdMinutes) ||
        o.customers_impacted >= args.large_outage_customer_threshold;
      return meetsThresholds;
    });

    // Check active outages
    const notifiableActiveOutages: OutageRow[] = [];
    if (activeOutages.length > 0) {
      const previousMap = new Map(previousFileOutages.map(o => [o.outage_id, o]));

      for (const current of activeOutages) {
        const previous = previousMap.get(current.outage_id);
        if (!previous) continue;

        const primaryThresholdsMet =
          (current.expected_length_minutes || 0) >= expectedLengthThresholdMinutes &&
          current.customers_impacted >= args.customer_threshold &&
          (current.elapsed_time_minutes || 0) >= elapsedTimeThresholdMinutes;

        const primaryThresholdsNotMetPreviously =
          (previous.expected_length_minutes === null ||
            previous.expected_length_minutes === undefined ||
            previous.expected_length_minutes < expectedLengthThresholdMinutes) ||
          previous.customers_impacted < args.customer_threshold ||
          (previous.elapsed_time_minutes === null ||
            previous.elapsed_time_minutes === undefined ||
            previous.elapsed_time_minutes < elapsedTimeThresholdMinutes);

        const largeOutageEscalation =
          current.customers_impacted >= args.large_outage_customer_threshold &&
          previous.customers_impacted < args.large_outage_customer_threshold;

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

            if (previous.customers_impacted < args.customer_threshold) {
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

          current.notification_reason = reasons.length > 0 ? reasons.join(', ') : 'unknown reason';
          notifiableActiveOutages.push(current);
        }
      }
    }

    console.log('notifiable_new_outages:');
    printDataframePretty(notifiableNewOutages);
    console.log('notifiable_resolved_outages:');
    printDataframePretty(notifiableResolvedOutages);
    console.log('notifiable_active_outages:');
    printDataframePretty(notifiableActiveOutages);

    // Print notification reasons for active outages
    if (notifiableActiveOutages.length > 0) {
      console.log('Active outage notification reasons:');
      for (const outage of notifiableActiveOutages) {
        console.log(`  Outage ${outage.outage_id}: ${outage.notification_reason}`);
      }
    }

    console.log('====== completed processing for file =======');

    // Send notification if there are notifiable outages
    console.log('sending notifications if there are new outages or resolved outages or notifiable active outages');
    if (notifiableNewOutages.length > 0 || notifiableResolvedOutages.length > 0 || notifiableActiveOutages.length > 0) {
      const thresholds: Thresholds = {
        length: args.remaining_expected_length_threshold,
        customers: args.customer_threshold,
        large_outage_customers: args.large_outage_customer_threshold,
        elapsed: args.elapsed_time_threshold
      };

      const notificationData: NotificationData = {
        new_outages: notifiableNewOutages,
        resolved_outages: notifiableResolvedOutages,
        active_outages: notifiableActiveOutages
      };

      await sendNotification(
        notificationData,
        thresholds,
        args.telegram_token,
        args.telegram_chat_id,
        args.telegram_thread_id,
        args.geocode_api_key,
        args.notification_output_dir
      );
    }
  }

  console.log('====== outage_notifier.py completed =======');
}

main().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
