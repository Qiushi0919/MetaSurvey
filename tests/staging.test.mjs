import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';
import {migrate,defaultMigrationDirectory} from '../src/baseline/migrate.mjs';
import {stageContractFixture,readContractFixture,legacyEvidenceEnvelope} from '../src/baseline/staging.mjs';
import {base,examples,H,envelope} from './helpers.mjs';
import {sealContract,hashValue} from '../src/contracts/validate.mjs';

test('Empty -> latest includes lossless v1 contract registry; all sixteen synthetic contracts roundtrip',async()=>{
  const db=new PGlite();try {
    const result=await migrate(db);assert.equal(result.schemaVersion,fs.readdirSync(defaultMigrationDirectory).filter(n=>/^\d{3}_[a-z0-9_]+\.sql$/.test(n)).length);
    for (const [name,object] of Object.entries(examples().all)) {
      const imported=await stageContractFixture(db,object,{fixtureKind:'SYNTHETIC'});
      assert.equal(imported.normalized_tables_written,false);
      assert.deepEqual(await readContractFixture(db,name,object.object_id,object.object_version),object);
    }
    for (const name of ['orders_sim','orders_real','fills_sim','fills_real','ledger_sim','ledger_real']) assert.equal((await db.query(`SELECT count(*)::int AS n FROM ${name}`)).rows[0].n,0);
    const object=examples().all.DataEnvelope;
    await assert.rejects(stageContractFixture(db,object,{fixtureKind:'SYNTHETIC'}),/duplicate key/);
    await assert.rejects(db.query('DELETE FROM contract_records'),/APPEND_ONLY_HISTORY/);
  } finally {await db.close();}
});
test('Minimal legacy import stays quarantined, retains original payload/hash and has no strategy mapping',async()=>{
  const db=new PGlite();try {
    await migrate(db);const legacyBase=base('DataEnvelope');legacyBase.provenance.source_id='legacy:fixture';
    const bytes=fs.readFileSync(new URL('./fixtures/legacy/v5-fourteen-days.v1.json',import.meta.url));
    const payload=JSON.parse(bytes),sourceHash=`sha256:${createHash('sha256').update(bytes).digest('hex')}`;
    const object=legacyEvidenceEnvelope({base:legacyBase,assetId:'legacy-v5-fixture',sourceHash,locator:'repo-fixture:tests/fixtures/legacy/v5-fourteen-days.v1.json',payload});
    const result=await stageContractFixture(db,object,{fixtureKind:'LEGACY'});assert.equal(result.status,'QUARANTINED');
    const stored=await readContractFixture(db,'DataEnvelope',object.object_id,1);
    assert.deepEqual(stored.payload,payload);assert.equal(stored.payload_hash,hashValue(payload));assert.equal(stored.raw_hash,sourceHash);assert.equal('strategy_id' in stored,false);
    assert.equal((await db.query('SELECT ingestion_status FROM contract_records')).rows[0].ingestion_status,'QUARANTINED');
  } finally {await db.close();}
});
test('Staging rejects production, unknown fixture label, tampered data and sensitive fixture fields before writing',async()=>{
  let writes=0;const db={query(){writes++;throw new Error('unreachable');}};
  await assert.rejects(stageContractFixture(db,sealContract({...examples().all.AccountProfile,mode:'PROD'}),{fixtureKind:'SYNTHETIC'}),{code:'PRODUCTION_DISABLED_P0'});
  await assert.rejects(stageContractFixture(db,examples().all.DataEnvelope,{fixtureKind:'SOURCE_SAMPLE'}),{code:'FIXTURE_KIND_REQUIRED'});
  await assert.rejects(stageContractFixture(db,{...examples().all.DataEnvelope,trace_id:'tampered'},{fixtureKind:'SYNTHETIC'}),{code:'HASH_MISMATCH'});
  const e=examples().all.DataEnvelope,payload={api_key:'synthetic-sensitive-value'};
  await assert.rejects(stageContractFixture(db,sealContract({...e,payload,payload_hash:hashValue(payload)}),{fixtureKind:'SYNTHETIC'}),{code:'SENSITIVE_FIXTURE_REJECTED'});
  assert.equal(writes,0);
});
test('DATE_ONLY packet fixture reads require the same explicit calendar context as writes',async()=>{
  const db=new PGlite();try {
    await migrate(db);const calendar=['2026-10-05','2026-10-08'];
    const e=envelope(),at='2026-10-08T01:00:00Z';
    const evidence=sealContract({...e,recorded_at:at,provenance:{...e.provenance,published_at:'2026-10-05',publication_precision:'DATE_ONLY',available_at:at,retrieved_at:at}});
    const packet=sealContract({...examples().all.BrainPacket,decision_cutoff:at,evidence:[evidence]});
    await stageContractFixture(db,packet,{fixtureKind:'SYNTHETIC',calendar});
    await assert.rejects(readContractFixture(db,'BrainPacket',packet.object_id,1),{code:'UNKNOWN_PUBLICATION'});
    assert.deepEqual(await readContractFixture(db,'BrainPacket',packet.object_id,1,{calendar}),packet);
  } finally {await db.close();}
});
