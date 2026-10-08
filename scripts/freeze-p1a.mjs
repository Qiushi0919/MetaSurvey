// Parent-only, explicit pre-release review action. Never run from CI or check.
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createCodeProvenance} from '../src/p1a/code-provenance.mjs';
if(process.argv[2]!=='--reviewed-before-release'||!/^[a-f0-9]{40}$/.test(process.argv[3]??''))throw new Error('EXPLICIT_PARENT_REVIEW_AND_COMMIT_REQUIRED');
const sha=b=>`sha256:${createHash('sha256').update(b).digest('hex')}`;
const code=await createCodeProvenance({commit:process.argv[3]});await writeFile(new URL('../config/p1a/code-provenance.json',import.meta.url),JSON.stringify(code,null,2)+'\n');
const directory=new URL('../contracts/p1a/',import.meta.url),names=(await readdir(directory)).filter(n=>n.endsWith('.schema.json')).sort();
const paths=[...names.map(n=>'contracts/p1a/'+n),'contracts/reason-codes.p1a.json',...(await readdir(new URL('../migrations/',import.meta.url))).filter(n=>n.endsWith('.sql')).map(n=>'migrations/'+n),'config/p1a/code-provenance.json'];
const files=await Promise.all(paths.map(async path=>({path,sha256:sha(await readFile(new URL('../'+path,import.meta.url)))})));
const release={release_version:'1.1.0',module_contract_version:'1.0.0',schema_version:5,phase:'P1A_OFFLINE_ONLY',gate_status:'REQUIRES_P1A_GATE_REVIEW',production_execution_enabled:false,p1b_research_enabled:false,p0_release_sha256:sha(await readFile(new URL('../contracts/release.v1.json',import.meta.url))),code_version:code.code_version,source_tree_hash:code.source_tree_hash,contracts:names.map(n=>n.replace('.schema.json','')),files};
await writeFile(new URL('../contracts/release.p1a.json',import.meta.url),JSON.stringify(release,null,2)+'\n');console.log(JSON.stringify({code_version:code.code_version,source_tree_hash:code.source_tree_hash,contracts:names.length,migrations:5}));
