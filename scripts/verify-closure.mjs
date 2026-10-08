import fs from 'node:fs/promises';import {execFile} from 'node:child_process';import {promisify} from 'node:util';
import {verifyCodeProvenance} from '../src/p1a/code-provenance.mjs';import {validateP1AContract} from '../src/p1a/contracts.mjs';import {sha,validateClosure} from '../src/closure/contracts.mjs';
const root=new URL('../',import.meta.url),read=p=>fs.readFile(new URL(p,root)),json=async p=>JSON.parse(await read(p));
const release=await json('contracts/release.closure.json'),old=await json('contracts/release.p1a.json'),historic=await json('config/p1a/code-provenance.json');
if(release.release_version!=='1.2.0'||release.schema_version!==6||release.production_execution_enabled!==false||release.p1b_research_enabled!==false||release.real_data_admission_gate!=='BLOCKED')throw Error('CLOSURE_SCOPE_GATE_CHANGED');
for(const [p,h]of [['contracts/release.v1.json','sha256:eee1c485838212210f646f755c0ce4c61b38b46dfd6fa1b8708a6ced1bb9b770'],['contracts/release.p1a.json','sha256:6e593b06f0b09f58ecf5f50e121f338cd7f73d752ce348330207e5c062e3a876']])if(sha(await read(p))!==h)throw Error('FROZEN_RELEASE_CHANGED:'+p);
for(const file of [...old.files,...release.files])if(sha(await read(file.path))!==file.sha256)throw Error('FROZEN_FILE_CHANGED:'+file.path);
const migrations=(await fs.readdir(new URL('migrations/',root))).filter(n=>n.endsWith('.sql')).sort();if(migrations.length!==6||migrations.some((n,i)=>Number(n.slice(0,3))!==i+1))throw Error('CLOSURE_MIGRATION_SEQUENCE_CHANGED');
const run=promisify(execFile);let git='git';try{await fs.access('/opt/homebrew/bin/git');git='/opt/homebrew/bin/git';}catch{}
// Historical proof is verified against its actual source commit, never misrepresented as current code.
for(const[p,h]of Object.entries(historic.files)){const bytes=(await run(git,['show',`${historic.code_version}:${p}`],{cwd:root,encoding:'buffer',maxBuffer:4194304})).stdout;if(sha(bytes)!==h)throw Error('HISTORICAL_SOURCE_PROOF_CHANGED:'+p);}
validateP1AContract('CodeProvenance',await verifyCodeProvenance(release));
console.log('Closure 1.2.0: historical immutable releases + all current committed source/fixtures + schema6 verified; real sources/production/P1B blocked.');
