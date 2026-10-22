import sqlite3InitModule from "@sqlite.org/sqlite-wasm";
import { wasmLocations } from "./wasm.js";

type Sqlite = Awaited<ReturnType<typeof sqlite3InitModule>>;
let module: Promise<Sqlite> | undefined;
type Bind = (string | number | Uint8Array | null)[];

/** A read-only in-memory SQLite database built from verified bytes. */
export interface SnapshotDatabase {
  all<T>(sql: string, bind?: Bind): T[];
  get<T>(sql: string, bind?: Bind): T | undefined;
  close(): void;
}

function sqliteModule(): Promise<Sqlite> {
  module ??= (() => {
    const { sqlite } = wasmLocations();
    // Emscripten module options: an explicit binary or file location.
    const options =
      sqlite instanceof Uint8Array
        ? { wasmBinary: sqlite }
        : sqlite
          ? { locateFile: () => String(sqlite) }
          : {};
    return (
      sqlite3InitModule as unknown as (options: object) => Promise<Sqlite>
    )(options);
  })();
  return module;
}

/**
 * Open bytes as a read-only database with the official SQLite WebAssembly
 * build (FTS5 included). Deserializing the hashed bytes, rather than opening
 * a path, rules out WAL replay and file-replacement races in every runtime.
 */
export async function openSnapshot(
  bytes: Uint8Array,
): Promise<SnapshotDatabase> {
  const sqlite3 = await sqliteModule();
  const { capi, wasm, oo1 } = sqlite3;
  const db = new oo1.DB(":memory:", "c");
  try {
    const pointer = wasm.allocFromTypedArray(bytes);
    const rc = capi.sqlite3_deserialize(
      db,
      "main",
      pointer,
      bytes.byteLength,
      bytes.byteLength,
      capi.SQLITE_DESERIALIZE_FREEONCLOSE | capi.SQLITE_DESERIALIZE_READONLY,
    );
    if (rc !== 0) throw new Error(`sqlite3_deserialize failed with ${rc}.`);
    db.exec("PRAGMA query_only = ON");
  } catch (error) {
    db.close();
    throw error;
  }
  return {
    all: <T>(sql: string, bind: Bind = []) =>
      db.selectObjects(sql, bind) as T[],
    get: <T>(sql: string, bind: Bind = []) =>
      (db.selectObjects(sql, bind)[0] as T | undefined) ?? undefined,
    close: () => db.close(),
  };
}

/**
 * Build a small in-memory database from bundled data (schema and rows), then
 * make it read-only. For corpora shipped inside the package instead of as an
 * artifact file.
 */
export async function openBuiltDatabase(
  statements: { sql: string; bind?: Bind }[],
): Promise<SnapshotDatabase> {
  const { oo1 } = await sqliteModule();
  const db = new oo1.DB(":memory:", "c");
  try {
    for (const statement of statements)
      db.exec(
        statement.bind
          ? { sql: statement.sql, bind: statement.bind }
          : { sql: statement.sql },
      );
    db.exec("PRAGMA query_only = ON");
  } catch (error) {
    db.close();
    throw error;
  }
  return {
    all: <T>(sql: string, bind: Bind = []) =>
      db.selectObjects(sql, bind) as T[],
    get: <T>(sql: string, bind: Bind = []) =>
      (db.selectObjects(sql, bind)[0] as T | undefined) ?? undefined,
    close: () => db.close(),
  };
}
