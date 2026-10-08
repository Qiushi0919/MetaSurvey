import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
execFileSync(process.execPath,[path.join(root,'scripts/verify-contracts.mjs')],{stdio:'inherit'});
const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8')),lock=JSON.parse(fs.readFileSync(path.join(root,'package-lock.json'),'utf8'));
if(lock.packages[''].engines.node!==pkg.engines.node)throw new Error('RUNTIME_LOCK_MISMATCH');
for(const section of ['dependencies','devDependencies'])for(const [name,version] of Object.entries(pkg[section]??{})) {
  if(!/^\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?$/.test(version)||lock.packages[''][section][name]!==version)throw new Error(`DEPENDENCY_NOT_LOCKED:${name}`);
}
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>{
  if(['node_modules','.git','.local','coverage'].includes(e.name))return [];
  const p=path.join(dir,e.name);if(e.isSymbolicLink())throw new Error(`REPO_SYMLINK_REJECTED:${path.relative(root,p)}`);
  return e.isDirectory()?walk(p):[p];
});}
for(const file of walk(root)) {
  const rel=path.relative(root,file),base=path.basename(file);
  if(/(?:^|\/)(?:credentials[^/]*|secrets[^/]*|state|runs)(?:\/|$)|\.(?:db|sqlite|parquet|pdf|zip|xlsx|pem|key)(?:-|$)/i.test(rel)||(base.startsWith('.env')&&base!=='.env.example'))throw new Error(`FORBIDDEN_REPO_ASSET:${rel}`);
  if(fs.statSync(file).size>1024*1024)throw new Error(`LARGE_REPO_FILE_REJECTED:${rel}`);
  const text=fs.readFileSync(file,'utf8');
  if(/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9]{30,}\b/.test(text))throw new Error(`CREDENTIAL_PATTERN_REJECTED:${rel}`);
}
const manifest=JSON.parse(fs.readFileSync(path.join(root,'legacy/asset-manifest.v1.json'),'utf8'));
if(!manifest)throw new Error('LEGACY_MANIFEST_MISSING');
console.log('Local P0 preflight passed: dependency lock, small source assets, credential/state exclusion.');
