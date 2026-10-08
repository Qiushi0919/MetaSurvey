import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {validateContract,contractNames} from '../src/contracts/validate.mjs';
import {productionGate} from '../src/baseline/gates.mjs';
const root=path.resolve(import.meta.dirname,'..');
const release=JSON.parse(fs.readFileSync(path.join(root,'contracts/release.v1.json'),'utf8'));
if(release.contract_version!=='1.0.0'||release.schema_version!==2||release.business_rules_inferred!==false)throw new Error('RELEASE_METADATA_INVALID');
if(JSON.stringify(release.contracts.map(c=>c.name).sort())!==JSON.stringify(contractNames())||release.contracts.length!==16)throw new Error('RELEASE_CONTRACT_INVENTORY_INVALID');
for(const entry of release.files) {
  const p=path.resolve(root,entry.path);if(!p.startsWith(`${root}${path.sep}`))throw new Error('RELEASE_PATH_INVALID');
  const actual=`sha256:${createHash('sha256').update(fs.readFileSync(p)).digest('hex')}`;
  if(actual!==entry.sha256)throw new Error(`FROZEN_BASELINE_CHANGED:${entry.path}`);
}
execFileSync(process.execPath,[path.join(root,'scripts/generate-contracts.mjs'),'--check'],{stdio:'inherit'});
for(const name of contractNames())validateContract(name,JSON.parse(fs.readFileSync(path.join(root,`tests/fixtures/synthetic/contracts/${name}.json`),'utf8')));
const profile=JSON.parse(fs.readFileSync(path.join(root,'config/account-profile.unconfigured.v1.json'),'utf8'));validateContract('AccountProfile',profile);
const gate=productionGate(profile);if(gate.allowed||gate.missing_paths.length<20)throw new Error('UNCONFIGURED_PRODUCTION_GATE_WEAKENED');
console.log(`Verified 16 contracts at 1.0.0, immutable release bytes and ${gate.missing_paths.length} explicit required configuration gaps.`);
