-- P1-A DEV/PAPER reference only. Separate tables cannot store PROD mode.
CREATE SCHEMA p1a_paper;
CREATE TABLE p1a_paper.accounts (
  mode TEXT NOT NULL CHECK (mode IN ('DEV','PAPER')),
  account_id TEXT NOT NULL,
  opening_cash money_cents NOT NULL CHECK (opening_cash >= 0),
  settled_cash money_cents NOT NULL CHECK (settled_cash >= 0),
  reserved_cash money_cents NOT NULL CHECK (reserved_cash >= 0 AND reserved_cash <= settled_cash),
  sequence BIGINT NOT NULL DEFAULT 0 CHECK (sequence >= 0),
  last_event_time TIMESTAMPTZ NOT NULL,
  opening_json JSONB NOT NULL,
  ledger_head sha256_digest NOT NULL,
  PRIMARY KEY(mode,account_id)
);
CREATE TABLE p1a_paper.orders (
  mode TEXT NOT NULL CHECK(mode IN ('DEV','PAPER')),
  account_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  client_order_id TEXT NOT NULL,
  strategy TEXT NOT NULL CHECK(strategy IN ('CORE_40','EVENT_3')),
  symbol TEXT NOT NULL CHECK(symbol ~ '^(SSE|SZSE):[0-9]{6}$'),
  side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
  quantity BIGINT NOT NULL CHECK(quantity > 0 AND quantity <= 9007199254740991),
  filled_quantity BIGINT NOT NULL DEFAULT 0 CHECK(filled_quantity >= 0 AND filled_quantity <= quantity),
  limit_price price_yuan NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('RESERVED','SUBMITTED','PARTIALLY_FILLED','FILLED','CANCELLED','REJECTED')),
  remaining_reservation money_cents NOT NULL CHECK(remaining_reservation >= 0),
  request_hash sha256_digest NOT NULL,
  intent_json JSONB NOT NULL,
  profile_json JSONB NOT NULL,
  security_json JSONB NOT NULL,
  calendar_json JSONB NOT NULL,
  fills_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  cumulative_json JSONB NOT NULL,
  PRIMARY KEY(mode,account_id,order_id),
  UNIQUE(mode,account_id,client_order_id),
  FOREIGN KEY(mode,account_id) REFERENCES p1a_paper.accounts(mode,account_id)
);
CREATE TABLE p1a_paper.lots (
  mode TEXT NOT NULL CHECK(mode IN ('DEV','PAPER')),
  account_id TEXT NOT NULL,
  strategy TEXT NOT NULL CHECK(strategy IN ('CORE_40','EVENT_3')),
  symbol TEXT NOT NULL,
  lot_id TEXT NOT NULL,
  original_quantity BIGINT NOT NULL CHECK(original_quantity > 0),
  remaining_quantity BIGINT NOT NULL CHECK(remaining_quantity >= 0 AND remaining_quantity <= original_quantity),
  reserved_quantity BIGINT NOT NULL DEFAULT 0 CHECK(reserved_quantity >= 0 AND reserved_quantity <= remaining_quantity),
  bought_date DATE NOT NULL,
  sellable_date DATE NOT NULL CHECK(sellable_date > bought_date),
  cost_cents money_cents NOT NULL CHECK(cost_cents >= 0),
  calendar_hash sha256_digest NOT NULL,
  PRIMARY KEY(mode,account_id,lot_id),
  FOREIGN KEY(mode,account_id) REFERENCES p1a_paper.accounts(mode,account_id)
);
CREATE TABLE p1a_paper.lot_reservations (
  mode TEXT NOT NULL CHECK(mode IN ('DEV','PAPER')),
  account_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  lot_id TEXT NOT NULL,
  quantity BIGINT NOT NULL CHECK(quantity >= 0),
  PRIMARY KEY(mode,account_id,order_id,lot_id),
  FOREIGN KEY(mode,account_id,order_id) REFERENCES p1a_paper.orders(mode,account_id,order_id),
  FOREIGN KEY(mode,account_id,lot_id) REFERENCES p1a_paper.lots(mode,account_id,lot_id)
);
CREATE TABLE p1a_paper.fills (
  mode TEXT NOT NULL CHECK(mode IN ('DEV','PAPER')),
  account_id TEXT NOT NULL,
  fill_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  request_hash sha256_digest NOT NULL,
  result_json JSONB NOT NULL,
  PRIMARY KEY(mode,account_id,fill_id),
  FOREIGN KEY(mode,account_id,order_id) REFERENCES p1a_paper.orders(mode,account_id,order_id)
);
CREATE TABLE p1a_paper.ledger (
  mode TEXT NOT NULL CHECK(mode IN ('DEV','PAPER')),
  account_id TEXT NOT NULL,
  sequence BIGINT NOT NULL CHECK(sequence > 0),
  event_id TEXT NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  entry_json JSONB NOT NULL,
  entry_hash sha256_digest NOT NULL,
  previous_hash sha256_digest NOT NULL,
  PRIMARY KEY(mode,account_id,sequence),
  UNIQUE(mode,account_id,event_id),
  FOREIGN KEY(mode,account_id) REFERENCES p1a_paper.accounts(mode,account_id)
);
CREATE TABLE p1a_paper.requests (
  mode TEXT NOT NULL CHECK(mode IN ('DEV','PAPER')),
  account_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  operation TEXT NOT NULL,
  request_hash sha256_digest NOT NULL,
  result_json JSONB NOT NULL,
  PRIMARY KEY(mode,account_id,idempotency_key),
  FOREIGN KEY(mode,account_id) REFERENCES p1a_paper.accounts(mode,account_id)
);
CREATE FUNCTION p1a_paper.append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'P1A_PAPER_APPEND_ONLY'; END; $$;
CREATE TRIGGER immutable_paper_fills BEFORE UPDATE OR DELETE ON p1a_paper.fills FOR EACH ROW EXECUTE FUNCTION p1a_paper.append_only();
CREATE TRIGGER immutable_paper_ledger BEFORE UPDATE OR DELETE ON p1a_paper.ledger FOR EACH ROW EXECUTE FUNCTION p1a_paper.append_only();
CREATE TRIGGER immutable_paper_requests BEFORE UPDATE OR DELETE ON p1a_paper.requests FOR EACH ROW EXECUTE FUNCTION p1a_paper.append_only();
-- Pre-release P1-A review: TRUNCATE must not bypass append-only evidence.
CREATE TRIGGER immutable_paper_fills_truncate BEFORE TRUNCATE ON p1a_paper.fills FOR EACH STATEMENT EXECUTE FUNCTION p1a_paper.append_only();
CREATE TRIGGER immutable_paper_ledger_truncate BEFORE TRUNCATE ON p1a_paper.ledger FOR EACH STATEMENT EXECUTE FUNCTION p1a_paper.append_only();
CREATE TRIGGER immutable_paper_requests_truncate BEFORE TRUNCATE ON p1a_paper.requests FOR EACH STATEMENT EXECUTE FUNCTION p1a_paper.append_only();
