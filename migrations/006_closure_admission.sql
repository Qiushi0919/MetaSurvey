-- Approved fixture-only policy/receipt/revocation/export-import audit. No business execution state.
CREATE SCHEMA p1a_closure;
CREATE TABLE p1a_closure.policies (
 content_hash sha256_digest PRIMARY KEY,
 policy_json JSONB NOT NULL,
 valid_from TIMESTAMPTZ NOT NULL, valid_until TIMESTAMPTZ NOT NULL,
 CHECK(valid_until>valid_from),
 CHECK(policy_json->>'contract_name'='SourceAdmissionPolicy'),
 CHECK(policy_json->>'fixture_scope'='SYNTHETIC_TEST_ONLY'),
 CHECK(policy_json->>'purpose'='FIXTURE_MANUAL_EXPORT'),
 CHECK(policy_json->>'allow_real_data'='false'),
 CHECK(policy_json->>'production_enabled'='false')
);
CREATE TABLE p1a_closure.receipts (
 content_hash sha256_digest PRIMARY KEY,
 policy_hash sha256_digest NOT NULL REFERENCES p1a_closure.policies(content_hash),
 receipt_json JSONB NOT NULL, issued_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
 CHECK(expires_at>issued_at),
 CHECK(receipt_json->>'contract_name'='AdmissionReceipt'),
 CHECK(receipt_json->>'fixture_scope'='SYNTHETIC_TEST_ONLY'),
 CHECK(receipt_json->>'purpose'='FIXTURE_MANUAL_EXPORT'),
 CHECK(receipt_json->>'production_enabled'='false')
);
CREATE TABLE p1a_closure.revocations (
 target_kind TEXT NOT NULL CHECK(target_kind IN ('POLICY','RECEIPT')),
 target_hash sha256_digest NOT NULL, revoked_at TIMESTAMPTZ NOT NULL,
 reason_code TEXT NOT NULL CHECK(reason_code LIKE 'CLOSURE_%'),
 PRIMARY KEY(target_kind,target_hash)
);
CREATE TABLE p1a_closure.audit (
 event_hash sha256_digest PRIMARY KEY,
 chain_id TEXT NOT NULL, sequence BIGINT NOT NULL CHECK(sequence>0),
 previous_hash sha256_digest NOT NULL,
 event_type TEXT NOT NULL CHECK(event_type IN ('EXPORT_ACCEPTED','EXPORT_REJECTED','IMPORT_COST_ESTIMATED','IMPORT_ACCEPTED','IMPORT_REJECTED','CONSUMER_ACCEPTED','CONSUMER_REJECTED')),
 event_time TIMESTAMPTZ NOT NULL, event_json JSONB NOT NULL,
 UNIQUE(chain_id,sequence)
);
CREATE FUNCTION p1a_closure.append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'CLOSURE_APPEND_ONLY'; END; $$;
CREATE TRIGGER closure_policy_no_mutation BEFORE UPDATE OR DELETE ON p1a_closure.policies FOR EACH ROW EXECUTE FUNCTION p1a_closure.append_only();
CREATE TRIGGER closure_receipt_no_mutation BEFORE UPDATE OR DELETE ON p1a_closure.receipts FOR EACH ROW EXECUTE FUNCTION p1a_closure.append_only();
CREATE TRIGGER closure_revocation_no_mutation BEFORE UPDATE OR DELETE ON p1a_closure.revocations FOR EACH ROW EXECUTE FUNCTION p1a_closure.append_only();
CREATE TRIGGER closure_audit_no_mutation BEFORE UPDATE OR DELETE ON p1a_closure.audit FOR EACH ROW EXECUTE FUNCTION p1a_closure.append_only();
CREATE TRIGGER closure_policy_no_truncate BEFORE TRUNCATE ON p1a_closure.policies FOR EACH STATEMENT EXECUTE FUNCTION p1a_closure.append_only();
CREATE TRIGGER closure_receipt_no_truncate BEFORE TRUNCATE ON p1a_closure.receipts FOR EACH STATEMENT EXECUTE FUNCTION p1a_closure.append_only();
CREATE TRIGGER closure_revocation_no_truncate BEFORE TRUNCATE ON p1a_closure.revocations FOR EACH STATEMENT EXECUTE FUNCTION p1a_closure.append_only();
CREATE TRIGGER closure_audit_no_truncate BEFORE TRUNCATE ON p1a_closure.audit FOR EACH STATEMENT EXECUTE FUNCTION p1a_closure.append_only();
