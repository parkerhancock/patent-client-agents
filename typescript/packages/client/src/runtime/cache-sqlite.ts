import { mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import type { SqlDatabase } from "../cache/sqlite.js";

/** Server runtimes: Python's default cache directory, `~/.cache/patent_client_agents`. */
export function defaultCacheDirectory(): string | undefined {
  return join(homedir(), ".cache", "patent_client_agents");
}
export function cacheFilePath(directory: string, name: string): string {
  return join(directory, `${name}.db`);
}

// Variables keep bundlers and the type checker from resolving runtime-only modules.
const BUN_SQLITE = "bun:sqlite";
const NODE_SQLITE = "node:sqlite";

/**
 * Open a SQLite file with `bun:sqlite` under Bun or `node:sqlite` under Node
 * (22.5 and later). Returns undefined where neither exists, and the caller
 * falls back to memory.
 */
export async function openSqlite(
  path: string,
): Promise<SqlDatabase | undefined> {
  await mkdir(dirname(path), { recursive: true });
  if ("Bun" in globalThis) {
    const { Database } = await import(BUN_SQLITE);
    return new Database(path, { create: true }) as SqlDatabase;
  }
  let module: { DatabaseSync: new (path: string) => SqlDatabase };
  try {
    module = await import(NODE_SQLITE);
  } catch {
    return undefined;
  }
  return new module.DatabaseSync(path);
}
