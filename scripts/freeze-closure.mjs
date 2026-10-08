// Explicit parent release action; never invoked by check/CI.
import fs from 'node:fs/promises';
import {createCodeProvenance} from '../src/p1a/code-provenance.mjs';
import {sha} from '../src/closure/contracts.mjs';
if(process.argv[2]!=='--reviewed-before-release'||!/^[a-f0-9]{40}$/.test(process.argv[3]??''))throw Error('EXPLICIT_PARENT_REVIEW_AND_COMMIT_REQUIRED');
const root=new URL('../',import.meta.url),code=await createCodeProvenance({commit:process.argv[3]});
await fs.mkdir(new URL('config/closure/',root),{recursive:true});
await fs.writeFile(new URL('config/closure/code-provenance.json',root),JSON.stringify(code,null,2)+'\n');
const paths=[...(await fs.readdir(new URL('contracts/closure/',root))).filter(n=>n.endsWith('.schema.json')).map(n=>'contracts/closure/'+n),'contracts/reason-codes.closure.json','migrations/006_closure_admission.sql','config/closure/code-provenance.json','docs/closure-implementation/W1-freeze.json','docs/closure-implementation/W1-interfaces.md','docs/closure-implementation/W1-clarifications.md','docs/authorizations/P1A-closure-implementation-20261005.md'];
const files=await Promise.all(paths.map(async path=>({path,sha256:sha(await fs.readFile(new URL(path,root)))})));
const release={release_version:'1.2.0',schema_version:6,phase:'P1A_CONDITIONAL_CLOSURE_FIXTURE_ONLY',gate_status:'REQUIRES_CLOSURE_GATE_REVIEW',real_data_admission_gate:'BLOCKED',production_execution_enabled:false,p1b_research_enabled:false,code_version:code.code_version,source_tree_hash:code.source_tree_hash,p0_release_sha256:sha(await fs.readFile(new URL('contracts/release.v1.json',root))),p1a_release_sha256:sha(await fs.readFile(new URL('contracts/release.p1a.json',root))),contracts:{BrainPacket:'1.1.0',AdmissionReceipt:'1.0.0',SourceAdmissionPolicy:'1.0.0',ResearchDraft:'1.0.0'},files};
await fs.writeFile(new URL('contracts/release.closure.json',root),JSON.stringify(release,null,2)+'\n');
console.log(JSON.stringify({code_version:code.code_version,source_tree_hash:code.source_tree_hash,files:Object.keys(code.files).length}));
