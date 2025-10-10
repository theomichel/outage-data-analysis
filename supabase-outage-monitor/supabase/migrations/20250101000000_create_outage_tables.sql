-- Create outage_snapshots table
CREATE TABLE IF NOT EXISTS outage_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    utility TEXT NOT NULL CHECK (utility IN ('pse', 'scl', 'snopud', 'pge')),
    snapshot_time TIMESTAMPTZ NOT NULL,
    outages JSONB NOT NULL,
    fetch_duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(utility, snapshot_time)
);

-- Create outage_records table
CREATE TABLE IF NOT EXISTS outage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES outage_snapshots(id) ON DELETE CASCADE,
    utility TEXT NOT NULL,
    outage_id TEXT NOT NULL,
    snapshot_time TIMESTAMPTZ NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    customers_impacted INTEGER NOT NULL,
    status TEXT,
    cause TEXT,
    est_restoration_time TIMESTAMPTZ,
    center_lon DOUBLE PRECISION,
    center_lat DOUBLE PRECISION,
    radius DOUBLE PRECISION,
    polygon JSONB,
    elapsed_time_minutes INTEGER,
    expected_length_minutes INTEGER,
    zipcode TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create zip_code_whitelist table
CREATE TABLE IF NOT EXISTS zip_code_whitelist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zipcode TEXT NOT NULL UNIQUE,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create notification_log table
CREATE TABLE IF NOT EXISTS notification_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outage_record_id UUID REFERENCES outage_records(id),
    notification_type TEXT NOT NULL CHECK (notification_type IN ('new', 'escalated', 'resolved')),
    outage_id TEXT NOT NULL,
    utility TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_successfully BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    notification_reason TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_outage_snapshots_utility_time ON outage_snapshots(utility, snapshot_time DESC);
CREATE INDEX idx_outage_records_utility_snapshot ON outage_records(utility, snapshot_time DESC);
CREATE INDEX idx_outage_records_outage_id ON outage_records(utility, outage_id, snapshot_time DESC);
CREATE INDEX idx_outage_records_zipcode ON outage_records(zipcode) WHERE zipcode IS NOT NULL;
CREATE INDEX idx_notification_log_outage ON notification_log(utility, outage_id, sent_at DESC);

-- Add comments
COMMENT ON TABLE outage_snapshots IS 'Raw outage data snapshots from utility APIs';
COMMENT ON TABLE outage_records IS 'Individual outage records with calculated fields';
COMMENT ON TABLE zip_code_whitelist IS 'Zip codes to filter outages by';
COMMENT ON TABLE notification_log IS 'Log of all notifications sent';
