/**
 * Where the SQLite and zstd WebAssembly binaries load from. By default each
 * library resolves its .wasm file next to its module with
 * `new URL(..., import.meta.url)`, which server runtimes and bundlers that
 * copy such assets handle. Otherwise serve the files yourself and call this
 * before the first corpus or zstd use.
 */
export interface WasmLocations {
  /** URL of sqlite3.wasm, or its bytes. */
  sqlite?: string | URL | Uint8Array;
  /** URL of zstd.wasm. */
  zstd?: string | URL;
}
let locations: WasmLocations = {};
let started = false;
export function configureWasm(next: WasmLocations): void {
  if (started)
    throw new Error(
      "configureWasm must be called before WebAssembly modules load.",
    );
  locations = { ...locations, ...next };
}
export function wasmLocations(): WasmLocations {
  started = true;
  return locations;
}
