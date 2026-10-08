import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export const defaultMigrationDirectory = fileURLToPath(new URL('../../migrations/', import.meta.url));

/** Adapter contract: exec(sql) and query(sql, positionalParams) on one connection. */
export async function migrate(db, { directory = defaultMigrationDirectory } = {}) {
  const sqlFiles = (await readdir(directory)).filter(n => n.endsWith('.sql'));
  if (sqlFiles.some(n => !/^\d{3}_[a-z0-9_]+\.sql$/.test(n))) throw new Error('MIGRATION_FILENAME_INVALID');
  const names = sqlFiles.sort();
  if (!names.length) throw new Error('MIGRATIONS_EMPTY');
  const migrations = await Promise.all(names.map(async name => {
    const bytes = await readFile(path.join(directory, name));
    return { name, number: Number(name.slice(0, 3)), sql: bytes.toString('utf8'), hash: `sha256:${createHash('sha256').update(bytes).digest('hex')}` };
  }));
  migrations.forEach((m, i) => { if (m.number !== i + 1) throw new Error('MIGRATION_SEQUENCE_GAP'); });
  // DDL and application are one transaction. A failed empty build leaves no tracking table.
  await db.exec('BEGIN');
  try {
    await db.exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
      number INTEGER PRIMARY KEY CHECK (number > 0),
      name TEXT UNIQUE NOT NULL,
      checksum TEXT NOT NULL CHECK (checksum ~ '^sha256:[a-f0-9]{64}$'),
      applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`);
    const { rows } = await db.query('SELECT number, name, checksum FROM schema_migrations ORDER BY number');
    for (let i = 0; i < rows.length; i++) {
      const old = rows[i], current = migrations[i];
      if (!current || old.number !== current.number || old.name !== current.name || old.checksum !== current.hash) {
        throw new Error(`MIGRATION_CHECKSUM_OR_HISTORY_MISMATCH:${old.name}`);
      }
    }
    const applied = [];
    for (const migration of migrations.slice(rows.length)) {
      await db.exec(migration.sql);
      await db.query('INSERT INTO schema_migrations(number,name,checksum) VALUES ($1,$2,$3)', [migration.number, migration.name, migration.hash]);
      applied.push(migration.name);
    }
    await db.exec('COMMIT');
    return { schemaVersion: migrations.at(-1).number, applied, verified: rows.map(r => r.name) };
  } catch (error) {
    await db.exec('ROLLBACK');
    throw error;
  }
}
