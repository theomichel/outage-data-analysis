// Shared types for the outage monitoring system

export type Utility = 'pse' | 'scl' | 'snopud' | 'pge';

export interface OutageRecord {
  id?: string;
  snapshot_id?: string;
  utility: Utility;
  outage_id: string;
  snapshot_time: string;
  start_time: string;
  customers_impacted: number;
  status: string;
  cause: string;
  est_restoration_time: string | null;
  center_lon: number;
  center_lat: number;
  radius: number;
  polygon: any;
  elapsed_time_minutes: number | null;
  expected_length_minutes: number | null;
  zipcode?: string | null;
  created_at?: string;
}

export interface OutageSnapshot {
  id?: string;
  utility: Utility;
  snapshot_time: string;
  outages: any;
  fetch_duration_ms?: number;
  created_at?: string;
}

export interface NotificationData {
  new_outages: OutageRecord[];
  resolved_outages: OutageRecord[];
  escalated_outages: OutageRecord[];
}

export interface ComparisonResult {
  new_outages: OutageRecord[];
  resolved_outages: OutageRecord[];
  escalated_outages: OutageRecord[];
  active_outages: OutageRecord[];
}

export interface Config {
  telegram_bot_token?: string;
  telegram_chat_id?: string;
  telegram_thread_id?: string;
  geocode_api_key?: string;
  customer_threshold: number;
  large_outage_threshold: number;
  elapsed_time_threshold_hours: number;
  expected_length_threshold_hours: number;
  enable_zip_filtering: boolean;
}

export interface NotificationLog {
  outage_record_id?: string;
  notification_type: 'new' | 'escalated' | 'resolved';
  outage_id: string;
  utility: Utility;
  message: string;
  sent_successfully: boolean;
  error_message?: string;
  notification_reason?: string;
}
