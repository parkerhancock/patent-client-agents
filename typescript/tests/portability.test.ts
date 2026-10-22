import { expect, test } from "bun:test";
import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";

const root = join(import.meta.dir, "..", "packages", "client", "src");
/** Server-only modules: the #files adapter and the corpus bootstrap, which the index does not export. */
const serverOnly = new Set(["runtime/files.ts", "corpus/bootstrap.ts"]);

async function sources(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  return (
    await Promise.all(
      entries.map((entry) =>
        entry.isDirectory()
          ? sources(join(directory, entry.name))
          : entry.name.endsWith(".ts")
            ? [join(directory, entry.name)]
            : [],
      ),
    )
  ).flat();
}

test("the client package uses only web-standard APIs outside the server file adapter", async () => {
  const offenders: string[] = [];
  for (const file of await sources(root)) {
    const name = relative(root, file);
    if (serverOnly.has(name)) continue;
    const text = await readFile(file, "utf8");
    for (const [label, pattern] of [
      ["node: import", /from\s+["']node:/],
      ["bun: import", /from\s+["']bun:/],
      ["Bun global", /\bBun\./],
      ["process global", /\bprocess\./],
      ["Buffer global", /\bBuffer\./],
      ["require()", /\brequire\(/],
    ] as const)
      if (pattern.test(text)) offenders.push(`${name}: ${label}`);
  }
  expect(offenders).toEqual([]);
});

test("the browser bundle builds and resolves the browser file adapter", async () => {
  const result = await Bun.build({
    entrypoints: [join(root, "index.ts")],
    target: "browser",
    format: "esm",
  });
  expect(result.logs.filter((log) => log.level === "error")).toEqual([]);
  expect(result.success).toBe(true);
  const code = await result.outputs
    .find((output) => output.kind === "entry-point")
    ?.text();
  expect(code).toBeDefined();
  expect(code).not.toMatch(/from\s*["']node:/);
  expect(code).not.toMatch(/from\s*["']bun:/);
  expect(code).toContain("File paths are unavailable in browsers");
  // The server-only corpus bootstrap stays out of the index.
  expect(code).not.toContain("CorpusBootstrapError");
});
