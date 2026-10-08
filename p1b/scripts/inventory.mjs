import fs from 'node:fs';
import {buildSourceInventory} from '../src/inventory.mjs';
const inventory=await buildSourceInventory();
const output=new URL('../../docs/p1b/source-inventory.json',import.meta.url);
fs.writeFileSync(output,JSON.stringify(inventory,null,2)+'\n');
console.log(JSON.stringify({source_count:inventory.sources.length,database_opened:inventory.database.opened,legacy_fingerprints_unchanged:inventory.database.fingerprints_unchanged,raw_payloads_exported:false}));
