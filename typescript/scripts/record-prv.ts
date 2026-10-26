// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { PrvClient } from "../packages/client/src/prv.js";
import { createServer } from "../packages/mcp/src/index.js";
import { operations, prvCassette, toolCalls } from "../tests/prv-recordings.js";

/** Record the PRV cassettes. Prints outcomes, never bodies. */
const pause = () => Bun.sleep(800);
const client = new PrvClient({ retryLimit: 0 });

for (const [name, run] of Object.entries(operations)) {
  const outcome = await prvCassette(
    name,
    () =>
      run(client).then(
        (value) => {
          const page = value as { rows?: unknown[]; total_hits?: number };
          return page.rows
            ? `${page.rows.length}/${page.total_hits}`
            : "record";
        },
        (error: Error) => `${error.name}: ${error.message.slice(0, 80)}`,
      ),
    true,
  );
  console.log(name, outcome);
  await pause();
}
for (const [name, [tool, args]] of Object.entries(toolCalls)) {
  const server = createServer({ clients: { prv: client } });
  const mcp = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await prvCassette(
      `mcp-${name}`,
      () => mcp.callTool<{ items: unknown[] }>(tool, args),
      true,
    );
    console.log(`mcp-${name}`, result.structuredContent?.items.length);
  } finally {
    await mcp.close();
    await server.close();
  }
  await pause();
}
