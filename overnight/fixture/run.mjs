import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {canonical} from '../../src/contracts/validate.mjs';
import {runFixtureSuite} from './chain.mjs';
const root='/Users/qiushi/投资研究/.p1b-archives/overnight-20261005/fixture';
const args=process.argv.slice(2);
if(args.length!==2||args[0]!=='--run-id'||!/^[A-Za-z0-9][A-Za-z0-9_-]{1,90}$/.test(args[1])){
 console.error('OVERNIGHT_ARGUMENT_INVALID');process.exit(1);
}
try{
 const directory=path.join(root,args[1]);
 await fs.mkdir(root,{recursive:true,mode:0o700});
 if(await fs.realpath(root)!==root)throw new Error('OVERNIGHT_OUTPUT_PATH_INVALID');
 await fs.mkdir(directory,{mode:0o700});
 const result=await runFixtureSuite(directory),inventory=[];
 for(const [name,value] of [['fixture-proof.json',result.proof],['fixture-artifacts.json',result.artifacts]]){
  const raw=Buffer.from(canonical(value)+'\n'),handle=await fs.open(path.join(directory,name),constants.O_CREAT|constants.O_EXCL|constants.O_WRONLY|constants.O_NOFOLLOW,0o600);
  try{await handle.writeFile(raw);}finally{await handle.close();}
  inventory.push({object:name,bytes:raw.length,sha256:'sha256:'+createHash('sha256').update(raw).digest('hex')});
 }
 const index={version:'1.0.0-diagnostic',fixture:true,source_admission:'BLOCKED',productionGate:false,artifacts:inventory};
 await fs.writeFile(path.join(directory,'artifact-index.json'),canonical(index)+'\n',{flag:'wx',mode:0o600});
 console.log('SYNTHETIC_CHAIN_SUITE_COMPLETE real_cards=0 model_calls=0 execution_writes=0');
}catch{
 console.error('OVERNIGHT_FIXTURE_FAILED_NO_PERMISSION');process.exit(1);
}
