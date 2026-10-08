-- P1-A append-only evidence store. Unknown clocks never enter P0 normalized contracts.
CREATE TABLE p1a_data_raw (
  raw_sha256 sha256_digest PRIMARY KEY,
  raw_bytes BYTEA NOT NULL,
  byte_length INTEGER NOT NULL CHECK(byte_length BETWEEN 1 AND 1048576),
  CHECK(octet_length(raw_bytes)=byte_length)
);
CREATE TABLE p1a_data_objects (
  object_id TEXT NOT NULL,
  object_version positive_version NOT NULL,
  content_hash sha256_digest NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('SOURCE_OBSERVATION','SECURITY','CALENDAR','STATUS','BAR_1D','CORPORATE_ACTION','ADJUSTMENT','FINANCIAL','SNAPSHOT')),
  source_id TEXT NOT NULL,
  source_version TEXT NOT NULL,
  source_hash sha256_digest NOT NULL,
  raw_sha256 sha256_digest NOT NULL REFERENCES p1a_data_raw(raw_sha256),
  payload_sha256 sha256_digest NOT NULL,
  event_time TIMESTAMPTZ,
  published_at TEXT,
  available_at TIMESTAMPTZ,
  retrieved_at TIMESTAMPTZ NOT NULL,
  publication_precision TEXT NOT NULL CHECK(publication_precision IN ('SECOND','DATE_ONLY','UNKNOWN','NOT_APPLICABLE')),
  clock_basis TEXT NOT NULL CHECK(clock_basis IN ('UNKNOWN','SOURCE_FIELD','RETRIEVAL_OBSERVATION','DATE_ONLY_NEXT_SESSION','SYNTHETIC')),
  scope TEXT NOT NULL CHECK(scope IN ('SYNTHETIC','PUBLIC_REFERENCE')),
  security_id TEXT,
  canonical_symbol TEXT,
  original_symbol TEXT,
  data_quality_status TEXT NOT NULL CHECK(data_quality_status IN ('PASS','QUARANTINED','UNKNOWN')),
  tradeability TEXT NOT NULL CHECK(tradeability IN ('OFFLINE_ELIGIBLE','NON_TRADEABLE')),
  reason_codes JSONB NOT NULL,
  lineage_refs JSONB NOT NULL,
  trace_id TEXT NOT NULL,
  payload JSONB NOT NULL,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(object_id,object_version,content_hash),
  CHECK(available_at IS NULL OR available_at<=retrieved_at),
  CHECK((clock_basis='UNKNOWN' AND available_at IS NULL) OR clock_basis<>'UNKNOWN'),
  CHECK(data_quality_status='PASS' OR tradeability='NON_TRADEABLE')
);
CREATE INDEX p1a_data_kind_security ON p1a_data_objects(kind,security_id,available_at);
CREATE TABLE p1a_data_staging (
  observation_id TEXT NOT NULL,
  observation_version positive_version NOT NULL,
  observation_hash sha256_digest NOT NULL,
  parser_version TEXT NOT NULL,
  normalized_ref JSONB,
  dq_status TEXT NOT NULL CHECK(dq_status IN ('PASS','QUARANTINED','UNKNOWN')),
  reason_codes JSONB NOT NULL,
  PRIMARY KEY(observation_id,observation_version,parser_version),
  FOREIGN KEY(observation_id,observation_version,observation_hash) REFERENCES p1a_data_objects(object_id,object_version,content_hash)
);
CREATE TABLE p1a_data_audit (
  sequence BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_hash sha256_digest NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  object_ref JSONB,
  source_id TEXT NOT NULL,
  source_hash sha256_digest NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  security_id TEXT,
  version TEXT NOT NULL,
  trace_id TEXT NOT NULL,
  reason_codes JSONB NOT NULL,
  event JSONB NOT NULL
);
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['p1a_data_raw','p1a_data_objects','p1a_data_staging','p1a_data_audit'] LOOP
    EXECUTE format('CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()',t);
    EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION reject_history_mutation()',t);
  END LOOP;
END $$;
