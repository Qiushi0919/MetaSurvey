import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {productionGate} from '../src/baseline/gates.mjs';
import {sealContract,validateContract} from '../src/contracts/validate.mjs';
import {accountRequiredFields,unsetInventory} from '../src/p1a/unset-inventory.mjs';
const profile=JSON.parse(fs.readFileSync(new URL('../config/account-profile.unconfigured.v1.json',import.meta.url),'utf8'));
test('P1-A cannot weaken accepted P0 production/approval gate bytes',()=>{
  const release=JSON.parse(fs.readFileSync(new URL('../contracts/release.v1.json',import.meta.url),'utf8'));
  for(const entry of release.files){const bytes=fs.readFileSync(new URL('../'+entry.path,import.meta.url));assert.equal('sha256:'+createHash('sha256').update(bytes).digest('hex'),entry.sha256,entry.path);}
  assert.equal(productionGate(profile).allowed,false);
  for(const value of ['true','1','PAPER','PROD']){
    process.env.PRODUCTION_EXECUTION=value;assert.equal(productionGate(profile).allowed,false);
  }
  delete process.env.PRODUCTION_EXECUTION;
});
test('UNSET_REQUIRED inventory is generated from schema and the actual unconfigured profile',()=>{
  const inventory=unsetInventory(profile);assert.equal(inventory.fields.length,30);
  assert.ok(inventory.fields.every(x=>x.required&&x.schema&&x.offline_engineering_blocked===false));
  assert.equal(inventory.production_execution,'BLOCKED');
});
for(const {pointer} of accountRequiredFields())test(`production required ${pointer} missing -> structural rejection and production fail closed`,()=>{
  const altered=structuredClone(profile),keys=pointer.slice(1).split('/');let parent=altered;
  for(const key of keys.slice(0,-1))parent=parent[key];delete parent[keys.at(-1)];
  const unsigned=pointer==='/content_hash'?altered:sealContract(altered);
  assert.throws(()=>validateContract('AccountProfile',unsigned));assert.equal(productionGate(unsigned).allowed,false);
});
