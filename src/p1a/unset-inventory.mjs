import fs from 'node:fs';
import {unsetPaths} from '../baseline/gates.mjs';
const schema=JSON.parse(fs.readFileSync(new URL('../../contracts/v1/AccountProfile.schema.json',import.meta.url),'utf8'));
const common=JSON.parse(fs.readFileSync(new URL('../../contracts/v1/common.schema.json',import.meta.url),'utf8'));
function resolve(node) {
  if(node.$ref?.startsWith('urn:ashare:contracts:v1:common#/$defs/'))return resolve(common.$defs[node.$ref.split('/').at(-1)]);
  if(node.anyOf)return node.anyOf.find(x=>x.const!=='UNSET_REQUIRED'&&x.type!=='null')??node;
  return node;
}
export function accountRequiredFields() {
  const result=[];
  function walk(node,pointer='') {
    node=resolve(node);
    if(node.type==='object')for(const key of node.required??[])walk(node.properties[key],`${pointer}/${key}`);
    else result.push({pointer,schema:node,required:true});
  }
  walk(schema);return result;
}
export function unsetInventory(profile) {
  const fields=new Map(accountRequiredFields().map(x=>[x.pointer,x]));
  return {inventory_version:'1.0.0',account_contract_version:'1.0.0',production_execution:'BLOCKED',fields:unsetPaths(profile).map(pointer=>({pointer,required:fields.has(pointer),schema:fields.get(pointer)?.schema??null,status:'UNSET_REQUIRED',blocks:['REAL_SIZING','REAL_ACCOUNT_RISK','REAL_BROKER_EXECUTION','PRODUCTION'],offline_engineering_blocked:false}))};
}
