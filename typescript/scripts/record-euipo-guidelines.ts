// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { EuipoGuidelinesClient } from "../packages/client/src/euipo-guidelines.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  euipoGuidelinesCassette,
  operations,
  toolCalls,
  trimRecording,
} from "../tests/euipo-guidelines-recordings.js";

/** Record the EUIPO Guidelines cassettes. Prints outcomes, never bodies. */
const pause = () => Bun.sleep(800);
/** A fresh client per cassette, so each records its own publication lookup. */
const fresh = () => new EuipoGuidelinesClient({ retryLimit: 0 });
/** Cassette names to record, e.g. `bun run record:euipo-guidelines missing`; all when none. */
const only = process.argv.slice(2);
const wanted = (name: string) => !only.length || only.includes(name);

for (const [name, run] of Object.entries(operations)) {
  if (!wanted(name)) continue;
  const outcome = await euipoGuidelinesCassette(
    name,
    () =>
      run(fresh()).then(
        (value) => {
          const page = value as {
            hits?: unknown[];
            total?: number;
            nodes?: unknown[];
            length?: number;
            data?: { text?: string };
          };
          if (page.hits) return `${page.hits.length}/${page.total}`;
          if (page.nodes) return `${page.nodes.length} nodes`;
          if (Array.isArray(value)) return `${value.length} publications`;
          return `text ${page.data?.text?.length ?? 0} chars`;
        },
        (error: Error) => `${error.name}: ${error.message.slice(0, 80)}`,
      ),
    true,
  );
  await trimRecording(name);
  console.log(name, outcome);
  await pause();
}
for (const [name, [tool, args]] of Object.entries(toolCalls)) {
  if (!wanted(`mcp-${name}`)) continue;
  const server = createServer({ clients: { euipoGuidelines: fresh() } });
  const mcp = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await euipoGuidelinesCassette(
      `mcp-${name}`,
      () => mcp.callTool<{ summary: string }>(tool, args),
      true,
    );
    await trimRecording(`mcp-${name}`);
    console.log(`mcp-${name}`, result.structuredContent?.summary);
  } finally {
    await mcp.close();
    await server.close();
  }
  await pause();
}
