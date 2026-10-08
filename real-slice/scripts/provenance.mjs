import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {hash,sha,requireSlice} from '../src/contracts.mjs';
import {gitBinary} from '../../p1b/scripts/provenance.mjs';
export const root=path.resolve(import.meta.dirname,'../..');
const run=promisify(execFile);
async function walk(folder){const out=[];for(const e of await fs.readdir(path.join(root,folder),{withFileTypes:true})){const p=folder+'/'+e.name;if(e.isDirectory())out.push(...await walk(p));else if(e.isFile()&&p!=='real-slice/config/code-provenance.json')out.push(p);}return out;}
export async function implementationPaths(){return [...await walk('real-slice'),...await walk('contracts/real-slice'),'contracts/release.real-slice.json','docs/real-slice/Interface-Freeze.md','docs/real-slice/capture-specs.json','docs/adr/ADR-016-current-observed-reference.md'].sort();}
export async function createProvenance(commit){requireSlice(/^[a-f0-9]{40}$/.test(commit),'SLICE_CODE_EPOCH_MISMATCH');const files={},git=await gitBinary();for(const p of await implementationPaths()){const actual=await fs.readFile(path.join(root,p)),original=(await run(git,['show',`${commit}:${p}`],{cwd:root,encoding:'buffer',maxBuffer:4194304})).stdout;requireSlice(sha(actual)===sha(original),'SLICE_CODE_EPOCH_MISMATCH');files[p]=sha(actual);}const body={version:'1.0.0',code_version:commit,source_tree_hash:hash(files),files,scope:'CURRENT_OBSERVED_REFERENCE_AND_SYNTHETIC_CHAIN_ONLY',schema_version:6,production_enabled:false};return {...body,content_hash:hash(body)};}
export async function verifyProvenance(){const pin=JSON.parse(await fs.readFile(path.join(root,'real-slice/config/code-provenance.json'),'utf8')),actual=await createProvenance(pin.code_version);requireSlice(hash(pin)===hash(actual),'SLICE_CODE_EPOCH_MISMATCH');return actual;}
export function epochOf(pin){return `${pin.code_version}:${pin.source_tree_hash}:schema6:clock1.0.0:receipt2.0.0:packet2.0.0`;}
