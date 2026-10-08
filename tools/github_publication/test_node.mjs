// Public checkout: preserve test bytes and explicitly declare private-evidence exclusions.
import {readdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../../',import.meta.url));
const localReferences=[
  'P1A data: real SSE raw->staging->normalized->DQ remains explicit non-tradeable; official holiday adapters prove reference dates',
  'P1A data: public fixtures have original byte hashes and explicit unknown license/time provenance'
];
const localGitHistory=[
  'R01-R12 closure: actual isolated manual roundtrip repeats exact identities; zero execution writes',
  'R05 R06 R08 R09 R10: hostile model returns and missing Cost do not write any execution state',
  'Experiment A: actual committed source + immutable snapshot replay twice, trace/wall time do not change economics',
  'Experiment A mutations: cost version only/rule version only/source byte only change identity and invalidate old approval/result',
  'Experiment B: fixed fills/gross, strict friction/net ordering; Edge counts monotonic and all rejections coded',
  'code provenance rejects valid-looking historical SHA and unbound source tree',
  'actual split-fill gross reconciliation and fixture cash/session binding reject hidden input changes'
];
const localOnly=[...localReferences,...localGitHistory];
console.log(JSON.stringify({scope:'PUBLIC_SYNTHETIC_ENGINEERING_ONLY',local_only_cases_not_executed:[
  ...localReferences.map(name=>({name,reason:'REFERENCE_FIXTURES_HAVE_UNVERIFIED_REDISTRIBUTION_LICENSE'})),
  ...localGitHistory.map(name=>({name,reason:'ORIGINAL_CODE_PROVENANCE_REQUIRES_UNPUBLISHED_SOURCE_GIT_HISTORY'}))
],business_gate_relaxation:false}));
const pattern=`^(?:${localOnly.map(s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')})$`;
const files=readdirSync(new URL('../../tests/',import.meta.url)).filter(s=>s.endsWith('.test.mjs')).sort().map(s=>`tests/${s}`);
const r=spawnSync(process.execPath,['--test','--test-concurrency=1',`--test-skip-pattern=${pattern}`,...files],{cwd:root,stdio:'inherit'});
if(r.error)throw r.error;
process.exit(r.status??1);
