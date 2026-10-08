import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {canonical,requireThat} from '../contracts/validate.mjs';
import {closureRef,sha} from './contracts.mjs';

export async function isolationAvailable(){if(process.platform!=='darwin')return false;try{await fs.access('/usr/bin/sandbox-exec',constants.X_OK);return true;}catch{return false;}}
const literal=p=>'(literal '+JSON.stringify(p)+')';
function profile(stage,node,files){
 const ancestors=new Set();for(const p of [stage,node,...files]){let d=path.dirname(p);while(d!=='/'){ancestors.add(d);d=path.dirname(d);}}ancestors.add('/');
 return '(version 1)\n(deny default)\n(allow process-exec '+literal(node)+')\n(allow sysctl-read)\n(allow file-read-metadata '+[...ancestors].map(literal).join(' ')+')\n(allow file-read* '+['/',node,stage,...files,'/dev/null','/dev/random','/dev/urandom'].map(literal).join(' ')+' (subpath "/System/Library") (subpath "/usr/lib"))\n';
}
function run(command,args,options){return new Promise((resolve,reject)=>{const child=spawn(command,args,options);let stdout='',stderr='';const timer=setTimeout(()=>{child.kill('SIGKILL');reject(new Error('CLOSURE_CONSUMER_ACCESS_DENIED'));},7000);child.on('error',e=>{clearTimeout(timer);reject(e);});child.stdout.on('data',b=>{stdout+=b;if(stdout.length>262144)child.kill('SIGKILL');});child.stderr.on('data',b=>{stderr+=b;if(stderr.length>262144)child.kill('SIGKILL');});child.on('close',(code,signal)=>{clearTimeout(timer);resolve({code,signal,stdout,stderr});});});}

// The caller cannot supply bootstrap code, a sandbox profile, environment,
// allowed directories or commands. Probe paths are attack targets, never grants.
export async function runIsolatedConsumer({service,packet,snapshot,export_path,now,probeOptions={}}){
 packet=structuredClone(packet);snapshot=structuredClone(snapshot);probeOptions=structuredClone(probeOptions);
 requireThat(await isolationAvailable(),'CLOSURE_ISOLATION_UNAVAILABLE');
 requireThat(probeOptions&&Object.keys(probeOptions).every(k=>['read_paths','network','network_port','exec','capability_discovery'].includes(k)),'CLOSURE_IMPORT_INVALID');
 requireThat(!probeOptions.read_paths||(Array.isArray(probeOptions.read_paths)&&probeOptions.read_paths.length<=16&&probeOptions.read_paths.every(p=>typeof p==='string'&&path.isAbsolute(p))),'CLOSURE_IMPORT_INVALID');
 requireThat(probeOptions.network_port===undefined||(Number.isInteger(probeOptions.network_port)&&probeOptions.network_port>0&&probeOptions.network_port<=65535),'CLOSURE_IMPORT_INVALID');
 const chain_id='closure-consumer:'+packet.content_hash.slice(7);
 await service.verifyPacket({packet,snapshot,purpose:'FIXTURE_MANUAL_EXPORT',strategy_id:packet.strategy_id,now});
 let stage;
 try{
  const handle=await fs.open(export_path,constants.O_RDONLY|constants.O_NOFOLLOW);let bytes;
  try{const st=await handle.stat();requireThat(st.isFile()&&st.size<=1048576,'CLOSURE_IMPORT_INVALID');bytes=await handle.readFile();}finally{await handle.close();}
  requireThat(canonical(JSON.parse(bytes.toString('utf8')))===canonical(packet),'CLOSURE_HASH_MISMATCH');
  stage=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'ashare-closure-consumer-')));await fs.chmod(stage,0o700);
  const artifact=path.join(stage,'export.json'),key=path.join(stage,'trusted-public.der'),bootstrap=path.join(stage,'consumer.mjs'),probes=path.join(stage,'probes.json');
  await fs.writeFile(artifact,bytes,{mode:0o400});await fs.writeFile(key,service.trustPublicKeyDer(),{mode:0o400});await fs.copyFile(new URL('./consumer.mjs',import.meta.url),bootstrap);await fs.chmod(bootstrap,0o400);await fs.writeFile(probes,canonical(probeOptions),{mode:0o400});
  const node=await fs.realpath(process.execPath),sandbox=profile(stage,node,[artifact,key,bootstrap,probes]);
  const out=await run('/usr/bin/sandbox-exec',['-p',sandbox,node,'--permission','--allow-fs-read='+stage,bootstrap,artifact,key,probes],{cwd:stage,env:{TZ:'UTC'},stdio:['ignore','pipe','pipe']});
  requireThat(out.code===0,'CLOSURE_CONSUMER_ACCESS_DENIED');
  const response=JSON.parse(out.stdout);
  requireThat(response.execution_writes===0&&response.broker_transport_calls===0,'CLOSURE_LLM_EXECUTION_INJECTION');
  // Fixed self-test repeats attack probes under the identical native profile,
  // without Node's permission defense, so OS evidence cannot be a false positive.
  let native_os_probes=null;
  if(Object.keys(probeOptions).length){const native=await run('/usr/bin/sandbox-exec',['-p',sandbox,node,bootstrap,artifact,key,probes],{cwd:stage,env:{TZ:'UTC'},stdio:['ignore','pipe','pipe']});requireThat(native.code===0,'CLOSURE_CONSUMER_ACCESS_DENIED');native_os_probes=JSON.parse(native.stdout).probes;}
  await service.verifyPacket({packet,snapshot,purpose:'FIXTURE_MANUAL_EXPORT',strategy_id:packet.strategy_id,now});
  await service.audit({chain_id,event_type:'CONSUMER_ACCEPTED',event_time:now,refs:[closureRef(packet),closureRef(packet.receipt)],reason_codes:[]});
  return {...response,native_os_probes,isolation:{mechanism:'MACOS_SANDBOX_EXEC_AND_NODE_PERMISSION',deny_default:true,raw_db_credentials_access:false,network_allowed:false,process_spawn_allowed:false,artifact_byte_hash:sha(bytes)}};
 }catch(error){await service.audit({chain_id,event_type:'CONSUMER_REJECTED',event_time:now,refs:[closureRef(packet)],reason_codes:[error.code?.startsWith('CLOSURE_')?error.code:'CLOSURE_CONSUMER_ACCESS_DENIED']}).catch(()=>{});throw error;}
 finally{if(stage)await fs.rm(stage,{recursive:true,force:true});}
}
