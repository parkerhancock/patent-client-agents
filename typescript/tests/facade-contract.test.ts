import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { UNPORTED_FACADE_TOOLS } from "../packages/mcp/src/facade/index.js";
import { createServer, toolsetFromEnv } from "../packages/mcp/src/index.js";

/**
 * The deployed Python facade (exported from patent-client-facade with
 * USITC_EDIS_TOKEN unset) is the contract: same tool names, parameter names,
 * required parameters and routing enums, so prompts and agents written for
 * the hosted servers keep working.
 */
type JsonSchema = {
  properties?: Record<string, JsonSchema>;
  required?: string[];
  enum?: unknown[];
  anyOf?: JsonSchema[];
  type?: string | string[];
};
const contract = JSON.parse(
  readFileSync(
    join(import.meta.dir, "fixtures", "facade", "python-facade-tools.json"),
    "utf8",
  ),
) as { name: string; inputSchema: JsonSchema }[];
const python = new Map(contract.map((tool) => [tool.name, tool.inputSchema]));
/** Enum values anywhere in a property schema (direct or inside anyOf). */
function enums(schema: JsonSchema | undefined): string[] {
  if (!schema) return [];
  return [
    ...(schema.enum ?? []).map(String),
    ...(schema.anyOf ?? []).flatMap(enums),
  ].sort();
}

async function curatedTools() {
  const server = createServer({ toolset: "curated" });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    return await client.listTools();
  } finally {
    await client.close();
    await server.close();
  }
}

test("every Python facade tool is served or explicitly listed as unported", async () => {
  const served = new Set((await curatedTools()).map((tool) => tool.name));
  const unported = new Set<string>(UNPORTED_FACADE_TOOLS);
  for (const name of python.keys())
    expect([name, served.has(name) || unported.has(name)]).toEqual([
      name,
      true,
    ]);
  for (const name of served)
    expect([name, python.has(name)]).toEqual([name, true]);
  for (const name of unported) expect(served.has(name)).toBe(false);
});

test("served facade tools keep the Python parameters, required fields and enums", async () => {
  const mismatches: string[] = [];
  for (const tool of await curatedTools()) {
    const expected = python.get(tool.name);
    if (!expected) continue;
    const actual = tool.inputSchema as JsonSchema;
    const names = (schema: JsonSchema) =>
      Object.keys(schema.properties ?? {}).sort();
    if (JSON.stringify(names(actual)) !== JSON.stringify(names(expected)))
      mismatches.push(
        `${tool.name}: parameters ${names(actual)} != ${names(expected)}`,
      );
    const required = (schema: JsonSchema) =>
      [...(schema.required ?? [])].sort();
    if (JSON.stringify(required(actual)) !== JSON.stringify(required(expected)))
      mismatches.push(
        `${tool.name}: required ${required(actual)} != ${required(expected)}`,
      );
    for (const [parameter, schema] of Object.entries(
      expected.properties ?? {},
    )) {
      const want = enums(schema);
      if (!want.length) continue;
      const got = enums(actual.properties?.[parameter]);
      if (JSON.stringify(got) !== JSON.stringify(want))
        mismatches.push(`${tool.name}.${parameter}: enum ${got} != ${want}`);
    }
  }
  expect(mismatches).toEqual([]);
});

test("the default toolset is unchanged and PCA_TOOLSET selects curated", async () => {
  expect(toolsetFromEnv({})).toBe("full");
  expect(toolsetFromEnv({ PCA_TOOLSET: "Curated" })).toBe("curated");
  expect(() => toolsetFromEnv({ PCA_TOOLSET: "everything" })).toThrow();
  const server = createServer();
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const names = (await client.listTools()).map((tool) => tool.name);
    expect(names).toContain("search_applications");
    expect(names).not.toContain("search_uspto");
  } finally {
    await client.close();
    await server.close();
  }
});
