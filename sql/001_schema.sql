-- sql/001_schema.sql  (safe to re-run)

-- Extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 1) Raw landing (debug/forensics)
CREATE TABLE IF NOT EXISTS habits_raw (
  row_hash bytea PRIMARY KEY,
  ingested_at timestamptz NOT NULL DEFAULT now(),
  payload jsonb NOT NULL
);

-- 2) Tidy events for Grafana
CREATE TABLE IF NOT EXISTS habit_events (
  event_id bigserial PRIMARY KEY,
  ts timestamptz NOT NULL,             -- normalized UTC instant for the "Report Date"
  user_email text NOT NULL,            -- from "Email Address"
  habit text NOT NULL,                 -- normalized id e.g. 'sleep_hours'
  value double precision,              -- numeric or 0/1 for bool
  notes text,                          -- optional
  source text NOT NULL DEFAULT 'sheets',
  UNIQUE(user_email, habit, ts)
);

-- Timescale-ify + indexes
SELECT create_hypertable('habit_events','ts', if_not_exists => true);
CREATE INDEX IF NOT EXISTS habit_events_ts_idx ON habit_events (ts DESC);
CREATE INDEX IF NOT EXISTS habit_events_user_habit_ts_idx ON habit_events (user_email, habit, ts DESC);

-- Example continuous aggregate: daily summaries per user+habit
CREATE MATERIALIZED VIEW IF NOT EXISTS habit_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', ts) AS day,
       user_email,
       habit,
       count(*) FILTER (WHERE value >= 1)           AS count_done,   -- for bool-y habits
       avg(value)                                   AS avg_value,    -- for 1-10 scales / minutes / liters
       sum(value) FILTER (WHERE habit='meditation_minutes') AS sum_meditation
FROM habit_events
GROUP BY 1,2,3;

-- Refresh policy (15 min cadence)
SELECT add_continuous_aggregate_policy('habit_daily',
  start_offset => INTERVAL '60 days',
  end_offset   => INTERVAL '15 minutes',
  schedule_interval => INTERVAL '15 minutes');
