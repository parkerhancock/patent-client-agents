// Calls every curated facade tool and mode against the live offices and
// records what happens. Credentials come from the environment (see
// docs/facade.md); nothing here prints them.
// Usage: bun scripts/live-facade.ts <report.json> [--only=tool,tool]
// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { writeFile } from "node:fs/promises";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { cases, type Found, type Raw } from "./live-facade-cases.js";

const reportPath = Bun.argv[2];
if (!reportPath)
  throw new Error(
    "Usage: bun scripts/live-facade.ts <report.json> [--only=a,b]",
  );
const only = Bun.argv
  .find((a) => a.startsWith("--only="))
  ?.slice(7)
  .split(",");
const server = createServer({ toolset: "curated" });
const client = await Client.connect(server, {
  versionNegotiation: { mode: "legacy" },
});
const found: Found = {};
const results: Record<string, unknown>[] = [];
try {
  for (const entry of cases) {
    if (only && !only.includes(entry.tool) && !only.includes(entry.name))
      continue;
    const args =
      typeof entry.args === "function" ? entry.args(found) : entry.args;
    if (!args) {
      results.push({
        name: entry.name,
        tool: entry.tool,
        outcome: "skipped",
        reason: "no identifier from an earlier step",
      });
      console.log(`skip  ${entry.name}`);
      continue;
    }
    const started = performance.now();
    let raw: Raw;
    try {
      raw = (await client.callToolRaw(entry.tool, args)) as Raw;
    } catch (error) {
      raw = {
        isError: true,
        content: [
          {
            type: "text",
            text: error instanceof Error ? error.message : String(error),
          },
        ],
      };
    }
    const ms = Math.round(performance.now() - started);
    const content = raw.structuredContent ?? {};
    const text = raw.content?.find((c) => c.type === "text")?.text ?? "";
    const ok = !raw.isError;
    if (ok) entry.harvest?.(content, found);
    const outcome =
      ok === ((entry.expect ?? "ok") === "ok")
        ? "as expected"
        : ok
          ? "unexpected success"
          : "FAILED";
    const record = {
      name: entry.name,
      tool: entry.tool,
      args,
      outcome,
      ms,
      ...(ok
        ? {
            summary: String(content.summary ?? "").slice(0, 240),
            items: Array.isArray(content.items)
              ? content.items.length
              : undefined,
            not_found: content.not_found,
            artifact:
              typeof content.download_url === "string" ||
              typeof content.file_path === "string",
            size: content.size,
          }
        : { error: text.slice(0, 400) }),
    };
    results.push(record);
    console.log(
      `${outcome === "as expected" ? "ok  " : "FAIL"}  ${entry.name.padEnd(28)} ${String(ms).padStart(6)}ms  ${ok ? String(content.summary ?? "").slice(0, 90) : text.slice(0, 140)}`,
    );
    await Bun.sleep(1200);
  }
} finally {
  await client.close();
  await server.close();
  await writeFile(
    reportPath,
    JSON.stringify(
      { ran_at: new Date().toISOString(), found, results },
      null,
      2,
    ),
  );
}
