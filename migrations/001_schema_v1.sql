-- P0 PostgreSQL V1 DRAFT. Structural constraints do not grant execution permission.
-- Connection/server role provisioning and external PostgreSQL deployment are later gates.
SET TIME ZONE 'UTC';

CREATE DOMAIN sha256_digest AS TEXT
  CHECK (VALUE ~ '^sha256:[a-f0-9]{64}$');
CREATE DOMAIN positive_version AS INTEGER CHECK (VALUE > 0);
CREATE DOMAIN strategy_namespace AS TEXT
  CHECK (VALUE IN ('CORE_40','EVENT_3','RESEARCH_6_18M'));
CREATE DOMAIN trading_namespace AS TEXT CHECK (VALUE IN ('CORE_40','EVENT_3'));
CREATE DOMAIN execution_mode AS TEXT CHECK (VALUE IN ('DEV','PAPER','PROD'));
-- No typmod coercion: NUMERIC(38,0) would round bad fractional cents before CHECK.
CREATE DOMAIN money_cents AS NUMERIC
  CHECK (VALUE = trunc(VALUE) AND abs(VALUE) < power(10::NUMERIC,38));
CREATE DOMAIN price_yuan AS NUMERIC
  CHECK (VALUE >= 0 AND scale(VALUE) <= 6 AND VALUE < power(10::NUMERIC,14));
CREATE DOMAIN decimal_rate AS NUMERIC
  CHECK (scale(VALUE) <= 10 AND abs(VALUE) < power(10::NUMERIC,10));

CREATE TABLE data_sources (
  source_id TEXT PRIMARY KEY,
  object_version positive_version NOT NULL,
  contract_version TEXT NOT NULL CHECK (contract_version='1.0.0'),
  provider TEXT NOT NULL,
  source_class TEXT NOT NULL CHECK (source_class IN ('OFFICIAL','LICENSED','BROKER','DERIVED','SYNTHETIC','LEGACY')),
  license_type TEXT NOT NULL,
  allowed_use JSONB NOT NULL CHECK (jsonb_typeof(allowed_use)='array'),
  retention_policy TEXT NOT NULL,
  redistribution_allowed BOOLEAN NOT NULL,
  rate_limit JSONB NOT NULL,
  terms_version TEXT NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  published_at TIMESTAMPTZ,
  published_at_precision TEXT NOT NULL CHECK (published_at_precision IN ('MICROSECOND','SECOND','MINUTE','DAY','NOT_APPLICABLE')),
  published_at_not_applicable BOOLEAN NOT NULL,
  available_at TIMESTAMPTZ NOT NULL,
  retrieved_at TIMESTAMPTZ NOT NULL,
  business_timezone TEXT NOT NULL CHECK (business_timezone='Asia/Shanghai'),
  source_version TEXT NOT NULL,
  source_hash sha256_digest NOT NULL,
  payload_hash sha256_digest NOT NULL,
  trace_id TEXT NOT NULL,
  reason_codes JSONB NOT NULL CHECK (jsonb_typeof(reason_codes)='array'),
  CHECK ((published_at_not_applicable AND published_at IS NULL AND published_at_precision='NOT_APPLICABLE')
    OR (NOT published_at_not_applicable AND published_at IS NOT NULL AND published_at_precision<>'NOT_APPLICABLE')),
  CHECK (published_at IS NULL OR published_at <= available_at),
  CHECK (available_at <= retrieved_at)
);

-- Migration-local helper expands common columns into ordinary flat PostgreSQL tables.
-- It is dropped below; no runtime dynamic-schema API remains.
CREATE FUNCTION p0_create_versioned_table(table_name TEXT, business_columns TEXT) RETURNS VOID
LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE format('CREATE TABLE %I (%s,
    object_version positive_version NOT NULL,
    contract_version TEXT NOT NULL CHECK (contract_version=''1.0.0''),
    business_timezone TEXT NOT NULL CHECK (business_timezone=''Asia/Shanghai''),
    event_time TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    published_at_precision TEXT NOT NULL CHECK (published_at_precision IN (''MICROSECOND'',''SECOND'',''MINUTE'',''DAY'',''NOT_APPLICABLE'')),
    published_at_not_applicable BOOLEAN NOT NULL,
    available_at TIMESTAMPTZ NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    source_id TEXT NOT NULL REFERENCES data_sources(source_id),
    source_version TEXT NOT NULL CHECK (length(source_version)>0),
    source_hash sha256_digest NOT NULL,
    payload_hash sha256_digest NOT NULL,
    trace_id TEXT NOT NULL CHECK (length(trace_id)>0),
    reason_codes JSONB NOT NULL CHECK (jsonb_typeof(reason_codes)=''array''),
    CHECK ((published_at_not_applicable AND published_at IS NULL AND published_at_precision=''NOT_APPLICABLE'')
      OR (NOT published_at_not_applicable AND published_at IS NOT NULL AND published_at_precision<>''NOT_APPLICABLE'')),
    CHECK (published_at IS NULL OR published_at<=available_at),
    CHECK (available_at<=retrieved_at)
  )',table_name,business_columns);
END $$;

SELECT p0_create_versioned_table('securities',$columns$
  security_id TEXT PRIMARY KEY, symbol TEXT NOT NULL,
  exchange TEXT NOT NULL CHECK (exchange IN ('SSE','SZSE','BSE')),
  UNIQUE(exchange,symbol)
$columns$);

SELECT p0_create_versioned_table('security_master',$columns$
  security_id TEXT NOT NULL REFERENCES securities(security_id),
  effective_from TIMESTAMPTZ NOT NULL, effective_to TIMESTAMPTZ,
  name TEXT NOT NULL, board TEXT NOT NULL,
  lot_size BIGINT NOT NULL CHECK (lot_size>0 AND lot_size<=9007199254740991),
  status TEXT NOT NULL CHECK (status IN ('ACTIVE','SUSPENDED','DELISTED','UNKNOWN')),
  st_flag BOOLEAN NOT NULL, list_date DATE NOT NULL, delist_date DATE,
  trading_rules JSONB NOT NULL,
  PRIMARY KEY(security_id,object_version),
  CHECK (effective_to IS NULL OR effective_to>effective_from),
  CHECK (delist_date IS NULL OR delist_date>=list_date)
$columns$);

SELECT p0_create_versioned_table('corp_actions',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL, security_version positive_version NOT NULL,
  action_type TEXT NOT NULL CHECK (action_type IN ('DIVIDEND','BONUS','SPLIT','RIGHTS','OTHER')),
  ex_date DATE NOT NULL, record_date DATE, terms JSONB NOT NULL,
  PRIMARY KEY(object_id,object_version),
  FOREIGN KEY(security_id,security_version) REFERENCES security_master(security_id,object_version)
$columns$);

SELECT p0_create_versioned_table('adjustment_versions',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL REFERENCES securities(security_id),
  method TEXT NOT NULL, action_refs JSONB NOT NULL CHECK(jsonb_typeof(action_refs)='array'),
  decision_cutoff TIMESTAMPTZ NOT NULL, factors_hash sha256_digest NOT NULL,
  visibility_basis TEXT NOT NULL CHECK(visibility_basis IN ('OBSERVED_AS_OF','PUBLIC_AS_OF')),
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,security_id)
$columns$);

SELECT p0_create_versioned_table('adjustment_actions',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL,
  adjustment_id TEXT NOT NULL, adjustment_version positive_version NOT NULL,
  action_id TEXT NOT NULL, action_version positive_version NOT NULL,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(adjustment_id,adjustment_version,action_id,action_version),
  FOREIGN KEY(adjustment_id,adjustment_version,security_id) REFERENCES adjustment_versions(object_id,object_version,security_id),
  FOREIGN KEY(action_id,action_version) REFERENCES corp_actions(object_id,object_version)
$columns$);

SELECT p0_create_versioned_table('bars_1d',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL, security_version positive_version NOT NULL,
  trade_date DATE NOT NULL, price_basis TEXT NOT NULL CHECK (price_basis IN ('RAW','ADJUSTED')),
  adjustment_id TEXT, adjustment_version positive_version,
  open price_yuan NOT NULL, high price_yuan NOT NULL, low price_yuan NOT NULL,
  close price_yuan NOT NULL, preclose price_yuan NOT NULL,
  volume BIGINT NOT NULL CHECK(volume>=0 AND volume<=9007199254740991), amount_cents money_cents NOT NULL CHECK(amount_cents>=0),
  PRIMARY KEY(object_id,object_version),
  UNIQUE(security_id,trade_date,price_basis,adjustment_id,adjustment_version,source_id,source_version,object_version),
  FOREIGN KEY(security_id,security_version) REFERENCES security_master(security_id,object_version),
  FOREIGN KEY(adjustment_id,adjustment_version,security_id) REFERENCES adjustment_versions(object_id,object_version,security_id),
  CHECK ((price_basis='RAW' AND adjustment_id IS NULL AND adjustment_version IS NULL)
    OR (price_basis='ADJUSTED' AND adjustment_id IS NOT NULL AND adjustment_version IS NOT NULL)),
  CHECK(event_time<=available_at),
  CHECK (high>=greatest(open,close,low) AND low<=least(open,close,high))
$columns$);
-- NULL raw adjustment fields must not weaken the natural identity uniqueness.
CREATE UNIQUE INDEX bars_1d_raw_identity ON bars_1d
  (security_id,trade_date,source_id,source_version,object_version) WHERE price_basis='RAW';

SELECT p0_create_versioned_table('bars_1m',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL, security_version positive_version NOT NULL,
  bar_start TIMESTAMPTZ NOT NULL, session TEXT NOT NULL,
  price_basis TEXT NOT NULL CHECK (price_basis IN ('RAW','ADJUSTED')),
  adjustment_id TEXT, adjustment_version positive_version,
  open price_yuan NOT NULL, high price_yuan NOT NULL, low price_yuan NOT NULL, close price_yuan NOT NULL,
  volume BIGINT NOT NULL CHECK(volume>=0 AND volume<=9007199254740991), amount_cents money_cents NOT NULL CHECK(amount_cents>=0),
  PRIMARY KEY(object_id,object_version),
  UNIQUE(security_id,bar_start,price_basis,adjustment_id,adjustment_version,source_id,source_version,object_version),
  FOREIGN KEY(security_id,security_version) REFERENCES security_master(security_id,object_version),
  FOREIGN KEY(adjustment_id,adjustment_version,security_id) REFERENCES adjustment_versions(object_id,object_version,security_id),
  CHECK ((price_basis='RAW' AND adjustment_id IS NULL AND adjustment_version IS NULL)
    OR (price_basis='ADJUSTED' AND adjustment_id IS NOT NULL AND adjustment_version IS NOT NULL)),
  CHECK(bar_start<=event_time AND event_time<=available_at),
  CHECK (high>=greatest(open,close,low) AND low<=least(open,close,high))
$columns$);
CREATE UNIQUE INDEX bars_1m_raw_identity ON bars_1m
  (security_id,bar_start,source_id,source_version,object_version) WHERE price_basis='RAW';

SELECT p0_create_versioned_table('orderbook_l2',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL REFERENCES securities(security_id),
  sequence_number BIGINT NOT NULL CHECK(sequence_number>=0), book JSONB NOT NULL,
  PRIMARY KEY(object_id,object_version), UNIQUE(security_id,event_time,sequence_number,source_id,object_version), CHECK(event_time<=available_at)
$columns$);

SELECT p0_create_versioned_table('announcements',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL REFERENCES securities(security_id),
  title TEXT NOT NULL, raw_uri TEXT NOT NULL, raw_hash sha256_digest NOT NULL,
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,security_id), CHECK(NOT published_at_not_applicable)
$columns$);

SELECT p0_create_versioned_table('financials',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL REFERENCES securities(security_id),
  period DATE NOT NULL, statement_type TEXT NOT NULL,
  announcement_id TEXT NOT NULL, announcement_version positive_version NOT NULL,
  revision_kind TEXT NOT NULL CHECK(revision_kind IN ('ORIGINAL','RESTATEMENT','SOURCE_CORRECTION')),
  currency TEXT NOT NULL CHECK(currency='CNY'), unit TEXT NOT NULL CHECK(unit='CNY_CENTS'),
  values_cents JSONB NOT NULL CHECK(jsonb_typeof(values_cents)='object'),
  PRIMARY KEY(object_id,object_version),
  UNIQUE(security_id,period,statement_type,source_id,object_version),
  FOREIGN KEY(announcement_id,announcement_version,security_id) REFERENCES announcements(object_id,object_version,security_id),
  CHECK(NOT published_at_not_applicable)
$columns$);

SELECT p0_create_versioned_table('news_events',$columns$
  object_id TEXT NOT NULL, entity TEXT NOT NULL, event_type TEXT NOT NULL,
  summary TEXT NOT NULL, sentiment TEXT, confidence decimal_rate,
  raw_uri TEXT NOT NULL, raw_hash sha256_digest NOT NULL,
  PRIMARY KEY(object_id,object_version), CHECK(NOT published_at_not_applicable),
  CHECK(confidence IS NULL OR confidence BETWEEN 0 AND 1)
$columns$);

SELECT p0_create_versioned_table('sector_membership',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL REFERENCES securities(security_id),
  sector_id TEXT NOT NULL, classification_version TEXT NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL, effective_to TIMESTAMPTZ,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(security_id,sector_id,effective_from,source_id,object_version),
  CHECK(effective_to IS NULL OR effective_to>effective_from)
$columns$);

SELECT p0_create_versioned_table('config_versions',$columns$
  object_id TEXT NOT NULL, strategy_id strategy_namespace,
  config_type TEXT NOT NULL CHECK(config_type IN ('ACCOUNT','COST','RISK','STRATEGY','SCORING','DATA_SOURCE','ALERT','EXECUTION')),
  configuration JSONB NOT NULL CHECK(jsonb_typeof(configuration)='object'),
  config_hash sha256_digest NOT NULL,
  parameter_status TEXT NOT NULL CHECK(parameter_status IN ('UNSET_REQUIRED','SYNTHETIC_FIXTURE','USER_CONFIRMED')),
  published_by TEXT NOT NULL,
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,config_hash)
$columns$);

SELECT p0_create_versioned_table('accounts',$columns$
  account_id TEXT PRIMARY KEY, mode execution_mode NOT NULL,
  identity_status TEXT NOT NULL CHECK(identity_status IN ('UNSET_REQUIRED','SYNTHETIC_FIXTURE','USER_CONFIRMED')),
  broker_ref TEXT NOT NULL, currency TEXT NOT NULL CHECK(currency='CNY'),
  production_authorized BOOLEAN NOT NULL CHECK(NOT production_authorized),
  UNIQUE(account_id,mode)
$columns$);

SELECT p0_create_versioned_table('account_profiles',$columns$
  object_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL,
  profile JSONB NOT NULL CHECK(jsonb_typeof(profile)='object'),
  parameter_status TEXT NOT NULL CHECK(parameter_status IN ('UNSET_REQUIRED','SYNTHETIC_FIXTURE','USER_CONFIRMED')),
  config_id TEXT NOT NULL, config_version positive_version NOT NULL, config_hash sha256_digest NOT NULL,
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,account_id,mode,payload_hash),
  FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode),
  FOREIGN KEY(config_id,config_version,config_hash) REFERENCES config_versions(object_id,object_version,config_hash)
$columns$);

SELECT p0_create_versioned_table('snapshot_manifests',$columns$
  object_id TEXT NOT NULL, decision_cutoff TIMESTAMPTZ NOT NULL,
  frozen_at TIMESTAMPTZ NOT NULL, data_hash sha256_digest NOT NULL,
  content_hash sha256_digest NOT NULL CHECK(content_hash=payload_hash),
  visibility_basis TEXT NOT NULL CHECK(visibility_basis IN ('OBSERVED_AS_OF','PUBLIC_AS_OF')),
  fixture_kind TEXT NOT NULL CHECK(fixture_kind IN ('SYNTHETIC','LEGACY','OBSERVED')),
  manifest JSONB NOT NULL CHECK(jsonb_typeof(manifest)='object'),
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,data_hash), UNIQUE(object_id,object_version,content_hash),
  CHECK(frozen_at>=decision_cutoff)
$columns$);

SELECT p0_create_versioned_table('snapshot_entries',$columns$
  object_id TEXT NOT NULL, snapshot_id TEXT NOT NULL, snapshot_version positive_version NOT NULL,
  dataset TEXT NOT NULL, dataset_object_id TEXT NOT NULL, dataset_object_version positive_version NOT NULL,
  dataset_hash sha256_digest NOT NULL,
  entry_role TEXT NOT NULL CHECK(entry_role IN ('DECISION_INPUT','FUTURE_REVEAL')),
  reveal_after TIMESTAMPTZ,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(snapshot_id,snapshot_version,dataset,dataset_object_id,dataset_object_version,entry_role),
  FOREIGN KEY(snapshot_id,snapshot_version) REFERENCES snapshot_manifests(object_id,object_version),
  CHECK((entry_role='DECISION_INPUT' AND reveal_after IS NULL) OR (entry_role='FUTURE_REVEAL' AND reveal_after IS NOT NULL))
$columns$);

CREATE FUNCTION check_snapshot_visibility() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE cutoff TIMESTAMPTZ; frozen TIMESTAMPTZ; basis TEXT; source_row JSONB; id_column TEXT;
BEGIN
  SELECT decision_cutoff,frozen_at,visibility_basis INTO cutoff,frozen,basis
    FROM snapshot_manifests WHERE object_id=NEW.snapshot_id AND object_version=NEW.snapshot_version;
  -- Typed references must resolve to saved source versions, never self-declared clocks.
  IF NEW.dataset IN ('bars_1d','bars_1m','corp_actions','adjustment_versions','announcements','financials',
    'news_events','sector_membership','features_eod','research_evidence','orderbook_l2','account_snapshots') THEN
    id_column := 'object_id';
  ELSIF NEW.dataset IN ('security_master','securities') THEN id_column := 'security_id';
  ELSE RAISE EXCEPTION 'SNAPSHOT_DATASET_UNSUPPORTED'; END IF;
  EXECUTE format('SELECT to_jsonb(s) FROM %I s WHERE %I=$1 AND object_version=$2',NEW.dataset,id_column)
    INTO source_row USING NEW.dataset_object_id,NEW.dataset_object_version;
  IF source_row IS NULL THEN RAISE EXCEPTION 'SNAPSHOT_MEMBER_NOT_FOUND'; END IF;
  IF NEW.dataset_hash::TEXT IS DISTINCT FROM source_row->>'payload_hash'
    OR NEW.source_id IS DISTINCT FROM source_row->>'source_id'
    OR NEW.source_version IS DISTINCT FROM source_row->>'source_version'
    OR NEW.source_hash::TEXT IS DISTINCT FROM source_row->>'source_hash'
    OR NEW.event_time IS DISTINCT FROM (source_row->>'event_time')::TIMESTAMPTZ
    OR NEW.published_at IS DISTINCT FROM (source_row->>'published_at')::TIMESTAMPTZ
    OR NEW.available_at IS DISTINCT FROM (source_row->>'available_at')::TIMESTAMPTZ
    OR NEW.retrieved_at IS DISTINCT FROM (source_row->>'retrieved_at')::TIMESTAMPTZ
    OR NEW.published_at_precision IS DISTINCT FROM source_row->>'published_at_precision'
    OR NEW.published_at_not_applicable IS DISTINCT FROM (source_row->>'published_at_not_applicable')::BOOLEAN THEN
    RAISE EXCEPTION 'SNAPSHOT_MEMBER_PROVENANCE_MISMATCH';
  END IF;
  IF NEW.entry_role='DECISION_INPUT' AND (NEW.available_at>cutoff OR
      (basis='OBSERVED_AS_OF' AND NEW.retrieved_at>cutoff)) THEN
    RAISE EXCEPTION 'PIT_FUTURE_DATA_BLOCKED';
  END IF;
  IF NEW.entry_role='FUTURE_REVEAL' AND NEW.reveal_after<=frozen THEN
    RAISE EXCEPTION 'FREEZE_BEFORE_REVEAL_REQUIRED';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER snapshot_visibility BEFORE INSERT ON snapshot_entries FOR EACH ROW EXECUTE FUNCTION check_snapshot_visibility();

SELECT p0_create_versioned_table('features_eod',$columns$
  object_id TEXT NOT NULL, security_id TEXT NOT NULL REFERENCES securities(security_id),
  trade_date DATE NOT NULL, feature_version TEXT NOT NULL, strategy_id strategy_namespace NOT NULL,
  snapshot_id TEXT NOT NULL, snapshot_version positive_version NOT NULL, snapshot_hash sha256_digest NOT NULL,
  values_decimal JSONB NOT NULL CHECK(jsonb_typeof(values_decimal)='object'),
  PRIMARY KEY(object_id,object_version),
  UNIQUE(security_id,trade_date,feature_version,strategy_id,snapshot_id,snapshot_version,object_version),
  FOREIGN KEY(snapshot_id,snapshot_version,snapshot_hash) REFERENCES snapshot_manifests(object_id,object_version,content_hash)
$columns$);

SELECT p0_create_versioned_table('research_evidence',$columns$
  object_id TEXT NOT NULL, strategy_id strategy_namespace NOT NULL,
  summary TEXT NOT NULL, raw_uri TEXT NOT NULL, raw_hash sha256_digest NOT NULL,
  trust_level TEXT NOT NULL, decision_cutoff TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,strategy_id,payload_hash),
  CHECK(available_at<=decision_cutoff)
$columns$);

SELECT p0_create_versioned_table('research_cards',$columns$
  object_id TEXT NOT NULL, strategy_id strategy_namespace NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL,
  security_id TEXT NOT NULL REFERENCES securities(security_id),
  grade TEXT NOT NULL CHECK(grade IN ('S','A','B','C','X','UNSET_REQUIRED')),
  action TEXT NOT NULL CHECK(action IN ('APPROVE','WAIT','REJECT','OBSERVE')),
  decision_cutoff TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
  snapshot_id TEXT NOT NULL, snapshot_version positive_version NOT NULL, snapshot_hash sha256_digest NOT NULL,
  rule_version TEXT NOT NULL, layers JSONB NOT NULL CHECK(jsonb_typeof(layers)='object'),
  invalidation_rules JSONB NOT NULL CHECK(jsonb_typeof(invalidation_rules)='array'),
  probability_calibrated BOOLEAN NOT NULL,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(object_id,object_version,payload_hash,strategy_id,security_id,account_id,mode),
  FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode),
  FOREIGN KEY(snapshot_id,snapshot_version,snapshot_hash) REFERENCES snapshot_manifests(object_id,object_version,content_hash),
  CHECK(expires_at>available_at)
$columns$);

SELECT p0_create_versioned_table('card_evidence',$columns$
  object_id TEXT NOT NULL, strategy_id strategy_namespace NOT NULL, security_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL,
  card_id TEXT NOT NULL, card_version positive_version NOT NULL, card_hash sha256_digest NOT NULL,
  evidence_id TEXT NOT NULL, evidence_version positive_version NOT NULL, evidence_hash sha256_digest NOT NULL,
  PRIMARY KEY(object_id,object_version),
  FOREIGN KEY(card_id,card_version,card_hash,strategy_id,security_id,account_id,mode) REFERENCES research_cards(object_id,object_version,payload_hash,strategy_id,security_id,account_id,mode),
  FOREIGN KEY(evidence_id,evidence_version,strategy_id,evidence_hash) REFERENCES research_evidence(object_id,object_version,strategy_id,payload_hash)
$columns$);

SELECT p0_create_versioned_table('brain_packets',$columns$
  object_id TEXT NOT NULL, strategy_id strategy_namespace NOT NULL,
  snapshot_id TEXT NOT NULL, snapshot_version positive_version NOT NULL, snapshot_hash sha256_digest NOT NULL,
  decision_cutoff TIMESTAMPTZ NOT NULL,
  brain_mode TEXT NOT NULL CHECK(brain_mode='MANUAL_EXPORT'),
  request_type TEXT NOT NULL CHECK(request_type IN ('INITIAL_RESEARCH','TRIGGER_REVIEW')),
  packet JSONB NOT NULL CHECK(jsonb_typeof(packet)='object'),
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,strategy_id),
  FOREIGN KEY(snapshot_id,snapshot_version,snapshot_hash) REFERENCES snapshot_manifests(object_id,object_version,content_hash)
$columns$);

SELECT p0_create_versioned_table('brain_reviews',$columns$
  object_id TEXT NOT NULL, packet_id TEXT NOT NULL, packet_version positive_version NOT NULL,
  strategy_id strategy_namespace NOT NULL, actor_kind TEXT NOT NULL CHECK(actor_kind IN ('LLM','RESEARCHER')),
  decision TEXT NOT NULL CHECK(decision IN ('APPROVE','WAIT','REJECT')),
  review JSONB NOT NULL CHECK(jsonb_typeof(review)='object'),
  PRIMARY KEY(object_id,object_version),
  FOREIGN KEY(packet_id,packet_version,strategy_id) REFERENCES brain_packets(object_id,object_version,strategy_id)
$columns$);

SELECT p0_create_versioned_table('candidate_eligibility',$columns$
  object_id TEXT NOT NULL, strategy_id trading_namespace NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL,
  security_id TEXT NOT NULL, card_id TEXT NOT NULL, card_version positive_version NOT NULL, card_hash sha256_digest NOT NULL,
  tradeable BOOLEAN NOT NULL, blockers JSONB NOT NULL CHECK(jsonb_typeof(blockers)='array'),
  PRIMARY KEY(object_id,object_version),
  FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode),
  FOREIGN KEY(card_id,card_version,card_hash,strategy_id,security_id,account_id,mode) REFERENCES research_cards(object_id,object_version,payload_hash,strategy_id,security_id,account_id,mode),
  CHECK(NOT tradeable OR jsonb_array_length(blockers)=0)
$columns$);

SELECT p0_create_versioned_table('signal_events',$columns$
  object_id TEXT NOT NULL, strategy_id trading_namespace NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL,
  security_id TEXT NOT NULL, card_id TEXT NOT NULL, card_version positive_version NOT NULL, card_hash sha256_digest NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('WATCHING','ARMED','TRIGGERED','ACKNOWLEDGED','APPROVED','EXECUTION_READY','EXECUTED','WAIT','REJECTED','EXPIRED','INVALIDATED')),
  rule_id TEXT NOT NULL, rule_version TEXT NOT NULL, dedupe_key TEXT NOT NULL,
  triggered_at TIMESTAMPTZ, expires_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(object_id,object_version,payload_hash,mode,account_id,strategy_id,security_id,card_id,card_version,card_hash),
  FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode),
  FOREIGN KEY(card_id,card_version,card_hash,strategy_id,security_id,account_id,mode) REFERENCES research_cards(object_id,object_version,payload_hash,strategy_id,security_id,account_id,mode),
  CHECK(expires_at>available_at), CHECK(triggered_at IS NULL OR (triggered_at<=event_time AND triggered_at<expires_at)),
  CHECK(state NOT IN ('TRIGGERED','ACKNOWLEDGED','APPROVED','EXECUTION_READY','EXECUTED') OR triggered_at IS NOT NULL)
$columns$);

SELECT p0_create_versioned_table('account_snapshots',$columns$
  object_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL,
  cash_cents money_cents NOT NULL, equity_cents money_cents NOT NULL,
  exposure_cents money_cents NOT NULL CHECK(exposure_cents>=0),
  ledger_sequence BIGINT NOT NULL CHECK(ledger_sequence>=0),
  reconciled BOOLEAN NOT NULL,
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,payload_hash,account_id,mode),
  FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode)
$columns$);

SELECT p0_create_versioned_table('cost_estimates',$columns$
  object_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL, strategy_id trading_namespace NOT NULL,
  security_id TEXT NOT NULL REFERENCES securities(security_id),
  side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), quantity BIGINT NOT NULL CHECK(quantity>0 AND quantity<=9007199254740991), price price_yuan NOT NULL CHECK(price>0),
  config_id TEXT NOT NULL, config_version positive_version NOT NULL, config_hash sha256_digest NOT NULL,
  commission_cents money_cents NOT NULL CHECK(commission_cents>=0),
  tax_cents money_cents NOT NULL CHECK(tax_cents>=0), other_fees_cents money_cents NOT NULL CHECK(other_fees_cents>=0),
  total_explicit_cents money_cents NOT NULL CHECK(total_explicit_cents>=0),
  slippage_model JSONB NOT NULL, simulation_assumptions BOOLEAN NOT NULL,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(object_id,object_version,payload_hash,account_id,mode,strategy_id,security_id,side,quantity,price),
  FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode),
  FOREIGN KEY(config_id,config_version,config_hash) REFERENCES config_versions(object_id,object_version,config_hash),
  CHECK(total_explicit_cents=commission_cents+tax_cents+other_fees_cents)
$columns$);

-- Immutable unsigned drafts provide a stable approval target without circular hashes.
SELECT p0_create_versioned_table('order_drafts',$columns$
  object_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL, strategy_id trading_namespace NOT NULL,
  security_id TEXT NOT NULL, signal_id TEXT NOT NULL, signal_version positive_version NOT NULL, signal_hash sha256_digest NOT NULL,
  card_id TEXT NOT NULL, card_version positive_version NOT NULL, card_hash sha256_digest NOT NULL,
  side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), quantity BIGINT NOT NULL CHECK(quantity>0 AND quantity<=9007199254740991), limit_price price_yuan NOT NULL CHECK(limit_price>0),
  cost_id TEXT NOT NULL, cost_version positive_version NOT NULL, cost_hash sha256_digest NOT NULL,
  account_snapshot_id TEXT NOT NULL, account_snapshot_version positive_version NOT NULL, account_snapshot_hash sha256_digest NOT NULL,
  target_fingerprint sha256_digest NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(object_id,object_version,payload_hash,target_fingerprint,account_id,mode,strategy_id),
  FOREIGN KEY(signal_id,signal_version,signal_hash,mode,account_id,strategy_id,security_id,card_id,card_version,card_hash)
    REFERENCES signal_events(object_id,object_version,payload_hash,mode,account_id,strategy_id,security_id,card_id,card_version,card_hash),
  FOREIGN KEY(cost_id,cost_version,cost_hash,account_id,mode,strategy_id,security_id,side,quantity,limit_price)
    REFERENCES cost_estimates(object_id,object_version,payload_hash,account_id,mode,strategy_id,security_id,side,quantity,price),
  FOREIGN KEY(account_snapshot_id,account_snapshot_version,account_snapshot_hash,account_id,mode)
    REFERENCES account_snapshots(object_id,object_version,payload_hash,account_id,mode),
  CHECK(expires_at>available_at)
$columns$);

SELECT p0_create_versioned_table('approvals',$columns$
  object_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL, strategy_id trading_namespace NOT NULL,
  phase TEXT NOT NULL CHECK(phase IN ('DECISION_APPROVAL','FINAL_ORDER_CONFIRMATION')),
  decision TEXT NOT NULL CHECK(decision IN ('USER_APPROVED','USER_WAIT','USER_REJECTED')),
  actor_kind TEXT NOT NULL CHECK(actor_kind='HUMAN_USER'), actor_id TEXT NOT NULL,
  draft_id TEXT NOT NULL, draft_version positive_version NOT NULL, draft_hash sha256_digest NOT NULL,
  target_fingerprint sha256_digest NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
  auth_context_hash sha256_digest NOT NULL,
  PRIMARY KEY(object_id,object_version),
  UNIQUE(object_id,object_version,phase,decision,draft_id,draft_version,draft_hash,target_fingerprint,account_id,mode,strategy_id),
  FOREIGN KEY(draft_id,draft_version,draft_hash,target_fingerprint,account_id,mode,strategy_id)
    REFERENCES order_drafts(object_id,object_version,payload_hash,target_fingerprint,account_id,mode,strategy_id),
  CHECK(length(actor_id)>0), CHECK(expires_at>available_at)
$columns$);

-- Two physical transaction families, each constrained to its own modes.
CREATE FUNCTION p0_create_transaction_family(family TEXT, mode_check TEXT) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE orders_name TEXT := 'orders_'||family; fills_name TEXT := 'fills_'||family;
  positions_name TEXT := 'positions_'||family; ledger_name TEXT := 'ledger_'||family;
BEGIN
  PERFORM p0_create_versioned_table(orders_name,format($cols$
    object_id TEXT NOT NULL, client_order_id TEXT NOT NULL,
    account_id TEXT NOT NULL, mode execution_mode NOT NULL CHECK(%s), strategy_id trading_namespace NOT NULL,
    draft_id TEXT NOT NULL, draft_version positive_version NOT NULL, draft_hash sha256_digest NOT NULL,
    target_fingerprint sha256_digest NOT NULL,
    decision_approval_id TEXT NOT NULL, decision_approval_version positive_version NOT NULL,
    decision_phase TEXT NOT NULL CHECK(decision_phase='DECISION_APPROVAL'), decision_value TEXT NOT NULL CHECK(decision_value='USER_APPROVED'),
    final_approval_id TEXT NOT NULL, final_approval_version positive_version NOT NULL,
    final_phase TEXT NOT NULL CHECK(final_phase='FINAL_ORDER_CONFIRMATION'), final_value TEXT NOT NULL CHECK(final_value='USER_APPROVED'),
    state TEXT NOT NULL CHECK(state IN ('PREPARED','SUBMITTED','PARTIAL','FILLED','CANCELLED','REJECTED','UNKNOWN')),
    PRIMARY KEY(object_id,object_version),
    UNIQUE(object_id,object_version,account_id,mode,strategy_id),
    FOREIGN KEY(draft_id,draft_version,draft_hash,target_fingerprint,account_id,mode,strategy_id)
      REFERENCES order_drafts(object_id,object_version,payload_hash,target_fingerprint,account_id,mode,strategy_id),
    FOREIGN KEY(decision_approval_id,decision_approval_version,decision_phase,decision_value,draft_id,draft_version,draft_hash,target_fingerprint,account_id,mode,strategy_id)
      REFERENCES approvals(object_id,object_version,phase,decision,draft_id,draft_version,draft_hash,target_fingerprint,account_id,mode,strategy_id),
    FOREIGN KEY(final_approval_id,final_approval_version,final_phase,final_value,draft_id,draft_version,draft_hash,target_fingerprint,account_id,mode,strategy_id)
      REFERENCES approvals(object_id,object_version,phase,decision,draft_id,draft_version,draft_hash,target_fingerprint,account_id,mode,strategy_id),
    CHECK(decision_approval_id<>final_approval_id)
  $cols$,mode_check));
  -- Persistent claim: revisions reuse the same client_order_id, a second order cannot.
  EXECUTE format('CREATE TABLE %I (account_id TEXT NOT NULL, mode execution_mode NOT NULL CHECK(%s), client_order_id TEXT NOT NULL,
    order_id TEXT NOT NULL, strategy_id trading_namespace NOT NULL,
    PRIMARY KEY(account_id,mode,client_order_id), UNIQUE(order_id),
    UNIQUE(account_id,mode,client_order_id,order_id,strategy_id),
    FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode))','order_claims_'||family,mode_check);
  EXECUTE format('ALTER TABLE %I ADD FOREIGN KEY(account_id,mode,client_order_id,object_id,strategy_id)
    REFERENCES %I(account_id,mode,client_order_id,order_id,strategy_id)',orders_name,'order_claims_'||family);
  PERFORM p0_create_versioned_table(fills_name,format($cols$
    object_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL CHECK(%s), strategy_id trading_namespace NOT NULL,
    order_id TEXT NOT NULL, order_version positive_version NOT NULL, broker_fill_id TEXT NOT NULL,
    trade_date DATE NOT NULL, quantity BIGINT NOT NULL CHECK(quantity>0 AND quantity<=9007199254740991), price price_yuan NOT NULL CHECK(price>0),
    notional_cents money_cents NOT NULL CHECK(notional_cents>0), fee_cents money_cents NOT NULL CHECK(fee_cents>=0),
    fill_observation TEXT NOT NULL CHECK(fill_observation IN ('SYNTHETIC','DAILY_PROXY_CONDITIONAL','BROKER_OBSERVED')),
    PRIMARY KEY(object_id,object_version), UNIQUE(account_id,mode,broker_fill_id),
    UNIQUE(object_id,object_version,account_id,mode,strategy_id),
    FOREIGN KEY(order_id,order_version,account_id,mode,strategy_id) REFERENCES %I(object_id,object_version,account_id,mode,strategy_id)
  $cols$,mode_check,orders_name));
  PERFORM p0_create_versioned_table(positions_name,format($cols$
    object_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL CHECK(%s), strategy_id trading_namespace NOT NULL,
    security_id TEXT NOT NULL REFERENCES securities(security_id), quantity BIGINT NOT NULL CHECK(quantity>=0 AND quantity<=9007199254740991),
    available_quantity BIGINT NOT NULL CHECK(available_quantity>=0 AND available_quantity<=quantity),
    cost_cents money_cents NOT NULL CHECK(cost_cents>=0), realized_pnl_cents money_cents NOT NULL,
    unrealized_pnl_cents money_cents NOT NULL, lot_allocations JSONB NOT NULL CHECK(jsonb_typeof(lot_allocations)='array'),
    PRIMARY KEY(object_id,object_version), UNIQUE(account_id,mode,strategy_id,security_id,object_version),
    FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode)
  $cols$,mode_check));
  PERFORM p0_create_versioned_table(ledger_name,format($cols$
    object_id TEXT NOT NULL, account_id TEXT NOT NULL, mode execution_mode NOT NULL CHECK(%s), strategy_id trading_namespace NOT NULL,
    account_sequence BIGINT NOT NULL CHECK(account_sequence>0),
    entry_type TEXT NOT NULL CHECK(entry_type IN ('CASH_IN','CASH_OUT','BUY','SELL','FEE','CORPORATE_ACTION','RECONCILIATION')),
    amount_cents money_cents NOT NULL, balance_cents money_cents NOT NULL,
    fill_id TEXT, fill_version positive_version, previous_entry_hash sha256_digest,
    PRIMARY KEY(object_id,object_version), UNIQUE(account_id,mode,account_sequence),
    FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode),
    FOREIGN KEY(fill_id,fill_version,account_id,mode,strategy_id) REFERENCES %I(object_id,object_version,account_id,mode,strategy_id),
    CHECK((fill_id IS NULL)=(fill_version IS NULL))
  $cols$,mode_check,fills_name));
END $$;
SELECT p0_create_transaction_family('sim','mode IN (''DEV'',''PAPER'')');
SELECT p0_create_transaction_family('real','mode=''PROD''');

SELECT p0_create_versioned_table('backtest_runs',$columns$
  object_id TEXT NOT NULL, strategy_id trading_namespace NOT NULL, mode execution_mode NOT NULL CHECK(mode IN ('DEV','PAPER')),
  account_id TEXT NOT NULL, snapshot_id TEXT NOT NULL, snapshot_version positive_version NOT NULL, data_hash sha256_digest NOT NULL,
  config_id TEXT NOT NULL, config_version positive_version NOT NULL, config_hash sha256_digest NOT NULL,
  rule_version TEXT NOT NULL, cost_version TEXT NOT NULL, feature_version TEXT NOT NULL,
  git_commit TEXT NOT NULL, scenario TEXT NOT NULL CHECK(scenario IN ('BASE','PESSIMISTIC','OPTIMISTIC','SYNTHETIC_REGRESSION')),
  result JSONB NOT NULL CHECK(jsonb_typeof(result)='object'), result_hash sha256_digest NOT NULL,
  PRIMARY KEY(object_id,object_version), UNIQUE(object_id,object_version,strategy_id,result_hash),
  FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode),
  FOREIGN KEY(snapshot_id,snapshot_version,data_hash) REFERENCES snapshot_manifests(object_id,object_version,data_hash),
  FOREIGN KEY(config_id,config_version,config_hash) REFERENCES config_versions(object_id,object_version,config_hash)
$columns$);

SELECT p0_create_versioned_table('strategy_metrics',$columns$
  object_id TEXT NOT NULL, run_id TEXT NOT NULL, run_version positive_version NOT NULL,
  strategy_id trading_namespace NOT NULL, result_hash sha256_digest NOT NULL,
  stratum TEXT NOT NULL, metrics JSONB NOT NULL CHECK(jsonb_typeof(metrics)='object'),
  sample_count BIGINT NOT NULL CHECK(sample_count>=0),
  PRIMARY KEY(object_id,object_version), UNIQUE(run_id,run_version,stratum,object_version),
  FOREIGN KEY(run_id,run_version,strategy_id,result_hash) REFERENCES backtest_runs(object_id,object_version,strategy_id,result_hash)
$columns$);

SELECT p0_create_versioned_table('audit_log',$columns$
  object_id TEXT NOT NULL, actor_kind TEXT NOT NULL CHECK(actor_kind IN ('HUMAN_USER','SERVICE','LLM','LEGACY_IMPORT')),
  actor_id TEXT NOT NULL, action TEXT NOT NULL, account_id TEXT, mode execution_mode, strategy_id strategy_namespace,
  before_state JSONB, after_state JSONB, previous_event_hash sha256_digest,
  PRIMARY KEY(object_id,object_version), CHECK((account_id IS NULL)=(mode IS NULL)),
  FOREIGN KEY(account_id,mode) REFERENCES accounts(account_id,mode)
$columns$);

SELECT p0_create_versioned_table('legacy_asset_registry',$columns$
  object_id TEXT NOT NULL, asset_kind TEXT NOT NULL,
  disposition TEXT NOT NULL CHECK(disposition IN ('KEEP','MODIFY','ISOLATE','DEPRECATE','DELETE_LATER')),
  external_locator TEXT NOT NULL, original_hash sha256_digest NOT NULL,
  legacy_namespace TEXT NOT NULL, legacy_assumptions JSONB NOT NULL,
  compatibility_status TEXT NOT NULL CHECK(compatibility_status IN ('PRESERVED','KNOWN_ISSUE','UNVERIFIED')),
  mapping_to_trading_strategy TEXT CHECK(mapping_to_trading_strategy IS NULL),
  PRIMARY KEY(object_id,object_version)
$columns$);

SELECT p0_create_versioned_table('staging_imports',$columns$
  object_id TEXT NOT NULL, legacy_asset_id TEXT, legacy_asset_version positive_version,
  fixture_kind TEXT NOT NULL CHECK(fixture_kind IN ('SYNTHETIC','LEGACY','SOURCE_SAMPLE')),
  raw_uri TEXT NOT NULL, raw_hash sha256_digest NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('QUARANTINED','VALIDATED','REJECTED')),
  normalized_payload JSONB NOT NULL,
  PRIMARY KEY(object_id,object_version),
  FOREIGN KEY(legacy_asset_id,legacy_asset_version) REFERENCES legacy_asset_registry(object_id,object_version),
  CHECK((legacy_asset_id IS NULL)=(legacy_asset_version IS NULL)),
  CHECK(fixture_kind<>'LEGACY' OR legacy_asset_id IS NOT NULL)
$columns$);

-- Explicit cutoff required; no current/latest view is usable as historical truth.
CREATE FUNCTION financials_as_of(cutoff TIMESTAMPTZ, visibility_basis TEXT DEFAULT 'OBSERVED_AS_OF')
RETURNS SETOF financials LANGUAGE plpgsql STABLE AS $$
BEGIN
  IF visibility_basis NOT IN ('OBSERVED_AS_OF','PUBLIC_AS_OF') THEN RAISE EXCEPTION 'UNKNOWN_VISIBILITY_BASIS'; END IF;
  RETURN QUERY SELECT DISTINCT ON (f.security_id,f.period,f.statement_type,f.source_id) f.*
    FROM financials f WHERE f.available_at<=cutoff AND f.published_at<=cutoff
      AND (visibility_basis='PUBLIC_AS_OF' OR f.retrieved_at<=cutoff)
    ORDER BY f.security_id,f.period,f.statement_type,f.source_id,f.available_at DESC,f.object_version DESC;
END $$;

CREATE FUNCTION bars_1d_as_of(cutoff TIMESTAMPTZ, visibility_basis TEXT DEFAULT 'OBSERVED_AS_OF')
RETURNS SETOF bars_1d LANGUAGE plpgsql STABLE AS $$
BEGIN
  IF visibility_basis NOT IN ('OBSERVED_AS_OF','PUBLIC_AS_OF') THEN RAISE EXCEPTION 'UNKNOWN_VISIBILITY_BASIS'; END IF;
  RETURN QUERY SELECT DISTINCT ON (b.security_id,b.trade_date,b.price_basis,b.adjustment_id,b.adjustment_version,b.source_id) b.*
    FROM bars_1d b WHERE b.event_time<=cutoff AND b.available_at<=cutoff AND (b.published_at IS NULL OR b.published_at<=cutoff)
      AND (visibility_basis='PUBLIC_AS_OF' OR b.retrieved_at<=cutoff)
    ORDER BY b.security_id,b.trade_date,b.price_basis,b.adjustment_id,b.adjustment_version,b.source_id,b.available_at DESC,b.object_version DESC;
END $$;

CREATE INDEX financials_pit_idx ON financials(security_id,period,statement_type,available_at,retrieved_at);
CREATE INDEX bars_1d_pit_idx ON bars_1d(security_id,trade_date,price_basis,available_at,retrieved_at);
CREATE INDEX signal_card_idx ON signal_events(card_id,card_version,strategy_id);
CREATE INDEX audit_trace_idx ON audit_log(trace_id,event_time);

CREATE FUNCTION check_adjustment_action_visibility() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE a adjustment_versions%ROWTYPE; c corp_actions%ROWTYPE;
BEGIN
  SELECT * INTO a FROM adjustment_versions WHERE object_id=NEW.adjustment_id AND object_version=NEW.adjustment_version;
  SELECT * INTO c FROM corp_actions WHERE object_id=NEW.action_id AND object_version=NEW.action_version;
  IF c.security_id<>NEW.security_id THEN RAISE EXCEPTION 'CORPORATE_ACTION_SECURITY_MISMATCH'; END IF;
  IF c.available_at>a.decision_cutoff OR (a.visibility_basis='OBSERVED_AS_OF' AND c.retrieved_at>a.decision_cutoff)
    OR NEW.available_at>a.available_at THEN RAISE EXCEPTION 'PIT_FUTURE_CORPORATE_ACTION_BLOCKED'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER adjustment_action_visibility BEFORE INSERT ON adjustment_actions FOR EACH ROW EXECUTE FUNCTION check_adjustment_action_visibility();

CREATE FUNCTION check_adjusted_bar_visibility() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE a adjustment_versions%ROWTYPE;
BEGIN
  IF NEW.price_basis='ADJUSTED' THEN
    SELECT * INTO a FROM adjustment_versions WHERE object_id=NEW.adjustment_id AND object_version=NEW.adjustment_version;
    IF NEW.available_at<a.available_at OR NEW.retrieved_at<a.retrieved_at THEN RAISE EXCEPTION 'ADJUSTED_BAR_BEFORE_FACTOR'; END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER adjusted_bar_visibility BEFORE INSERT ON bars_1d FOR EACH ROW EXECUTE FUNCTION check_adjusted_bar_visibility();
CREATE TRIGGER adjusted_bar_visibility BEFORE INSERT ON bars_1m FOR EACH ROW EXECUTE FUNCTION check_adjusted_bar_visibility();

-- An object's later revisions cannot silently move to another namespace/account.
CREATE FUNCTION check_revision_namespace() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE prior JSONB; incoming JSONB := to_jsonb(NEW);
BEGIN
  EXECUTE format('SELECT to_jsonb(t) FROM %I t WHERE object_id=$1 ORDER BY object_version LIMIT 1',TG_TABLE_NAME)
    INTO prior USING NEW.object_id;
  IF prior IS NOT NULL AND ((prior->'strategy_id') IS DISTINCT FROM (incoming->'strategy_id')
    OR (prior->'account_id') IS DISTINCT FROM (incoming->'account_id')
    OR (prior->'mode') IS DISTINCT FROM (incoming->'mode')) THEN RAISE EXCEPTION 'REVISION_NAMESPACE_CHANGE_BLOCKED'; END IF;
  RETURN NEW;
END $$;
DO $$ DECLARE name TEXT; BEGIN
  FOREACH name IN ARRAY ARRAY['config_versions','account_profiles','features_eod','research_evidence','research_cards',
    'brain_packets','brain_reviews','candidate_eligibility','signal_events','account_snapshots','cost_estimates','order_drafts',
    'approvals','orders_sim','orders_real','positions_sim','positions_real','fills_sim','fills_real','ledger_sim','ledger_real',
    'backtest_runs','strategy_metrics'] LOOP
    EXECUTE format('CREATE TRIGGER revision_namespace BEFORE INSERT ON %I FOR EACH ROW EXECUTE FUNCTION check_revision_namespace()',name);
  END LOOP;
END $$;

CREATE FUNCTION check_financial_values() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v RECORD; announcement_available TIMESTAMPTZ; announcement_retrieved TIMESTAMPTZ; announcement_published TIMESTAMPTZ;
BEGIN
  FOR v IN SELECT value FROM jsonb_each(NEW.values_cents) LOOP
    IF jsonb_typeof(v.value)<>'string' OR (v.value #>> '{}') !~ '^-?(0|[1-9][0-9]{0,37})$' THEN
      RAISE EXCEPTION 'FINANCIAL_MONEY_INTEGER_STRING_REQUIRED';
    END IF;
  END LOOP;
  SELECT available_at,retrieved_at,published_at INTO announcement_available,announcement_retrieved,announcement_published FROM announcements
    WHERE object_id=NEW.announcement_id AND object_version=NEW.announcement_version;
  IF NEW.available_at<announcement_available OR NEW.retrieved_at<announcement_retrieved OR NEW.published_at<announcement_published THEN
    RAISE EXCEPTION 'FINANCIAL_BEFORE_DISCLOSURE'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER financial_values BEFORE INSERT ON financials FOR EACH ROW EXECUTE FUNCTION check_financial_values();

CREATE FUNCTION check_research_cutoff() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE cutoff TIMESTAMPTZ; frozen TIMESTAMPTZ;
BEGIN
  SELECT decision_cutoff,frozen_at INTO cutoff,frozen FROM snapshot_manifests
    WHERE object_id=NEW.snapshot_id AND object_version=NEW.snapshot_version;
  IF NEW.decision_cutoff<>cutoff OR NEW.available_at<frozen THEN RAISE EXCEPTION 'SNAPSHOT_CUTOFF_MISMATCH'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER card_cutoff BEFORE INSERT ON research_cards FOR EACH ROW EXECUTE FUNCTION check_research_cutoff();
CREATE TRIGGER packet_cutoff BEFORE INSERT ON brain_packets FOR EACH ROW EXECUTE FUNCTION check_research_cutoff();

CREATE FUNCTION check_evidence_cutoff() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE cutoff TIMESTAMPTZ; basis TEXT; evidence_available TIMESTAMPTZ; evidence_retrieved TIMESTAMPTZ;
BEGIN
  SELECT c.decision_cutoff,s.visibility_basis INTO cutoff,basis FROM research_cards c
    JOIN snapshot_manifests s ON s.object_id=c.snapshot_id AND s.object_version=c.snapshot_version
    WHERE c.object_id=NEW.card_id AND c.object_version=NEW.card_version;
  SELECT available_at,retrieved_at INTO evidence_available,evidence_retrieved FROM research_evidence
    WHERE object_id=NEW.evidence_id AND object_version=NEW.evidence_version;
  IF evidence_available>cutoff OR (basis='OBSERVED_AS_OF' AND evidence_retrieved>cutoff) THEN
    RAISE EXCEPTION 'PIT_FUTURE_EVIDENCE_BLOCKED';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER evidence_cutoff BEFORE INSERT ON card_evidence FOR EACH ROW EXECUTE FUNCTION check_evidence_cutoff();

-- Inserting a historical order uses its event_time as the decision instant. The
-- future execution service must separately recheck freshness/current auth/config.
CREATE FUNCTION check_order_version_chain() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE d order_drafts%ROWTYPE; s signal_events%ROWTYPE; c research_cards%ROWTYPE; a approvals%ROWTYPE;
BEGIN
  SELECT * INTO d FROM order_drafts WHERE object_id=NEW.draft_id AND object_version=NEW.draft_version;
  IF NOT FOUND THEN RETURN NEW; END IF; -- exact FK reports absent draft
  SELECT * INTO s FROM signal_events WHERE object_id=d.signal_id AND object_version=d.signal_version;
  SELECT * INTO c FROM research_cards WHERE object_id=d.card_id AND object_version=d.card_version;
  IF s.state NOT IN ('TRIGGERED','ACKNOWLEDGED') OR s.triggered_at IS NULL OR s.triggered_at>NEW.event_time
      OR s.rule_version<>c.rule_version OR c.grade='UNSET_REQUIRED' THEN
    RAISE EXCEPTION 'ORDER_SIGNAL_OR_RULE_INVALID';
  END IF;
  IF d.available_at>NEW.event_time OR d.expires_at<=NEW.event_time OR
      s.available_at>NEW.event_time OR s.expires_at<=NEW.event_time OR
      c.available_at>NEW.event_time OR c.expires_at<=NEW.event_time THEN
    RAISE EXCEPTION 'EXPIRED_OR_FUTURE_ORDER_CHAIN';
  END IF;
  IF EXISTS(SELECT 1 FROM research_cards WHERE object_id=c.object_id AND object_version>c.object_version AND available_at<=NEW.event_time)
    OR EXISTS(SELECT 1 FROM signal_events WHERE object_id=s.object_id AND object_version>s.object_version AND available_at<=NEW.event_time) THEN
    RAISE EXCEPTION 'SUPERSEDED_ORDER_CHAIN';
  END IF;
  FOR a IN SELECT * FROM approvals WHERE
    (object_id=NEW.decision_approval_id AND object_version=NEW.decision_approval_version) OR
    (object_id=NEW.final_approval_id AND object_version=NEW.final_approval_version) LOOP
    IF a.available_at>NEW.event_time OR a.expires_at<=NEW.event_time THEN RAISE EXCEPTION 'EXPIRED_OR_FUTURE_APPROVAL'; END IF;
  END LOOP;
  RETURN NEW;
END $$;
CREATE TRIGGER order_version_chain BEFORE INSERT ON orders_sim FOR EACH ROW EXECUTE FUNCTION check_order_version_chain();
CREATE TRIGGER order_version_chain BEFORE INSERT ON orders_real FOR EACH ROW EXECUTE FUNCTION check_order_version_chain();

CREATE FUNCTION reject_history_mutation() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'APPEND_ONLY_HISTORY:%',TG_TABLE_NAME; END $$;
DO $$ DECLARE t RECORD; BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'schema_migrations' LOOP
    EXECUTE format('CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()',t.tablename);
    EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION reject_history_mutation()',t.tablename);
  END LOOP;
END $$;

DROP FUNCTION p0_create_transaction_family(TEXT,TEXT);
DROP FUNCTION p0_create_versioned_table(TEXT,TEXT);
COMMENT ON DOMAIN money_cents IS 'CNY integer cents: no fractional coercion, <38 decimal digits; explicit application rounding before insert.';
COMMENT ON TABLE approvals IS 'Human records only; actor/auth fields are claims validated by future trusted auth service, not DB authentication.';
COMMENT ON TABLE order_drafts IS 'Immutable unsigned intent target; hash syntax and FK equality do not prove content hash/authenticity.';
COMMENT ON TABLE snapshot_manifests IS 'content_hash/payload_hash project canonical wire content_hash; data_hash separately identifies dataset bytes. Projection importer not yet implemented.';
COMMENT ON TABLE accounts IS 'P0 production_authorized must be false. No P0 code can submit any broker orders.';
