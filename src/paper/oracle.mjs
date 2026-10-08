// Independent BigInt rational oracle. It imports no cost functions and uses no Decimal.
import { hashValue } from '../contracts/validate.mjs';
const genesis=hashValue({kind:'P1A_PAPER_LEDGER_GENESIS',version:'1.0.0'});
function check(test,code){if(!test)throw new Error(code);}
function scaled(value,places){check(typeof value==='string'&&/^(0|[1-9][0-9]*)(\.[0-9]+)?$/.test(value),'ORACLE_DECIMAL_INVALID');const[whole,fraction='']=value.split('.');check(fraction.length<=places,'ORACLE_PRECISION_INVALID');return BigInt(whole)*10n**BigInt(places)+BigInt(fraction.padEnd(places,'0')||'0');}
function halfUp(numerator,denominator){check(numerator>=0n&&denominator>0n,'ORACLE_SIGN_INVALID');return(numerator*2n+denominator)/(2n*denominator);}
export function independentCostOracle({profile,side,fills}){
  check(side==='BUY'||side==='SELL','ORACLE_SIDE_INVALID');let micros=0n,gross=0n,quantity=0;
  for(const f of fills){check(Number.isSafeInteger(f.quantity)&&f.quantity>0,'ORACLE_QUANTITY_INVALID');const v=scaled(f.price,6)*BigInt(f.quantity);micros+=v;gross+=halfUp(v,10000n);quantity+=f.quantity;}
  const fee=r=>halfUp(micros*scaled(r,10),100000000000000n);
  let proportional=0n,actual=0n,tax=0n,exchange=0n,other=0n,slip=0n;
  if(fills.length){proportional=fee(profile.commission_rate);actual=proportional>BigInt(profile.minimum_commission_cents)?proportional:BigInt(profile.minimum_commission_cents);tax=side==='SELL'?fee(profile.stamp_tax_sell_rate):0n;exchange=profile.exchange_fee.included_in==='EXCLUDED'?fee(profile.exchange_fee.rate):0n;other=profile.other_fee.included_in==='EXCLUDED'?fee(profile.other_fee.rate):0n;slip=profile.slippage.treatment==='SEPARATE_ESTIMATE'?fee(profile.slippage.rate):0n;}
  const friction=actual+tax+exchange+other+slip;
  return{quantity,notional_cents:gross.toString(),commission_cents:actual.toString(),proportional_commission_cents:proportional.toString(),minimum_commission_effect_cents:(actual-proportional).toString(),stamp_tax_cents:tax.toString(),exchange_fee_cents:exchange.toString(),other_fee_cents:other.toString(),slippage_cents:slip.toString(),total_friction_cents:friction.toString(),actual_commission_cents:actual.toString(),cash_delta_cents:(side==='BUY'?-gross-friction:gross-friction).toString()};
}
export function reconcilePaperAccount({account,ledger,orders}){
  let cash=BigInt(account.opening_cash_cents),reserved=0n,head=genesis,sequence=0;
  const orderMap=new Map(orders.map(o=>[o.order_id,o]));const fills=new Map(),remaining=new Map(),positions=new Map(),lotReservations=new Map();const lots=[];
  const feeKeys=['notional_cents','commission_cents','proportional_commission_cents','minimum_commission_effect_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents','total_friction_cents','actual_commission_cents','cash_delta_cents'];
  for(const entry of ledger){
    const{entry_hash,trace_id,...economic}=entry;
    check(hashValue(economic)===entry_hash,'LEDGER_HASH_MISMATCH');check(entry.previous_hash===head&&entry.sequence===++sequence,'LEDGER_CHAIN_MISMATCH');head=entry_hash;
    const order=orderMap.get(entry.order_id);check(order&&order.mode===account.mode&&order.account_id===account.account_id,'ORACLE_ORDER_SCOPE_MISMATCH');
    check(order.strategy===entry.strategy&&order.symbol===entry.symbol,'ORACLE_NAMESPACE_MISMATCH');
    let cashDelta=0n,newReservation=remaining.get(entry.order_id)??0n;
    if(entry.event==='RESERVE'){
      check(!fills.has(entry.order_id),'ORACLE_DUPLICATE_ORDER');fills.set(entry.order_id,[]);
      const cost=independentCostOracle({profile:order.profile_json,side:order.side,fills:[{price:order.intent_json.limit_price,quantity:order.intent_json.quantity}]});
      newReservation=order.side==='BUY'?((scaled(order.intent_json.limit_price,6)+9999n)/10000n)*BigInt(order.intent_json.quantity)+BigInt(cost.total_friction_cents):BigInt(cost.total_friction_cents);
      if(order.side==='SELL'){let needed=order.intent_json.quantity;const allocations=[];for(const lot of lots.filter(l=>l.strategy===entry.strategy&&l.symbol===entry.symbol&&l.sellable_date<=new Date(Date.parse(entry.event_time)+8*60*60*1000).toISOString().slice(0,10)).sort((a,b)=>a.bought_date.localeCompare(b.bought_date)||a.lot_id.localeCompare(b.lot_id))){const take=Math.min(lot.remaining_quantity-lot.reserved_quantity,needed);if(take){lot.reserved_quantity+=take;allocations.push({lot_id:lot.lot_id,quantity:take});needed-=take;}}check(needed===0,'ORACLE_SELL_RESERVE_SHORTFALL');lotReservations.set(entry.order_id,allocations);}
    }else if(entry.event==='FILL'){
      const prior=fills.get(entry.order_id);check(prior,'ORACLE_UNRESERVED_FILL');
      const before=independentCostOracle({profile:order.profile_json,side:order.side,fills:prior});
      const next={fill_id:entry.fill_id,price:entry.price,quantity:entry.quantity,trade_date:entry.trade_date};prior.push(next);
      const after=independentCostOracle({profile:order.profile_json,side:order.side,fills:prior});
      for(const key of feeKeys){check(entry.cumulative_cost[key]===after[key],`ORACLE_CUMULATIVE_COST_MISMATCH:${key}`);check(entry.cost_delta[key]===(BigInt(after[key])-BigInt(before[key])).toString(),`ORACLE_COST_DELTA_MISMATCH:${key}`);}
      cashDelta=BigInt(after.cash_delta_cents)-BigInt(before.cash_delta_cents);
      const rest=order.intent_json.quantity-after.quantity;check(rest>=0,'ORACLE_OVERFILL');
      const bound=rest?independentCostOracle({profile:order.profile_json,side:order.side,fills:[...prior,{price:order.intent_json.limit_price,quantity:rest}]}):after;
      newReservation=order.side==='BUY'?((scaled(order.intent_json.limit_price,6)+9999n)/10000n)*BigInt(rest)+BigInt(bound.total_friction_cents)-BigInt(after.total_friction_cents):BigInt(bound.total_friction_cents)-BigInt(after.total_friction_cents);
      const key=`${entry.strategy}:${entry.symbol}`;positions.set(key,(positions.get(key)??0n)+(order.side==='BUY'?BigInt(entry.quantity):-BigInt(entry.quantity)));check(positions.get(key)>=0,'ORACLE_CROSS_NAMESPACE_POSITION');
      if(order.side==='BUY'){
        const sellable=order.calendar_json.sessions.find(d=>d>entry.trade_date);check(sellable,'ORACLE_CALENDAR_NEXT_UNKNOWN');lots.push({lot_id:entry.fill_id,strategy:entry.strategy,symbol:entry.symbol,bought_date:entry.trade_date,sellable_date:sellable,remaining_quantity:entry.quantity,reserved_quantity:0});
      }else{
        let needed=entry.quantity;
        for(const allocation of lotReservations.get(entry.order_id)??[]){const lot=lots.find(l=>l.lot_id===allocation.lot_id);const take=Math.min(allocation.quantity,needed);if(take){check(lot.sellable_date<=entry.trade_date,'ORACLE_T1_BYPASS');allocation.quantity-=take;lot.remaining_quantity-=take;lot.reserved_quantity-=take;needed-=take;}}
        check(needed===0,'ORACLE_LOT_SHORTFALL');
      }
    }else if(entry.event==='CANCELLED'||entry.event==='REJECTED'){newReservation=0n;if(order.side==='SELL')for(const allocation of lotReservations.get(entry.order_id)??[]){const lot=lots.find(l=>l.lot_id===allocation.lot_id);lot.reserved_quantity-=allocation.quantity;allocation.quantity=0;}}
    else check(entry.event==='SUBMIT','ORACLE_EVENT_UNKNOWN');
    const reservationDelta=newReservation-(remaining.get(entry.order_id)??0n);remaining.set(entry.order_id,newReservation);
    check(entry.cash_delta_cents===cashDelta.toString()&&entry.reservation_delta_cents===reservationDelta.toString(),'ORACLE_LEDGER_DELTA_MISMATCH');cash+=cashDelta;reserved+=reservationDelta;check(cash>=reserved&&reserved>=0n,'ORACLE_OVERSPEND');
  }
  check(cash.toString()===account.settled_cash_cents&&reserved.toString()===account.reserved_cash_cents&&(cash-reserved).toString()===account.available_cash_cents,'ORACLE_CASH_RECONCILIATION');
  check(sequence===account.sequence&&head===account.ledger_chain_hash,'ORACLE_FINAL_CHAIN');
  check(orders.reduce((n,o)=>n+BigInt(o.remaining_reservation),0n)===reserved,'ORACLE_RESERVATION_SUM');
  for(const lot of account.lots){const expected=lots.find(l=>l.lot_id===lot.lot_id);check(expected&&expected.strategy===lot.strategy&&expected.symbol===lot.symbol&&expected.sellable_date===lot.sellable_date&&expected.remaining_quantity===Number(lot.remaining_quantity)&&expected.reserved_quantity===Number(lot.reserved_quantity),'ORACLE_LOT_RECONCILIATION');}
  check(lots.length===account.lots.length,'ORACLE_LOT_COUNT');
  return{passed:true,settled_cash_cents:cash.toString(),reserved_cash_cents:reserved.toString(),available_cash_cents:(cash-reserved).toString(),ledger_chain_hash:head,ledger_entries:sequence,positions:Object.fromEntries([...positions].sort().map(([key,value])=>[key,value.toString()]))};
}
