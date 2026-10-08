// Explicit maintainer operation before a reviewed release. Never called by CI/check.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
const root=path.resolve(import.meta.dirname,'..');
const names=fs.readdirSync(path.join(root,'contracts/v1')).filter(x=>x.endsWith('.schema.json')).sort();
const paths=[...names.map(x=>`contracts/v1/${x}`),'contracts/reason-codes.v1.json','contracts/persistence-mapping.v1.json','scripts/generate-contracts.mjs','src/contracts/validate.mjs','src/baseline/gates.mjs','src/baseline/economics.mjs','src/baseline/ledger.mjs','src/baseline/migrate.mjs','src/baseline/staging.mjs','config/account-profile.unconfigured.v1.json',...fs.readdirSync(path.join(root,'migrations')).filter(x=>x.endsWith('.sql')).sort().map(x=>`migrations/${x}`)];
const files=paths.map(p=>({path:p,sha256:`sha256:${createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex')}`}));
const release={contract_version:'1.0.0',schema_version:2,gate_status:'AWAITING_P0_GATE_REVIEW',business_rules_inferred:false,contracts:names.filter(x=>x!=='common.schema.json').map(x=>({name:x.replace('.schema.json',''),version:'1.0.0',path:`contracts/v1/${x}`})),files};
fs.writeFileSync(path.join(root,'contracts/release.v1.json'),JSON.stringify(release,null,2)+'\n');
console.log('P0 release bytes frozen; changes require an explicit reviewed release update.');
