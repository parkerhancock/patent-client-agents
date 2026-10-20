import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";

// Packaging is the boundary: installing the client/MCP must not install a browser.
test("browser runtime dependencies are confined to the optional worker", async () => {
  const packages = new Map<string, Record<string, string>>();
  for (const directory of ["client", "mcp", "waf-session", "waf-worker"]) {
    const manifest = JSON.parse(
      await readFile(
        new URL(`../packages/${directory}/package.json`, import.meta.url),
        "utf8",
      ),
    );
    packages.set(manifest.name, {
      ...manifest.dependencies,
      ...manifest.optionalDependencies,
    });
  }
  function dependencies(name: string, seen = new Set<string>()): Set<string> {
    for (const dependency of Object.keys(packages.get(name) ?? {})) {
      if (seen.has(dependency)) continue;
      seen.add(dependency);
      if (packages.has(dependency)) dependencies(dependency, seen);
    }
    return seen;
  }
  for (const name of ["client", "mcp", "waf-session"]) {
    const runtime = dependencies(`@patent-client-agents/${name}`);
    expect(runtime.has("@patent-client-agents/waf-worker")).toBe(false);
    expect([...runtime].some((item) => /playwright|puppeteer/.test(item))).toBe(
      false,
    );
  }
  expect(
    dependencies("@patent-client-agents/waf-worker").has("playwright"),
  ).toBe(true);
});
