// Verification only. Actual private signing keys are never accepted here.
import { createPublicKey, verify } from 'node:crypto';
let input='';for await(const chunk of process.stdin){input+=chunk;if(input.length>1_000_000)process.exit(2);}
try{
 const x=JSON.parse(input);
 if(Object.keys(x).sort().join(',')!=='message,public_der,signature'||
    !/^[a-f0-9]{88}$/.test(x.public_der)||!/^[a-f0-9]{128}$/.test(x.signature)||
    typeof x.message!=='string')throw Error('shape');
 const key=createPublicKey({key:Buffer.from(x.public_der,'hex'),type:'spki',format:'der'});
 if(key.asymmetricKeyType!=='ed25519')throw Error('algorithm');
 process.stdout.write(verify(null,Buffer.from(x.message,'base64'),key,Buffer.from(x.signature,'hex'))?'PASS':'REJECT');
}catch{process.stdout.write('REJECT');}
