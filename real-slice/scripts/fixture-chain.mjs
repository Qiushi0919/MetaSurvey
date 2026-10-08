import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {canonical} from '../../src/contracts/validate.mjs';
import {runFixtureChain,verifyFixtureChain,compareFixtureChains} from '../src/fixture-chain.mjs';

// Optional explicit artifact directory is local engineering output only.
const directory=process.argv[2]?path.resolve(process.argv[2]):await fs.mkdtemp(path.join(os.tmpdir(),'ashare-fixture-chain-replay-'));
const first=await runFixtureChain({directory}),second=await runFixtureChain({directory});
if(first.replay_hash!==second.replay_hash||canonical(first.chain)!==canonical(second.chain))throw new Error('SLICE_REF_INVALIDATED');
verifyFixtureChain(second.chain,second);
const report={run_id:'SYNTHETIC_FIXTURE_RESEARCH_CHAIN_1',scope:'SYNTHETIC_TEST_ONLY',fixture_E2E:'PASS',deterministic_replay:'PASS',replay_hash:first.replay_hash,comparison:compareFixtureChains(first.chain,second.chain),first,second,actual_model_calls:0,real_stock_research_gate:'BLOCKED',production_enabled:false,authority_lifetime:'IN_PROCESS_FIXTURE_COMPOSITION_ONLY_NO_RESTART_ADMISSION'};
await fs.writeFile(path.join(directory,'fixture-chain-results.json'),canonical(report)+'\n',{mode:0o600});
process.stdout.write(JSON.stringify({fixture_E2E:report.fixture_E2E,deterministic_replay:report.deterministic_replay,replay_hash:report.replay_hash,execution_writes:first.execution_writes,actual_model_calls:0,production_enabled:false})+'\n');
