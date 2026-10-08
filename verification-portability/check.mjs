import path from 'node:path';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const root = path.resolve(import.meta.dirname, '..');
const bundledPython = path.resolve(process.execPath, '../../../python/bin/python3');
const python = process.env.TUSHARE_DIAGNOSTIC_PYTHON || bundledPython;
const run = (bin, args) => {
  const result = spawnSync(bin, args, {cwd: root, stdio: 'inherit', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}});
  if (result.status !== 0) process.exit(result.status ?? 1);
};
if (process.argv.slice(2).some(a => a !== '--new-only') || process.argv.length > 3) {
  console.error('VERIFICATION_ARGUMENT_INVALID'); process.exit(1);
}
// --new-only selects this epoch's compatibility/security suite for development.
// The default entry also runs every frozen baseline and current probe check.
if (!process.argv.includes('--new-only')) run(process.execPath, ['real-slice/scripts/check.mjs']);
run(process.execPath, ['verification-portability/verify.mjs']);
run(process.execPath, ['--test', '--test-concurrency=1', ...fs.readdirSync(path.join(root, 'verification-portability/tests')).filter(p => p.endsWith('.test.mjs')).map(p => 'verification-portability/tests/' + p)]);
if (!process.argv.includes('--new-only')) {
  run(python, ['-B', '-m', 'unittest', 'discover', '-s', 'tushare-admission/tests', '-v']);
  run(process.execPath, ['tushare-real-admission/check.mjs', '--new-only']);
}
console.log('Offline read-only checkout verification complete; no data admission or execution permission.');
