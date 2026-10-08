import test from 'node:test';
import assert from 'node:assert/strict';
import Decimal from 'decimal.js';
import {estimateCost,cumulativeCost,incrementalCost,affordableQuantity,sealCostProfile,validateCostProfile} from '../src/cost/index.mjs';
import {independentCostOracle} from '../src/paper/oracle.mjs';
import {fixture,profile} from './p1a-paper-helpers.mjs';
const input={mode:'PAPER',profile,side:'BUY',price:'10',quantity:100,trade_date:'2025-04-10'};
const fields=['notional_cents','commission_cents','proportional_commission_cents','minimum_commission_effect_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents','total_friction_cents','actual_commission_cents','cash_delta_cents'];
function compare(actual,expected){for(const f of fields)assert.equal(actual[f],expected[f],f);}
test('P1-A cost uses independent BigInt oracle across rounding/minimum/tax and large precision boundaries',()=>{
  Decimal.set({precision:8});
  for(const side of ['BUY','SELL'])for(const price of ['0.005','1.234567','10','14.995','15','15.005','12345678901234.123456'])for(const quantity of [1,100,999,9007199254740991]){
    const cost=estimateCost({...input,side,price,quantity});compare(cost,independentCostOracle({profile,side,fills:[{price,quantity}]}));
  }
  Decimal.set({precision:20});
});
test('minimum effect is part of actual commission, never an extra fee',()=>{
  const c=estimateCost(input);assert.equal(c.commission_cents,'150');assert.equal(c.proportional_commission_cents,'100');assert.equal(c.minimum_commission_effect_cents,'50');assert.equal(c.total_friction_cents,'195');
  assert.equal(BigInt(c.total_friction_cents),['commission_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents'].reduce((n,k)=>n+BigInt(c[k]),0n));
});
test('partial cumulative settlement crosses minimum and reports negative sub-attribution delta correctly',()=>{
  const one={price:'10',quantity:100},two={price:'10',quantity:100};const first=incrementalCost({...input,previous_fills:[],next_fill:one});const second=incrementalCost({...input,previous_fills:[one],next_fill:two});
  assert.equal(first.delta.commission_cents,'150');assert.equal(second.delta.commission_cents,'50');assert.equal(second.delta.minimum_commission_effect_cents,'-50');assert.equal(second.cumulative.commission_cents,'200');compare(second.cumulative,independentCostOracle({profile,side:'BUY',fills:[one,two]}));
});
test('partial gross rounds per execution, fee basis uses exact cumulative notional',()=>{
  const fills=[{price:'0.005',quantity:1},{price:'0.005',quantity:1},{price:'0.005',quantity:1}];compare(cumulativeCost({...input,fills}),independentCostOracle({profile,side:'BUY',fills}));
  assert.equal(cumulativeCost({...input,fills}).notional_cents,'3');assert.equal(estimateCost({...input,price:'0.005',quantity:3}).notional_cents,'2');
});
test('fee-inclusive affordability rejects gross-only budget and passes exact all-in boundary',()=>{
  const args={...input,lot_size:100,max_quantity:10000,available_cash_cents:'100000'};assert.equal(affordableQuantity(args).quantity,0);assert.equal(affordableQuantity({...args,available_cash_cents:'100195'}).quantity,100);assert.equal(affordableQuantity({...args,available_cash_cents:'100194'}).quantity,0);
});
test('inclusion relationships and embedded slippage do not double count',()=>{
  const p=sealCostProfile({...fixture.cost_profile,exchange_fee:{rate:'0.5',included_in:'COMMISSION'},other_fee:{rate:'0.6',included_in:'COMMISSION'},slippage:{treatment:'INCLUDED_IN_EXECUTION_PRICE',rate:'0'}});const cost=estimateCost({...input,profile:p});assert.equal(cost.exchange_fee_cents,'0');assert.equal(cost.other_fee_cents,'0');assert.equal(cost.slippage_cents,'0');assert.equal(cost.total_friction_cents,'150');
  assert.throws(()=>estimateCost({...input,profile:sealCostProfile({...p,slippage:{treatment:'INCLUDED_IN_EXECUTION_PRICE',rate:'0.001'}})}),/SLIPPAGE_DOUBLE_COUNTING/);
});
test('cost version/hash/date and missing configuration fail closed',()=>{
  assert.throws(()=>estimateCost({...input,mode:'PROD'}),/PRODUCTION_DISABLED/);
  assert.throws(()=>estimateCost({...input,profile:{...profile,commission_rate:'0'}}),/HASH_MISMATCH/);
  for(const trade_date of ['2025-02-29','2025-99-99','2024-12-31','2026-01-01'])assert.throws(()=>estimateCost({...input,trade_date}),/DATE_INVALID/);
  for(const mutation of [{effective_from:'2025-99-99'},{effective_from:'2025-12-31',effective_to:'2025-01-01'},{commission_rate:'UNSET_REQUIRED'},{minimum_commission_cents:150},{commission_scope:'PER_FILL'},{exchange_fee:{rate:'0.01'}},{object_version:0}])assert.throws(()=>validateCostProfile(sealCostProfile({...fixture.cost_profile,...mutation}),input));
  assert.doesNotThrow(()=>estimateCost({...input,trade_date:'2025-01-01'}));assert.doesNotThrow(()=>estimateCost({...input,trade_date:'2025-12-31'}));
  assert.throws(()=>estimateCost({...input,price:10}),/PRICE_REQUIRED/);assert.throws(()=>estimateCost({...input,quantity:1.5}),/QUANTITY_REQUIRED/);
});
test('all-in amount rejects 39-digit cents although gross and individual fee each fit 38 digits',()=>{
  const p=sealCostProfile({...fixture.cost_profile,minimum_commission_cents:'99999999999999999999999999999999999999'});
  assert.throws(()=>estimateCost({...input,profile:p,price:'1',quantity:100}),/MONEY_OVERFLOW/);
  assert.throws(()=>affordableQuantity({...input,profile:p,price:'1',lot_size:100,max_quantity:100,available_cash_cents:'99999999999999999999999999999999999999'}),/MONEY_OVERFLOW/);
});
