import test from 'node:test';
import assert from 'node:assert/strict';
import Decimal from 'decimal.js';
import { validateContract, contractNames, sealContract, hashValue } from '../src/contracts/validate.mjs';
import { examples, envelope, T, FUTURE } from './helpers.mjs';

for (const name of contractNames()) test(`${name} v1 required/optional/schema/hash validate explicit synthetic example`,()=>assert.equal(validateContract(name,examples().all[name]).contract_version,'1.0.0'));
test('Every contract rejects missing required field, unknown fields and unversioned hash tamper',()=>{
  for (const [name,value] of Object.entries(examples().all)) {
    const missing={...value};delete missing.trace_id;
    assert.throws(()=>validateContract(name,missing),{code:'CONTRACT_SCHEMA_INVALID'});
    assert.throws(()=>validateContract(name,sealContract({...value,unexpected:'injected'})),{code:'CONTRACT_SCHEMA_INVALID'});
    assert.throws(()=>validateContract(name,{...value,trace_id:'tampered'}),{code:'HASH_MISMATCH'});
  }
});
test('No float/bool money, exponent or unzoned time in contracts',()=>{
  const e=examples().all.CostEstimate;
  for (const value of [100000,true,1.5,'1e5','NaN','Infinity','-0','01']) assert.throws(()=>validateContract('CostEstimate',sealContract({...e,notional_cents:value})));
  assert.throws(()=>validateContract('CostEstimate',sealContract({...e,price:'1e1'})));
  assert.throws(()=>validateContract('CostEstimate',sealContract({...e,recorded_at:'2026-10-05T02:00:00'})));
});
test('Research namespace produces neither signals/orders nor short-horizon card',()=>{
  const c=examples().all.ResearchCard;
  assert.throws(()=>validateContract('ResearchCard',sealContract({...c,strategy_id:'RESEARCH_6_18M'})),{code:'STRATEGY_NAMESPACE_MISMATCH'});
  for (const name of ['SignalEvent','OrderIntent','Approval','Fill','LedgerEntry']) assert.throws(()=>validateContract(name,sealContract({...examples().all[name],strategy_id:'RESEARCH_6_18M'})),{code:'CONTRACT_SCHEMA_INVALID'});
  assert.throws(()=>validateContract('ResearchCard',sealContract({...c,trade:{...c.trade,target_holding_sessions:{minimum:5,maximum:8}}})),{code:'STRATEGY_HORIZON_MISMATCH'});
});
test('Missing probability calibration proof and hard negative prevent eligible card',()=>{
  const c=examples().all.ResearchCard;
  assert.throws(()=>validateContract('ResearchCard',sealContract({...c,probability:{...c.probability,calibration_ref:null}})),{code:'UNCALIBRATED_PROBABILITY'});
  assert.throws(()=>validateContract('ResearchCard',sealContract({...c,hard_blocks:['THESIS_INVALIDATED']})),{code:'DATA_QUALITY_FAILED'});
});
test('Available/retrieved never precede a precise publication and payload hashes bind raw projection',()=>{
  const e=envelope();
  assert.throws(()=>validateContract('DataEnvelope',sealContract({...e,provenance:{...e.provenance,published_at:FUTURE,publication_precision:'SECOND'}})),{code:'INVALID_CLOCK'});
  assert.throws(()=>validateContract('DataEnvelope',sealContract({...e,payload:{title:'different'}})),{code:'HASH_MISMATCH'});
  assert.equal(hashValue({a:'-0.005',b:'0.1'}),hashValue({b:'0.1',a:'-0.005'}));
});
test('LLM APPROVE cannot be an Approval actor or USER approval enum',()=>{
  const a=examples().all.Approval;
  for (const patch of [{actor_type:'LLM'},{decision:'APPROVE'},{channel:'LLM'}]) assert.throws(()=>validateContract('Approval',sealContract({...a,...patch})),{code:'CONTRACT_SCHEMA_INVALID'});
});
test('BrainPacket validates nested payload/content hashes and excludes future evidence',()=>{
  const packet=examples().all.BrainPacket;
  const tampered=structuredClone(packet);tampered.evidence[0].payload.title='tampered title';
  assert.throws(()=>validateContract('BrainPacket',sealContract(tampered)),{code:'HASH_MISMATCH'});
  const future=structuredClone(packet);future.evidence[0]=envelope({provenance:{...envelope().provenance,available_at:FUTURE,retrieved_at:FUTURE}});
  assert.throws(()=>validateContract('BrainPacket',sealContract(future)),{code:'FUTURE_DATA'});
});
test('Money validation retains full legal precision independently of global Decimal settings',()=>{
  const cost=examples().all.CostEstimate;
  const price='12345678901234.123456',quantity=9007199254740991;
  const exact=(12345678901234123456n*BigInt(quantity)+5000n)/10000n;
  assert.equal(exact.toString(),'11119998979846757342693147619778');
  const oldPrecision=Decimal.precision;
  try {
    Decimal.set({precision:10});
    validateContract('CostEstimate',sealContract({...cost,price,quantity,notional_cents:exact.toString()}));
    assert.throws(()=>validateContract('CostEstimate',sealContract({...cost,price,quantity,notional_cents:'11119998979846757343000000000000'})),{code:'RECONCILIATION_FAILED'});
  } finally { Decimal.set({precision:oldPrecision}); }
});
test('Canonical identity, positive trade prices, valid feature values and active state are consistent',()=>{
  const all=examples().all;
  assert.throws(()=>validateContract('SecurityIdentity',sealContract({...all.SecurityIdentity,symbol:'SZSE:000001'})),{code:'SECURITY_IDENTITY_MISMATCH'});
  assert.throws(()=>validateContract('SecurityIdentity',sealContract({...all.SecurityIdentity,tick_size:'0'})),{code:'PRICE_INVALID'});
  assert.throws(()=>validateContract('OrderIntent',sealContract({...all.OrderIntent,limit_price:'0'})),{code:'PRICE_INVALID'});
  assert.throws(()=>validateContract('FeatureSet',sealContract({...all.FeatureSet,features:{bad:{value:null,unit:'RATIO',quality:'VALID'}}})),{code:'DATA_QUALITY_FAILED'});
  assert.throws(()=>validateContract('DataEnvelope',sealContract({...all.DataEnvelope,invalidation:{...all.DataEnvelope.invalidation,invalidated_at:T}})),{code:'INVALIDATION_STATE_INVALID'});
});
test('Future bar observations cannot be backdated while announced future actions remain representable',()=>{
  const e=envelope({data_kind:'BAR_1D'}),p={...e.provenance,event_time:FUTURE};
  assert.throws(()=>validateContract('DataEnvelope',sealContract({...e,provenance:p})),{code:'FUTURE_MARKET_DATA'});
  validateContract('DataEnvelope',sealContract({...e,data_kind:'CORPORATE_ACTION',provenance:p}));
});
