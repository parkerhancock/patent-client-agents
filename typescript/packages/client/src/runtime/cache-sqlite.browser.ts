import type { SqlDatabase } from "../cache/sqlite.js";

/** Browsers have no cache directory or SQLite file storage. */
export function defaultCacheDirectory(): string | undefined {
  return undefined;
}
export function cacheFilePath(directory: string, name: string): string {
  return `${directory}/${name}.db`;
}
export async function openSqlite(
  _path: string,
): Promise<SqlDatabase | undefined> {
  return undefined;
}
