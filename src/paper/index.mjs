import { hashValue, timestampMs } from '../contracts/validate.mjs';
import { assertPaperMode, ensure, cents, quantity, price, estimateCost, cumulativeCost, incrementalCost, validateCostProfile, maximumBuyReservation } from '../cost/index.mjs';
export { reconcilePaperAccount, independentCostOracle } from './oracle.mjs';

const queues = new WeakMap();
const zero = hashValue({ kind: 'P1A_PAPER_LEDGER_GENESIS', version: '1.0.0' });
const terminal = new Set(['FILLED', 'CANCELLED', 'REJECTED']);
const copy = v => structuredClone(v);
function noSecrets(value) {
  for (const [key, item] of Object.entries(value ?? {})) {
    ensure(!/(password|token|secret|credentials|broker_account_number)/i.test(key), 'SENSITIVE_FIELD_FORBIDDEN');
    if (item && typeof item === 'object') noSecrets(item);
  }
}
export function sealReferenceObject(value) { const { content_hash, ...body } = copy(value); return { ...body, content_hash: hashValue(body) }; }
function verifiedObject(value, code) { ensure(value && value.content_hash, code); const { content_hash, ...body } = value; ensure(content_hash === hashValue(body), code); return value; }
export function orderTermsHash(intent) { const { authorization, content_hash, ...terms } = intent; return hashValue(terms); }
function dayOf(clock) {
  timestampMs(clock);
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date(clock));
  const field = key => parts.find(p => p.type === key).value;
  return `${field('year')}-${field('month')}-${field('day')}`;
}
function clockCheck(input) { ensure(typeof input.trace_id === 'string' && input.trace_id, 'TRACE_REQUIRED'); timestampMs(input.event_time); noSecrets(input); }
function checkCalendar(calendar, clock) {
  verifiedObject(calendar, 'CALENDAR_HASH_MISMATCH');
  ensure(typeof calendar.version === 'string' && calendar.version && Array.isArray(calendar.sessions) && calendar.sessions.length > 1, 'CALENDAR_REQUIRED');
  ensure(calendar.sessions.every(d => typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d) && Number.isFinite(Date.parse(`${d}T00:00:00Z`)) && new Date(`${d}T00:00:00Z`).toISOString().slice(0,10)===d) && new Set(calendar.sessions).size === calendar.sessions.length && JSON.stringify(calendar.sessions) === JSON.stringify([...calendar.sessions].sort()), 'CALENDAR_SESSION_INVALID');
  ensure(timestampMs(calendar.available_at) <= timestampMs(clock), 'FUTURE_CALENDAR');
  ensure(calendar.source && ['SYNTHETIC_FIXTURE','OFFICIAL_CAPTURE'].includes(calendar.source.kind) && /^sha256:[a-f0-9]{64}$/.test(calendar.source.source_hash), 'CALENDAR_SOURCE_REQUIRED');
  const day = dayOf(clock); ensure(calendar.sessions.includes(day), 'NON_TRADING_SESSION'); return day;
}
function checkSecurity(security, symbol, clock) {
  verifiedObject(security, 'SECURITY_HASH_MISMATCH');
  ensure(security.canonical_symbol === symbol && /^(SSE|SZSE):[0-9]{6}$/.test(symbol), 'SECURITY_IDENTITY_MISMATCH');
  ensure(typeof security.security_id === 'string' && security.security_id && typeof security.original_symbol === 'string' && typeof security.version === 'string', 'SECURITY_VERSION_REQUIRED');
  quantity(security.lot_size);
  ensure(security.status === 'ACTIVE' && security.suspended === false && security.tradeable === true, 'SECURITY_NOT_TRADEABLE');
  ensure(timestampMs(security.available_at) <= timestampMs(clock), 'FUTURE_SECURITY');
}
function fresh(at, now) { const elapsed = timestampMs(now) - timestampMs(at); ensure(elapsed >= 0 && elapsed <= 5000, elapsed < 0 ? 'FUTURE_MARKET_DATA' : 'STALE_MARKET_DATA'); }
function checkAuthorization(intent, authorization, authority) {
  ensure(authorization && authorization.kind === 'FIXTURE_HUMAN_CONFIRMATION' && authorization.scope === 'SYNTHETIC_TEST_ONLY' && authorization.actor_type === 'HUMAN_USER', 'HUMAN_CONFIRMATION_REQUIRED');
  ensure(authorization.order_terms_hash === orderTermsHash(intent), 'APPROVAL_TERMS_MISMATCH');
  ensure(/^sha256:[a-f0-9]{64}$/.test(authorization.decision_approval_hash) && /^sha256:[a-f0-9]{64}$/.test(authorization.final_confirmation_hash) && authorization.decision_approval_hash !== authorization.final_confirmation_hash, 'TWO_PHASE_APPROVAL_REQUIRED');
  ensure(authority?.scope === 'SYNTHETIC_TEST_ONLY' && authority.actor_type === 'HUMAN_USER' && authority.verified_approval_hashes instanceof Set && authority.verified_approval_hashes.has(authorization.decision_approval_hash) && authority.verified_approval_hashes.has(authorization.final_confirmation_hash), 'UNTRUSTED_APPROVAL');
}
function intentCheck(intent, mode, event_time, security, calendar) {
  ensure(intent && intent.contract_name === 'PaperReplayOrderIntent' && intent.contract_version === '1.0.0' && intent.fixture_scope === 'SYNTHETIC_TEST_ONLY' && intent.mode === mode, 'PAPER_INTENT_SCOPE_INVALID');
  ensure(intent.strategy === 'CORE_40' || intent.strategy === 'EVENT_3', 'STRATEGY_NAMESPACE_MISMATCH');
  for (const key of ['account_id','order_id','client_order_id','rule_version','snapshot_hash','feature_hash']) ensure(typeof intent[key] === 'string' && intent[key], 'ORDER_BINDING_REQUIRED');
  quantity(intent.quantity); price(intent.limit_price); ensure(intent.side === 'BUY' || intent.side === 'SELL', 'ORDER_SIDE_INVALID');
  checkSecurity(security, intent.symbol, event_time); const day = checkCalendar(calendar, event_time);
  ensure(intent.trade_date === day, 'TRADE_DATE_CLOCK_MISMATCH');
  ensure(intent.calendar_hash === calendar.content_hash && intent.security_hash === security.content_hash, 'SOURCE_VERSION_BINDING_MISMATCH');
  ensure(intent.quantity % security.lot_size === 0, 'LOT_SIZE_VIOLATION');
  fresh(intent.market_data_at, event_time); ensure(timestampMs(intent.valid_until) > timestampMs(event_time), 'ORDER_EXPIRED');
  return day;
}
function cleanRequest(input) {
  const { authority, trace_id, ...request } = input; return request;
}
async function queued(db, work) {
  const previous = queues.get(db) ?? Promise.resolve();
  const next = previous.catch(() => {}).then(work); queues.set(db, next.catch(() => {})); return next;
}
async function rows(db, sql, params = []) { return (await db.query(sql, params)).rows; }
async function accountRow(db, mode, account_id, lock = false) {
  const account = (await rows(db, `SELECT mode,account_id,opening_cash::text,settled_cash::text,reserved_cash::text,sequence::text,last_event_time,opening_json,ledger_head FROM p1a_paper.accounts WHERE mode=$1 AND account_id=$2${lock ? ' FOR UPDATE' : ''}`, [mode,account_id]))[0];
  ensure(account, 'ACCOUNT_NOT_FOUND'); return account;
}
async function orderRow(db, mode, account_id, order_id) { const row = (await rows(db, 'SELECT *,remaining_reservation::text,limit_price::text,quantity::text,filled_quantity::text FROM p1a_paper.orders WHERE mode=$1 AND account_id=$2 AND order_id=$3 FOR UPDATE', [mode,account_id,order_id]))[0]; ensure(row, 'ORDER_NOT_FOUND'); return row; }
async function append(db, account, input, economic) {
  const sequence = Number(account.sequence) + 1; ensure(Number.isSafeInteger(sequence), 'SEQUENCE_OVERFLOW');
  const entry = { contract_name: 'PaperLedgerEvent', contract_version: '1.0.0', mode: input.mode, account_id: input.account_id, sequence, event_id: input.idempotency_key, event_time: input.event_time, business_timezone: 'Asia/Shanghai', ...economic, source: { source_id: 'P1A_PAPER_REFERENCE', source_version: '1.0.0', source_hash: hashValue(economic.source ?? {}), event_time: input.event_time, published_at: input.event_time, available_at: input.event_time, retrieved_at: input.event_time, visibility_basis: 'SYNTHETIC_DERIVED', ...(economic.source ?? {}) }, previous_hash: account.ledger_head };
  const entry_hash = hashValue(entry);
  await db.query('INSERT INTO p1a_paper.ledger(mode,account_id,sequence,event_id,event_time,entry_json,entry_hash,previous_hash) VALUES($1,$2,$3,$4,$5,$6,$7,$8)', [input.mode,input.account_id,sequence,input.idempotency_key,input.event_time,{ ...entry, trace_id: input.trace_id },entry_hash,account.ledger_head]);
  await db.query('UPDATE p1a_paper.accounts SET sequence=$3,last_event_time=$4,ledger_head=$5 WHERE mode=$1 AND account_id=$2', [input.mode,input.account_id,sequence,input.event_time,entry_hash]);
  return { ...entry, trace_id: input.trace_id, entry_hash };
}
function orderScope(row, input) { ensure(row.strategy === input.strategy && row.symbol === input.symbol, 'ORDER_SCOPE_MISMATCH'); }
async function transact(db, input, operation, work) {
  assertPaperMode(input.mode); clockCheck(input); ensure(typeof input.account_id === 'string' && input.account_id && typeof input.idempotency_key === 'string' && input.idempotency_key, 'IDEMPOTENCY_SCOPE_REQUIRED');
  const request_hash = hashValue({ operation, ...cleanRequest(input) });
  return queued(db, async () => {
    await db.exec('BEGIN');
    try {
      const account = await accountRow(db, input.mode,input.account_id,true);
      const prior = (await rows(db, 'SELECT operation,request_hash,result_json FROM p1a_paper.requests WHERE mode=$1 AND account_id=$2 AND idempotency_key=$3', [input.mode,input.account_id,input.idempotency_key]))[0];
      if (prior) { ensure(prior.operation === operation && prior.request_hash === request_hash, 'IDEMPOTENCY_PAYLOAD_CONFLICT'); await db.exec('COMMIT'); return prior.result_json; }
      ensure(timestampMs(input.event_time) >= new Date(account.last_event_time).getTime(), 'ACCOUNT_EVENT_ORDER_VIOLATION');
      const result = await work(account,request_hash);
      await db.query('INSERT INTO p1a_paper.requests(mode,account_id,idempotency_key,operation,request_hash,result_json) VALUES($1,$2,$3,$4,$5,$6)', [input.mode,input.account_id,input.idempotency_key,operation,request_hash,result]);
      await db.exec('COMMIT'); return result;
    } catch (error) { await db.exec('ROLLBACK'); throw error; }
  });
}
async function snapshotAccount(db,mode,account_id) {
  const a=await accountRow(db,mode,account_id);
  const lots=await rows(db,'SELECT strategy,symbol,lot_id,remaining_quantity::text,reserved_quantity::text,bought_date::text,sellable_date::text,cost_cents::text,calendar_hash FROM p1a_paper.lots WHERE mode=$1 AND account_id=$2 ORDER BY strategy,symbol,lot_id',[mode,account_id]);
  return{mode,account_id,opening_cash_cents:a.opening_cash,settled_cash_cents:a.settled_cash,reserved_cash_cents:a.reserved_cash,available_cash_cents:(BigInt(a.settled_cash)-BigInt(a.reserved_cash)).toString(),sequence:Number(a.sequence),ledger_chain_hash:a.ledger_head,lots};
}
async function snapshotLedger(db,mode,account_id) {
  return(await rows(db,'SELECT entry_json,entry_hash FROM p1a_paper.ledger WHERE mode=$1 AND account_id=$2 ORDER BY sequence',[mode,account_id])).map(r=>({...r.entry_json,entry_hash:r.entry_hash}));
}
async function readTransaction(db,work) {
  return queued(db,async()=>{await db.exec('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');try{const result=await work();await db.exec('COMMIT');return result;}catch(error){await db.exec('ROLLBACK');throw error;}});
}
export function createPaperService({ db }) {
  ensure(db?.query && db?.exec, 'DATABASE_ADAPTER_REQUIRED');
  return {
    async openAccount(input) {
      assertPaperMode(input.mode); clockCheck(input); const opening = cents(input.opening_cash_cents);
      ensure(input.fixture_scope === 'SYNTHETIC_TEST_ONLY' && typeof input.account_id === 'string' && input.account_id && input.source_ref?.content_hash, 'ACCOUNT_FIXTURE_PROVENANCE_REQUIRED');
      const { trace_id, ...economic } = input;
      return queued(db, async () => {
        await db.exec('BEGIN');
        try {
          const prior = (await rows(db, 'SELECT opening_json FROM p1a_paper.accounts WHERE mode=$1 AND account_id=$2', [input.mode,input.account_id]))[0];
          if (prior) ensure(hashValue(prior.opening_json) === hashValue(economic), 'ACCOUNT_OPENING_CONFLICT');
          else await db.query('INSERT INTO p1a_paper.accounts(mode,account_id,opening_cash,settled_cash,reserved_cash,last_event_time,opening_json,ledger_head) VALUES($1,$2,$3,$3,0,$4,$5,$6)', [input.mode,input.account_id,opening.toString(),input.event_time,economic,zero]);
          await db.exec('COMMIT'); return { mode: input.mode,account_id: input.account_id,opening_cash_cents: opening.toString() };
        } catch(error) { await db.exec('ROLLBACK'); throw error; }
      });
    },
    async reserveOrder(input) {
      assertPaperMode(input.mode); clockCheck(input);
      const { intent, cost_profile, security, calendar, authorization, authority } = input;
      ensure(intent?.account_id === input.account_id, 'ORDER_ACCOUNT_MISMATCH');
      const day = intentCheck(intent,input.mode,input.event_time,security,calendar);
      validateCostProfile(cost_profile,{mode:input.mode,trade_date:day});
      ensure(intent.cost_profile_hash === cost_profile.content_hash && intent.cost_version === cost_profile.object_version, 'COST_VERSION_BINDING_MISMATCH');
      checkAuthorization(intent,authorization,authority);
      return transact(db,input,'RESERVE', async (account,request_hash) => {
        const existing = await rows(db, 'SELECT request_hash FROM p1a_paper.orders WHERE mode=$1 AND account_id=$2 AND (order_id=$3 OR client_order_id=$4)', [input.mode,input.account_id,intent.order_id,intent.client_order_id]);
        ensure(!existing.length, 'DUPLICATE_ORDER');
        const cost = estimateCost({mode:input.mode,profile:cost_profile,side:intent.side,price:intent.limit_price,quantity:intent.quantity,trade_date:day});
        const reserve = intent.side === 'BUY' ? BigInt(maximumBuyReservation({mode:input.mode,profile:cost_profile,remaining_quantity:intent.quantity,limit_price:intent.limit_price,trade_date:day})) : BigInt(cost.total_friction_cents);
        ensure(reserve <= BigInt(account.settled_cash) - BigInt(account.reserved_cash), 'INSUFFICIENT_AVAILABLE_CASH');
        await db.query('INSERT INTO p1a_paper.orders(mode,account_id,order_id,client_order_id,strategy,symbol,side,quantity,limit_price,status,remaining_reservation,request_hash,intent_json,profile_json,security_json,calendar_json,cumulative_json) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,\'RESERVED\',$10,$11,$12,$13,$14,$15,$16)', [input.mode,input.account_id,intent.order_id,intent.client_order_id,intent.strategy,intent.symbol,intent.side,intent.quantity,intent.limit_price,reserve.toString(),request_hash,intent,cost_profile,security,calendar,cumulativeCost({mode:input.mode,profile:cost_profile,side:intent.side,fills:[],trade_date:day})]);
        if (intent.side === 'SELL') {
          const lots = await rows(db, 'SELECT *,remaining_quantity::text,reserved_quantity::text FROM p1a_paper.lots WHERE mode=$1 AND account_id=$2 AND strategy=$3 AND symbol=$4 AND sellable_date <= $5 ORDER BY bought_date,lot_id FOR UPDATE', [input.mode,input.account_id,intent.strategy,intent.symbol,day]);
          let needed = intent.quantity;
          for (const lot of lots) {
            const free = Number(lot.remaining_quantity) - Number(lot.reserved_quantity), take = Math.min(free,needed);
            if (take) { await db.query('UPDATE p1a_paper.lots SET reserved_quantity=reserved_quantity+$4 WHERE mode=$1 AND account_id=$2 AND lot_id=$3',[input.mode,input.account_id,lot.lot_id,take]); await db.query('INSERT INTO p1a_paper.lot_reservations(mode,account_id,order_id,lot_id,quantity) VALUES($1,$2,$3,$4,$5)',[input.mode,input.account_id,intent.order_id,lot.lot_id,take]); needed -= take; }
          }
          ensure(needed === 0, 'T1_OR_NAMESPACE_POSITION_UNAVAILABLE');
        }
        await db.query('UPDATE p1a_paper.accounts SET reserved_cash=reserved_cash+$3 WHERE mode=$1 AND account_id=$2',[input.mode,input.account_id,reserve.toString()]);
        const entry = await append(db,account,input,{ event: 'RESERVE',order_id:intent.order_id,strategy:intent.strategy,symbol:intent.symbol,side:intent.side,quantity:intent.quantity,cash_delta_cents:'0',reservation_delta_cents:reserve.toString(),source: {security_hash:security.content_hash,calendar_hash:calendar.content_hash,cost_profile_hash:cost_profile.content_hash,snapshot_hash:intent.snapshot_hash,feature_hash:intent.feature_hash,rule_version:intent.rule_version} });
        return { order_id:intent.order_id,status:'RESERVED',reserved_cash_cents:reserve.toString(),entry_hash:entry.entry_hash };
      });
    },
    async submitOrder(input) {
      return transact(db,input,'SUBMIT',async account => {
        const order=await orderRow(db,input.mode,input.account_id,input.order_id); orderScope(order,input);
        ensure(order.status === 'RESERVED','ORDER_NOT_RESERVED');
        fresh(order.intent_json.market_data_at,input.event_time); ensure(timestampMs(order.intent_json.valid_until)>timestampMs(input.event_time),'ORDER_EXPIRED');
        const day=checkCalendar(order.calendar_json,input.event_time); validateCostProfile(order.profile_json,{mode:input.mode,trade_date:day});
        await db.query('UPDATE p1a_paper.orders SET status=\'SUBMITTED\' WHERE mode=$1 AND account_id=$2 AND order_id=$3',[input.mode,input.account_id,input.order_id]);
        const entry=await append(db,account,input,{event:'SUBMIT',order_id:input.order_id,strategy:order.strategy,symbol:order.symbol,cash_delta_cents:'0',reservation_delta_cents:'0',source:{cost_profile_hash:order.profile_json.content_hash,calendar_hash:order.calendar_json.content_hash,security_hash:order.security_json.content_hash}});
        return {order_id:input.order_id,status:'SUBMITTED',entry_hash:entry.entry_hash};
      });
    },
    async fillOrder(input) {
      assertPaperMode(input.mode);
      quantity(input.quantity);price(input.price);ensure(typeof input.fill_id==='string'&&input.fill_id,'FILL_ID_REQUIRED');
      return transact(db,input,'FILL',async(account,request_hash)=>{
        const order=await orderRow(db,input.mode,input.account_id,input.order_id);orderScope(order,input);
        const duplicate=(await rows(db,'SELECT request_hash FROM p1a_paper.fills WHERE mode=$1 AND account_id=$2 AND fill_id=$3',[input.mode,input.account_id,input.fill_id]))[0];ensure(!duplicate,'DUPLICATE_FILL');
        ensure(order.status==='SUBMITTED'||order.status==='PARTIALLY_FILLED','ORDER_NOT_FILLABLE');
        ensure(timestampMs(order.intent_json.valid_until)>timestampMs(input.event_time),'ORDER_EXPIRED');fresh(input.market_data_at,input.event_time);
        const day=checkCalendar(order.calendar_json,input.event_time); validateCostProfile(order.profile_json,{mode:input.mode,trade_date:day});
        checkSecurity(order.security_json,order.symbol,input.event_time);
        ensure(order.side==='BUY'?price(input.price).lte(order.limit_price):price(input.price).gte(order.limit_price),'LIMIT_PRICE_VIOLATION');
        const filled=Number(order.filled_quantity)+input.quantity;ensure(Number.isSafeInteger(filled)&&filled<=Number(order.quantity),'FILL_QUANTITY_EXCEEDED');
        const next={fill_id:input.fill_id,price:input.price,quantity:input.quantity,trade_date:day,event_time:input.event_time};
        const {cumulative,delta}=incrementalCost({mode:input.mode,profile:order.profile_json,side:order.side,previous_fills:order.fills_json,next_fill:next,trade_date:day});
        const fillList=[...order.fills_json,next],remaining=Number(order.quantity)-filled;
        const bound=remaining?cumulativeCost({mode:input.mode,profile:order.profile_json,side:order.side,fills:[...fillList,{price:order.limit_price,quantity:remaining}],trade_date:day}):cumulative;
        const newReserve=order.side==='BUY'?BigInt(maximumBuyReservation({mode:input.mode,profile:order.profile_json,executed_fills:fillList,remaining_quantity:remaining,limit_price:order.limit_price,trade_date:day})):BigInt(bound.total_friction_cents)-BigInt(cumulative.total_friction_cents);
        ensure(newReserve>=0n,'RESERVATION_NEGATIVE');
        const reserveDelta=newReserve-BigInt(order.remaining_reservation),newCash=BigInt(account.settled_cash)+BigInt(delta.cash_delta_cents),newReserved=BigInt(account.reserved_cash)+reserveDelta;
        ensure(newCash>=newReserved&&newCash>=0n&&newReserved>=0n,'RESERVATION_CASH_EXCEEDED');ensure(newCash<10n**38n&&newReserved<10n**38n,'MONEY_OVERFLOW');
        if(order.side==='BUY'){
          const nextDay=order.calendar_json.sessions.find(d=>d>day);ensure(nextDay,'NEXT_TRADING_SESSION_UNKNOWN');
          await db.query('INSERT INTO p1a_paper.lots(mode,account_id,strategy,symbol,lot_id,original_quantity,remaining_quantity,bought_date,sellable_date,cost_cents,calendar_hash) VALUES($1,$2,$3,$4,$5,$6,$6,$7,$8,$9,$10)',[input.mode,input.account_id,order.strategy,order.symbol,input.fill_id,input.quantity,day,nextDay,(-BigInt(delta.cash_delta_cents)).toString(),order.calendar_json.content_hash]);
        }else{
          const lots=await rows(db,'SELECT r.lot_id,r.quantity::text,l.sellable_date::text FROM p1a_paper.lot_reservations r JOIN p1a_paper.lots l USING(mode,account_id,lot_id) WHERE r.mode=$1 AND r.account_id=$2 AND r.order_id=$3 ORDER BY l.bought_date,r.lot_id FOR UPDATE OF r,l',[input.mode,input.account_id,input.order_id]);
          let needed=input.quantity;
          for(const lot of lots){ensure(day>=String(lot.sellable_date).slice(0,10),'T1_BYPASS');const take=Math.min(Number(lot.quantity),needed);if(take){await db.query('UPDATE p1a_paper.lots SET remaining_quantity=remaining_quantity-$4,reserved_quantity=reserved_quantity-$4 WHERE mode=$1 AND account_id=$2 AND lot_id=$3',[input.mode,input.account_id,lot.lot_id,take]);await db.query('UPDATE p1a_paper.lot_reservations SET quantity=quantity-$5 WHERE mode=$1 AND account_id=$2 AND order_id=$3 AND lot_id=$4',[input.mode,input.account_id,input.order_id,lot.lot_id,take]);needed-=take;}}
          ensure(needed===0,'RESERVED_LOT_UNAVAILABLE');
        }
        const status=remaining?'PARTIALLY_FILLED':'FILLED';
        await db.query('UPDATE p1a_paper.accounts SET settled_cash=$3,reserved_cash=$4 WHERE mode=$1 AND account_id=$2',[input.mode,input.account_id,newCash.toString(),newReserved.toString()]);
        await db.query('UPDATE p1a_paper.orders SET status=$4,filled_quantity=$5,remaining_reservation=$6,fills_json=$7,cumulative_json=$8 WHERE mode=$1 AND account_id=$2 AND order_id=$3',[input.mode,input.account_id,input.order_id,status,filled,newReserve.toString(),fillList,cumulative]);
        const entry=await append(db,account,input,{event:'FILL',order_id:input.order_id,fill_id:input.fill_id,strategy:order.strategy,symbol:order.symbol,side:order.side,quantity:input.quantity,price:input.price,trade_date:day,cash_delta_cents:delta.cash_delta_cents,reservation_delta_cents:reserveDelta.toString(),cost_delta:delta,cumulative_cost:cumulative,source:{cost_profile_hash:order.profile_json.content_hash,cost_version:order.profile_json.object_version,calendar_hash:order.calendar_json.content_hash,calendar_version:order.calendar_json.version,security_hash:order.security_json.content_hash,security_version:order.security_json.version,snapshot_hash:order.intent_json.snapshot_hash,feature_hash:order.intent_json.feature_hash,rule_version:order.intent_json.rule_version}});
        const result={order_id:input.order_id,fill_id:input.fill_id,status,quantity:input.quantity,price:input.price,trade_date:day,cost_delta:delta,cumulative_cost:cumulative,settled_cash_cents:newCash.toString(),reserved_cash_cents:newReserved.toString(),entry_hash:entry.entry_hash};
        await db.query('INSERT INTO p1a_paper.fills(mode,account_id,fill_id,order_id,request_hash,result_json) VALUES($1,$2,$3,$4,$5,$6)',[input.mode,input.account_id,input.fill_id,input.order_id,request_hash,result]);return result;
      });
    },
    async cancelOrder(input){return closeOrder(input,'CANCELLED');},
    async rejectOrder(input){return closeOrder(input,'REJECTED');},
    async getAccount({mode,account_id}){assertPaperMode(mode);return readTransaction(db,()=>snapshotAccount(db,mode,account_id));},
    async getOrder({mode,account_id,order_id}){assertPaperMode(mode);return queued(db,async()=>{const row=(await rows(db,'SELECT *,remaining_reservation::text,limit_price::text,quantity::text,filled_quantity::text FROM p1a_paper.orders WHERE mode=$1 AND account_id=$2 AND order_id=$3',[mode,account_id,order_id]))[0];ensure(row,'ORDER_NOT_FOUND');return row;});},
    async getLedger({mode,account_id}){assertPaperMode(mode);return queued(db,()=>snapshotLedger(db,mode,account_id));},
    async reconcile({mode,account_id}){assertPaperMode(mode);return readTransaction(db,async()=>{const{reconcilePaperAccount}=await import('./oracle.mjs');const account=await snapshotAccount(db,mode,account_id),ledger=await snapshotLedger(db,mode,account_id);const orders=await rows(db,'SELECT *,remaining_reservation::text FROM p1a_paper.orders WHERE mode=$1 AND account_id=$2 ORDER BY order_id',[mode,account_id]);return reconcilePaperAccount({account,ledger,orders});});}
  };
  async function closeOrder(input,status){
    assertPaperMode(input.mode);
    ensure(typeof input.reason_code==='string'&&input.reason_code,'CLOSE_REASON_REQUIRED');
    return transact(db,input,status,async account=>{
      const order=await orderRow(db,input.mode,input.account_id,input.order_id);orderScope(order,input);ensure(!terminal.has(order.status),'ORDER_ALREADY_TERMINAL');
      const release=BigInt(order.remaining_reservation);
      if(order.side==='SELL'){
        const lots=await rows(db,'SELECT lot_id,quantity::text FROM p1a_paper.lot_reservations WHERE mode=$1 AND account_id=$2 AND order_id=$3',[input.mode,input.account_id,input.order_id]);
        for(const lot of lots){await db.query('UPDATE p1a_paper.lots SET reserved_quantity=reserved_quantity-$4 WHERE mode=$1 AND account_id=$2 AND lot_id=$3',[input.mode,input.account_id,lot.lot_id,lot.quantity]);await db.query('UPDATE p1a_paper.lot_reservations SET quantity=0 WHERE mode=$1 AND account_id=$2 AND order_id=$3 AND lot_id=$4',[input.mode,input.account_id,input.order_id,lot.lot_id]);}
      }
      await db.query('UPDATE p1a_paper.accounts SET reserved_cash=reserved_cash-$3 WHERE mode=$1 AND account_id=$2',[input.mode,input.account_id,release.toString()]);await db.query('UPDATE p1a_paper.orders SET status=$4,remaining_reservation=0 WHERE mode=$1 AND account_id=$2 AND order_id=$3',[input.mode,input.account_id,input.order_id,status]);
      const entry=await append(db,account,input,{event:status,order_id:input.order_id,strategy:order.strategy,symbol:order.symbol,reason_code:input.reason_code,cash_delta_cents:'0',reservation_delta_cents:(-release).toString(),source:{cost_profile_hash:order.profile_json.content_hash,calendar_hash:order.calendar_json.content_hash,security_hash:order.security_json.content_hash}});
      return{order_id:input.order_id,status,released_cash_cents:release.toString(),entry_hash:entry.entry_hash};
    });
  }
}
