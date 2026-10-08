import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import Ajv from 'ajv/dist/2020.js';
const evidence=JSON.parse(fs.readFileSync(new URL('../../docs/overnight/evidence.json',import.meta.url)));
const schema=JSON.parse(fs.readFileSync(new URL('../../contracts/overnight/AdmissionReadinessDryRun.schema.json',import.meta.url)));
const validate=new Ajv({strict:true,allErrors:true}).compile(schema);
const source=JSON.parse(fs.readFileSync(evidence.artifacts.find(r=>r.object==='readiness').path));
test('diagnostic contract accepts the exact eight-category private dry-run report',()=>{
 assert.equal(validate(source),true,JSON.stringify(validate.errors));
 assert.equal(source.categories.length,8);assert.deepEqual(source.closed_business_condition_ids,[]);
});
test('every real permission, issued object count and account-default escalation is rejected',()=>{
 const mutations=[{productionGate:true},{source_admission:'ADMITTED'},{real_snapshot_B_ready:true},{pilot_ready:true},
  {cloud_export_permitted:true},{historical_backtest_permitted:true},{redistribution_permitted:true},{broker_permitted:true},
  {real_receipts_issued:1},{real_cards_issued:1},{new_source_policies:1},{all_actual_account_parameters:'10000'},
  {historical_visibility_proven:true},{closed_business_condition_ids:['C14']}];
 for(const patch of mutations)assert.equal(validate({...structuredClone(source),...patch}),false);
});
test('omitted lineage, category admission, and injected approvals cannot pass the diagnostic schema',()=>{
 const missing=structuredClone(source);delete missing.input_hashes.factor;assert.equal(validate(missing),false);
 const admitted=structuredClone(source);admitted.categories[0].admission_status='ADMITTED';assert.equal(validate(admitted),false);
 assert.equal(validate({...structuredClone(source),Approval:{actor_type:'HUMAN_USER'}}),false);
 const wider=structuredClone(source);wider.namespace='EVENT_3';assert.equal(validate(wider),false);
});
