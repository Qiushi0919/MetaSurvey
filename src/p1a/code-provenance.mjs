import {readFile,readdir,access} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {hashValue,requireThat} from '../contracts/validate.mjs';
const run=promisify(execFile),defaultRoot=path.resolve(import.meta.dirname,'../..');
const sha=b=>`sha256:${createHash('sha256').update(b).digest('hex')}`;
async function gitBinary(){try{await access('/opt/homebrew/bin/git');return '/opt/homebrew/bin/git';}catch{return 'git';}}
async function list(root,folder,suffix){const out=[];for(const e of await readdir(path.join(root,folder),{withFileTypes:true})){const p=path.posix.join(folder,e.name);if(e.isDirectory())out.push(...await list(root,p,suffix));else if(e.isFile()&&e.name.endsWith(suffix))out.push(p);}return out;}
export async function implementationFiles(root=defaultRoot){
 const old=[...await list(root,'src','.mjs'),...await list(root,'scripts','.mjs'),...await list(root,'tests','.mjs'),...await list(root,'migrations','.sql'),...await list(root,'contracts/v1','.schema.json'),...await list(root,'contracts/p1a','.schema.json'),'contracts/reason-codes.p1a.json','contracts/reason-codes.v1.json','tests/fixtures/p1a-replay/experiment.json','config/account-profile.unconfigured.v1.json','package.json','package-lock.json'];
 try{await access(path.join(root,'contracts/closure'));old.push(...await list(root,'contracts/closure','.schema.json'),'contracts/reason-codes.closure.json',...await list(root,'tests/fixtures','.json'),...await list(root,'tests/fixtures','.html'));}catch(e){if(e.code!=='ENOENT')throw e;}
 return [...new Set(old)].sort();
}
export async function createCodeProvenance({commit,root=defaultRoot}){
  requireThat(/^[a-f0-9]{40}$/.test(commit),'ACTUAL_CODE_VERSION_REQUIRED');const git=await gitBinary();
  const resolved=(await run(git,['rev-parse',`${commit}^{commit}`],{cwd:root})).stdout.trim();requireThat(resolved===commit,'ACTUAL_CODE_VERSION_REQUIRED');
  const files=await implementationFiles(root),hashes={};
  for(const file of files){const current=await readFile(path.join(root,file));const committed=(await run(git,['show',`${commit}:${file}`],{cwd:root,encoding:'buffer',maxBuffer:4194304})).stdout;requireThat(sha(current)===sha(committed),'IMPLEMENTATION_NOT_COMMITTED');hashes[file]=sha(current);}
  const body={contract_name:'CodeProvenance',contract_version:'1.0.0',code_version:commit,source_tree_hash:hashValue(hashes),files:hashes,scope:'P1A_OFFLINE_IMPLEMENTATION',production_enabled:false};return {...body,content_hash:hashValue(body)};
}
export async function loadCodeProvenance(root=defaultRoot){let file='config/closure/code-provenance.json';try{await access(path.join(root,file));}catch(e){if(e.code!=='ENOENT')throw e;file='config/p1a/code-provenance.json';}return JSON.parse(await readFile(path.join(root,file),'utf8'));}
export async function verifyCodeProvenance({code_version,source_tree_hash,root=defaultRoot}){
  const pinned=await loadCodeProvenance(root);requireThat(pinned.code_version===code_version&&pinned.source_tree_hash===source_tree_hash,'CODE_BINDING_MISMATCH');
  const actual=await createCodeProvenance({commit:code_version,root});requireThat(actual.content_hash===pinned.content_hash,'IMPLEMENTATION_SOURCE_CHANGED');return actual;
}
