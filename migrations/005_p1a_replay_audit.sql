-- Offline outcomes and audit only. No execution path or production mode.
CREATE SCHEMA p1a_replay;
CREATE TABLE p1a_replay.audit (
  chain_id TEXT NOT NULL, sequence BIGINT NOT NULL CHECK(sequence>0),
  previous_hash sha256_digest NOT NULL, event_hash sha256_digest NOT NULL,
  event_type TEXT NOT NULL, event_time TIMESTAMPTZ NOT NULL, event_json JSONB NOT NULL,
  PRIMARY KEY(chain_id,sequence), UNIQUE(chain_id,event_hash)
);
CREATE TABLE p1a_replay.results (
  economic_result_hash sha256_digest PRIMARY KEY, input_hash sha256_digest NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('DEV','PAPER')),
  fixture_scope TEXT NOT NULL CHECK(fixture_scope='SYNTHETIC_EXPERIMENTAL'),
  code_version TEXT NOT NULL CHECK(code_version ~ '^[a-f0-9]{40}$'),
  result_json JSONB NOT NULL, metrics_json JSONB NOT NULL,
  mae_resolution TEXT NOT NULL CHECK(mae_resolution='DAILY_APPROXIMATION'),
  mfe_resolution TEXT NOT NULL CHECK(mfe_resolution='DAILY_APPROXIMATION')
);
CREATE FUNCTION p1a_replay.append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'P1A_REPLAY_APPEND_ONLY'; END; $$;
CREATE TRIGGER immutable_replay_audit BEFORE UPDATE OR DELETE ON p1a_replay.audit FOR EACH ROW EXECUTE FUNCTION p1a_replay.append_only();
CREATE TRIGGER immutable_replay_results BEFORE UPDATE OR DELETE ON p1a_replay.results FOR EACH ROW EXECUTE FUNCTION p1a_replay.append_only();
CREATE TRIGGER immutable_replay_audit_truncate BEFORE TRUNCATE ON p1a_replay.audit FOR EACH STATEMENT EXECUTE FUNCTION p1a_replay.append_only();
CREATE TRIGGER immutable_replay_results_truncate BEFORE TRUNCATE ON p1a_replay.results FOR EACH STATEMENT EXECUTE FUNCTION p1a_replay.append_only();
