-- The Backlot — shared ClickHouse data foundation
-- One data lake, six specialist agents. Every table below is queried by at
-- least two agents, which is what lets the Control Room orchestrator
-- correlate findings across domains (e.g. a Ghost Ads revenue leak that
-- lines up in time with a Premiere Pulse buffering anomaly).

CREATE DATABASE IF NOT EXISTS backlot;

-- Dimension: titles catalog, joined into almost every query for readable output.
CREATE TABLE IF NOT EXISTS backlot.titles
(
    title_id     String,
    title_name   String,
    genre        LowCardinality(String),
    release_date Date,
    budget_usd   Float64
)
ENGINE = MergeTree
ORDER BY title_id;

-- Fact: raw playback telemetry. Backbone of Premiere Pulse and Churn Early-Warning.
CREATE TABLE IF NOT EXISTS backlot.play_events
(
    event_time         DateTime64(3),
    session_id         String,
    user_id            String,
    title_id           String,
    territory          LowCardinality(String),
    device_type        LowCardinality(String),
    device_id          String,
    cdn_node           LowCardinality(String),
    bitrate_kbps       UInt32,
    buffering_ms        UInt32,
    rebuffer_count      UInt16,
    watch_seconds       UInt32,
    is_drop_off         UInt8,
    subscription_tier   LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (title_id, territory, event_time);

-- Fact: ad pod insertion outcomes. Backbone of Ghost Ads.
CREATE TABLE IF NOT EXISTS backlot.ad_events
(
    event_time            DateTime64(3),
    session_id            String,
    title_id              String,
    territory             LowCardinality(String),
    ad_pod_id             String,
    ad_slot_seq            UInt8,
    requested              UInt8,
    filled                 UInt8,
    fill_reason            LowCardinality(String), -- ok, timeout, no_fill, creative_error, ssai_stitch_fail
    expected_revenue_usd    Float64,
    actual_revenue_usd      Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (title_id, territory, event_time);

-- Fact: structured rights obligations, extracted by the Contract Intelligence
-- agent from raw contract text. Backbone of Chain of Title.
CREATE TABLE IF NOT EXISTS backlot.rights_contracts
(
    contract_id                    String,
    rights_holder                  String,
    role                           LowCardinality(String), -- actor, writer, composer, director, musician
    title_id                       String,
    territory                      LowCardinality(String),
    rate_type                      LowCardinality(String), -- per_stream, per_minute, flat_window, revenue_share_pct
    rate_value                     Float64,
    window_start                   Date,
    window_end                     Date,
    escalation_threshold_units    Nullable(UInt64),
    escalation_rate_value           Nullable(Float64),
    source_clause                   String -- raw contract text snippet, kept for traceability in dispute briefs
)
ENGINE = MergeTree
ORDER BY (title_id, rights_holder, contract_id);

-- Fact: payments actually made against contracts (synthetic ledger, some
-- deliberately wrong to give the Reconciliation Agent something to find).
CREATE TABLE IF NOT EXISTS backlot.royalty_ledger
(
    payment_id       String,
    contract_id      String,
    rights_holder    String,
    title_id         String,
    territory        LowCardinality(String),
    period_start     Date,
    period_end       Date,
    amount_paid_usd  Float64,
    paid_at          DateTime
)
ENGINE = MergeTree
ORDER BY (contract_id, period_start);

-- Fact: session/device fingerprint features. Backbone of Stream Fraud Sentinel.
CREATE TABLE IF NOT EXISTS backlot.fraud_signals
(
    event_time                  DateTime64(3),
    session_id                  String,
    user_id                     String,
    device_fingerprint          String,
    ip_geo_territory            LowCardinality(String),
    account_home_territory      LowCardinality(String),
    concurrent_sessions_5min    UInt16,
    impossible_travel_flag      UInt8,
    device_count_24h            UInt16,
    is_bot_ua                   UInt8
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (user_id, event_time);

-- Fact: review/social sentiment signals. Feeds Churn Early-Warning and
-- Performance War Room.
CREATE TABLE IF NOT EXISTS backlot.sentiment_events
(
    event_time      DateTime,
    title_id        String,
    territory       LowCardinality(String),
    source          LowCardinality(String), -- review, social, app_rating
    sentiment_score Float32,                -- -1.0 .. 1.0
    text_snippet    String
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (title_id, event_time);
