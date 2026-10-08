// Standalone consumer bootstrap. The parent copies only this file, the sanitized
// signed artifact and its pinned PUBLIC key into an isolated staging directory.
import fs from 'node:fs';
import {createHash,createPublicKey,verify} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import net from 'node:net';
import {spawnSync} from 'node:child_process';

function check(ok,code){if(!ok)throw new Error(code);}
function canonical(v){if(v===null||['boolean','string'].includes(typeof v))return JSON.stringify(v);if(typeof v==='number'){check(Number.isSafeInteger(v),'CLOSURE_IMPORT_INVALID');return JSON.stringify(v);}if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';check(v&&Object.getPrototypeOf(v)===Object.prototype,'CLOSURE_IMPORT_INVALID');return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';}
const sha=b=>'sha256:'+createHash('sha256').update(b).digest('hex');
const ref=o=>({object_id:o.object_id,object_version:o.object_version,content_hash:o.content_hash});
function hashObject(o){const{content_hash,proof,...body}=o;return sha(canonical(body));}
function signature(o,key){check(o.content_hash===hashObject(o),'CLOSURE_HASH_MISMATCH');check(o.issuer?.public_key_hash===sha(key)&&o.proof?.algorithm==='ED25519'&&verify(null,Buffer.from(o.content_hash),createPublicKey({key,format:'der',type:'spki'}),Buffer.from(o.proof.signature,'base64')),'CLOSURE_SIGNATURE_INVALID');}

export function verifyExportArtifact(packet,trustedPublicKeyDer){
 check(packet?.contract_name==='BrainPacket'&&packet.contract_version==='1.1.0'&&packet.transfer_mode==='MANUAL_EXPORT'&&packet.fixture_scope==='SYNTHETIC_TEST_ONLY'&&packet.purpose==='FIXTURE_MANUAL_EXPORT'&&['DEV','PAPER'].includes(packet.mode)&&packet.production_enabled===false&&packet.can_produce_order===false&&packet.contains_account_identity_or_credentials===false,'CLOSURE_IMPORT_INVALID');
 signature(packet,trustedPublicKeyDer);signature(packet.receipt,trustedPublicKeyDer);
 check(packet.receipt.contract_name==='AdmissionReceipt'&&packet.receipt.contract_version==='1.0.0'&&packet.receipt.verification==='VERIFIED'&&packet.receipt.admission==='ADMITTED'&&packet.receipt.fixture_scope===packet.fixture_scope&&packet.receipt.purpose===packet.purpose&&packet.receipt.strategy_id===packet.strategy_id&&packet.receipt.production_enabled===false,'CLOSURE_RECEIPT_INVALIDATED');
 for(const k of ['snapshot_ref','data_hash','decision_cutoff','feature_version','rules_hash'])check(canonical(packet[k])===canonical(packet.receipt[k]),'CLOSURE_RECEIPT_INVALIDATED');
 const projected=Object.fromEntries(['snapshot_ref','data_hash','decision_cutoff','feature_version','rules_hash','evidence'].map(k=>[k,packet[k]]));check(sha(canonical(projected))===packet.projection_hash,'CLOSURE_HASH_MISMATCH');
 check(Array.isArray(packet.evidence)&&packet.evidence.length>0,'CLOSURE_IMPORT_INVALID');
 for(const e of packet.evidence){const{content_hash,...body}=e;check(sha(canonical(body))===content_hash&&sha(canonical(e.payload))===e.payload_hash&&e.data_quality==='PASS'&&e.data_kind==='BAR_1D'&&e.invalidation.status==='ACTIVE'&&e.provenance.visibility_basis==='SYNTHETIC'&&Date.parse(e.provenance.available_at)<=Date.parse(packet.decision_cutoff),'CLOSURE_IMPORT_INVALID');}
 return packet;
}

async function probe(probes,protectedArtifact){
 const reads=(probes.read_paths??[]).map((p,i)=>{try{fs.readFileSync(p);return {index:i,denied:false};}catch(e){return {index:i,denied:['EACCES','EPERM','ERR_ACCESS_DENIED'].includes(e.code)};}});
 let network=null;
 if(probes.network)network=await new Promise(resolve=>{let done=false;const finish=(denied)=>{if(done)return;done=true;socket?.destroy();resolve({denied});};let socket;try{socket=net.connect({host:'127.0.0.1',port:probes.network_port??9});socket.on('connect',()=>finish(false));socket.on('error',e=>finish(['EACCES','EPERM','ERR_ACCESS_DENIED'].includes(e.code)));socket.setTimeout(500,()=>finish(false));}catch(e){finish(['EACCES','EPERM','ERR_ACCESS_DENIED'].includes(e.code));}});
 const execution=probes.exec?['/bin/sh',process.execPath].map((command,index)=>{try{const r=spawnSync(command,index===0?['-c','exit 0']:['-e','process.exit(0)'],{timeout:500,env:{}});return {index,denied:['EACCES','EPERM','ERR_ACCESS_DENIED'].includes(r.error?.code)};}catch(e){return {index,denied:['EACCES','EPERM','ERR_ACCESS_DENIED'].includes(e.code)};}}):[];
 const capability=probes.capability_discovery?{environment_keys:Object.keys(process.env).sort(),global_db_present:Object.hasOwn(globalThis,'db'),global_broker_present:Object.hasOwn(globalThis,'broker'),regular_file_descriptor_count:Array.from({length:64},(_,fd)=>{try{return fs.fstatSync(fd).isFile()?1:0;}catch{return 0;}}).reduce((a,b)=>a+b,0)}:null;
 let write=null;if(Object.keys(probes).length){try{fs.writeFileSync(protectedArtifact,'UNAUTHORIZED_SYNTHETIC_MUTATION');write={denied:false};}catch(e){write={denied:['EACCES','EPERM','ERR_ACCESS_DENIED'].includes(e.code)};}}
 return {reads,network,execution,capability,write};
}

export async function consumerMain(artifactPath,keyPath,probesPath){
 const packet=verifyExportArtifact(JSON.parse(fs.readFileSync(artifactPath,'utf8')),fs.readFileSync(keyPath));
 const result={packet_ref:ref(packet),receipt_ref:ref(packet.receipt),strategy_id:packet.strategy_id,purpose:packet.purpose,observations:packet.evidence.map(e=>({evidence_ref:ref(e),statement:'Synthetic bar evidence is present at the admitted cutoff.',classification:'DESCRIPTIVE_ONLY'}))};
 return {result,probes:await probe(probesPath?JSON.parse(fs.readFileSync(probesPath,'utf8')):{},artifactPath),execution_writes:0,broker_transport_calls:0};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){try{process.stdout.write(canonical(await consumerMain(process.argv[2],process.argv[3],process.argv[4])));}catch(e){process.stderr.write(e.message+'\n');process.exitCode=1;}}
