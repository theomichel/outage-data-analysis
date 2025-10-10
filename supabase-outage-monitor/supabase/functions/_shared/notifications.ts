// Notification sending logic

import type { OutageRecord, Config, NotificationLog, Utility } from './types.ts';

function getUtilityDisplayName(utility: Utility): string {
  if (utility === 'pge') return 'PG&E';
  return utility.toUpperCase();
}

function escapeMarkdown(text: string | null | undefined): string {
  if (text === null || text === undefined) return '';

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
): Promise<{ success: boolean; error?: string }> {
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  const data: any = {
    chat_id: chatId,
    text: message,
    link_preview_options: {
      is_disabled: true,
    },
    parse_mode: 'Markdown',
  };

  if (threadId) {
    data.message_thread_id = threadId;
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Telegram API error:', errorData);
      return { success: false, error: JSON.stringify(errorData) };
    }

    console.log('Telegram message sent successfully');
    return { success: true };
  } catch (e) {
    console.error('Error sending Telegram message:', e);
    return { success: false, error: String(e) };
  }
}

async function reverseGeocode(lat: number, lon: number, apiKey?: string): Promise<string> {
  const mapsUrl = `https://maps.google.com/maps?q=${lat.toFixed(6)},${lon.toFixed(6)}`;

  if (!apiKey) return mapsUrl;

  try {
    const url = `https://geocode.maps.co/reverse?lat=${lat}&lon=${lon}&api_key=${apiKey}`;
    const response = await fetch(url);
    const data = await response.json();
    const address = data.address || {};

    const STATE_ABBR: { [key: string]: string } = {
      washington: 'WA',
      california: 'CA',
      // Add more as needed
    };

    const suburb = address.suburb || '';
    const city = address.city || address.town || '';
    const county = address.county || '';
    const state = address.state || '';
    const stateAbbr = state ? STATE_ABBR[state.toLowerCase()] || state : '';

    if (suburb && city && stateAbbr) {
      return `[${suburb}, ${city}, ${stateAbbr}](${mapsUrl})`;
    } else if (city && stateAbbr) {
      return `[${city}, ${stateAbbr}](${mapsUrl})`;
    } else if (county && stateAbbr) {
      return `[${county}, ${stateAbbr}](${mapsUrl})`;
    } else if (stateAbbr) {
      return `[${stateAbbr}](${mapsUrl})`;
    }

    return mapsUrl;
  } catch (e) {
    console.warn(`Error reverse geocoding ${lat}, ${lon}:`, e);
    return mapsUrl;
  }
}

async function createNewOutageMessage(outage: OutageRecord, config: Config): Promise<string> {
  const elapsedHours = (outage.elapsed_time_minutes || 0) / 60;

  let message = '🚨 NEW OUTAGE 🚨\n\n';
  message += `Utility/ID: ${getUtilityDisplayName(outage.utility)} / ${outage.outage_id}\n`;
  message += `Customers: ${outage.customers_impacted.toLocaleString()} \n`;

  const expectedHoursString =
    outage.expected_length_minutes !== null && outage.expected_length_minutes !== undefined
      ? `${(outage.expected_length_minutes / 60).toFixed(1)}h`
      : 'Unknown';

  message += `Elapsed / Remaining Time: ${elapsedHours.toFixed(1)}h / ${expectedHoursString} \n`;
  message += `Status: ${outage.status}\n`;
  message += `Cause: ${outage.cause}\n`;

  if (outage.center_lat && outage.center_lon) {
    const locationInfo = await reverseGeocode(outage.center_lat, outage.center_lon, config.geocode_api_key);
    message += `Location: ${locationInfo}\n`;
  }

  const currentTime = new Date();
  const pacificOffset = -8 * 60;
  const pacificTime = new Date(currentTime.getTime() + pacificOffset * 60 * 1000);
  message += `${pacificTime.toISOString().slice(0, 19).replace('T', ' ')} PST\n`;

  return message;
}

async function createEscalatedOutageMessage(outage: OutageRecord, config: Config): Promise<string> {
  const elapsedHours = (outage.elapsed_time_minutes || 0) / 60;

  let message = '🚨 ESCALATED OUTAGE 🚨\n\n';
  message += `Utility/ID: ${getUtilityDisplayName(outage.utility)} / ${outage.outage_id}\n`;
  message += `Customers: ${outage.customers_impacted.toLocaleString()} \n`;

  const expectedHoursString =
    outage.expected_length_minutes !== null && outage.expected_length_minutes !== undefined
      ? `${(outage.expected_length_minutes / 60).toFixed(1)}h`
      : 'Unknown';

  message += `Elapsed / Remaining Time: ${elapsedHours.toFixed(1)}h / ${expectedHoursString} \n`;
  message += `Status: ${outage.status}\n`;
  message += `Cause: ${outage.cause}\n`;

  const notificationReason = (outage as any).notification_reason;
  if (notificationReason) {
    const escapedReason = escapeMarkdown(notificationReason);
    message += `Reason: ${escapedReason}\n`;
  }

  if (outage.center_lat && outage.center_lon) {
    const locationInfo = await reverseGeocode(outage.center_lat, outage.center_lon, config.geocode_api_key);
    message += `Location: ${locationInfo}\n`;
  }

  const currentTime = new Date();
  const pacificOffset = -8 * 60;
  const pacificTime = new Date(currentTime.getTime() + pacificOffset * 60 * 1000);
  message += `${pacificTime.toISOString().slice(0, 19).replace('T', ' ')} PST\n`;

  return message;
}

async function createResolvedOutageMessage(outage: OutageRecord, config: Config): Promise<string> {
  let message = '😌 RESOLVED OUTAGE 😌\n\n';
  message += `Utility/ID: ${getUtilityDisplayName(outage.utility)} / ${outage.outage_id}\n`;
  message += `Customers: ${outage.customers_impacted.toLocaleString()}\n`;

  if (outage.elapsed_time_minutes !== null && outage.elapsed_time_minutes !== undefined) {
    const actualHours = outage.elapsed_time_minutes / 60;
    message += `Actual Duration: ${actualHours.toFixed(1)}h\n`;
  }

  message += `Cause: ${outage.cause}\n`;

  if (outage.center_lat && outage.center_lon) {
    const locationInfo = await reverseGeocode(outage.center_lat, outage.center_lon, config.geocode_api_key);
    message += `Location: ${locationInfo}\n`;
  }

  const currentTime = new Date();
  const pacificOffset = -8 * 60;
  const pacificTime = new Date(currentTime.getTime() + pacificOffset * 60 * 1000);
  message += `${pacificTime.toISOString().slice(0, 19).replace('T', ' ')} PST\n`;

  return message;
}

export async function sendNotifications(
  newOutages: OutageRecord[],
  escalatedOutages: OutageRecord[],
  resolvedOutages: OutageRecord[],
  config: Config
): Promise<NotificationLog[]> {
  const logs: NotificationLog[] = [];

  // Send new outage notifications
  for (const outage of newOutages) {
    const message = await createNewOutageMessage(outage, config);
    let result: { success: boolean; error?: string } = { success: false, error: 'No Telegram credentials provided' };

    if (config.telegram_bot_token && config.telegram_chat_id) {
      result = await sendTelegramMessage(
        config.telegram_bot_token,
        config.telegram_chat_id,
        message,
        config.telegram_thread_id
      );
    }

    logs.push({
      outage_record_id: outage.id,
      notification_type: 'new',
      outage_id: outage.outage_id,
      utility: outage.utility,
      message,
      sent_successfully: result.success,
      error_message: result.error,
    });
  }

  // Send escalated outage notifications
  for (const outage of escalatedOutages) {
    const message = await createEscalatedOutageMessage(outage, config);
    let result: { success: boolean; error?: string } = { success: false, error: 'No Telegram credentials provided' };

    if (config.telegram_bot_token && config.telegram_chat_id) {
      result = await sendTelegramMessage(
        config.telegram_bot_token,
        config.telegram_chat_id,
        message,
        config.telegram_thread_id
      );
    }

    logs.push({
      outage_record_id: outage.id,
      notification_type: 'escalated',
      outage_id: outage.outage_id,
      utility: outage.utility,
      message,
      sent_successfully: result.success,
      error_message: result.error,
      notification_reason: (outage as any).notification_reason,
    });
  }

  // Send resolved outage notifications
  for (const outage of resolvedOutages) {
    const message = await createResolvedOutageMessage(outage, config);
    let result: { success: boolean; error?: string } = { success: false, error: 'No Telegram credentials provided' };

    if (config.telegram_bot_token && config.telegram_chat_id) {
      result = await sendTelegramMessage(
        config.telegram_bot_token,
        config.telegram_chat_id,
        message,
        config.telegram_thread_id
      );
    }

    logs.push({
      outage_record_id: outage.id,
      notification_type: 'resolved',
      outage_id: outage.outage_id,
      utility: outage.utility,
      message,
      sent_successfully: result.success,
      error_message: result.error,
    });
  }

  return logs;
}
