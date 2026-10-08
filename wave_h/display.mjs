// Readiness metadata only; no native contract or execution authority.
import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const names=['Actual-Collector-Readiness.json','Snapshot-B-Readiness.json','Forward-Paper-Readiness.json','Owner-Activation-Report.json','Historical-PIT-Three-Symbol-Matrix.json','Historical-PIT-Closure-Progress.json'];
const issued=new WeakSet();
const hash=b=>'sha256:'+createHash('sha256').update(b).digest('hex');
function freezeJson(x){if(x&&typeof x==='object'){for(const value of Object.values(x))freezeJson(value);Object.freeze(x);}return x;}
export function load(name){if(!names.includes(name))throw Error('WH_DISPLAY_NAME');
 const manifest=JSON.parse(fs.readFileSync(path.join(root,'docs/wave-h/evidence.json')));
 const r=manifest.artifacts.find(x=>x.name===name);const b=fs.readFileSync(path.join(root,'docs/wave-h',name));
 if(!r||hash(b)!==r.sha256||b.length!==r.bytes)throw Error('WH_DISPLAY_BYTES');const x=JSON.parse(b);
 if(x.productionGate!==false||x.actual_forward_days!==0||x.context_hash!==manifest.context_hash)throw Error('WH_DISPLAY_PROMOTION');
 const out=freezeJson({kind:'WAVE_H_READINESS_DISPLAY',name,body:x,live_money_authority:false});issued.add(out);return out;}
export function transition(x,target){if(!issued.has(x)||target!=='LOCAL_READINESS_DISPLAY')throw Error('WH_NO_NATIVE_PROMOTION');return x;}
export function execute(){throw Error('WH_NO_EXECUTION');}
export function exportCloud(){throw Error('WH_NO_CLOUD');}
