// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { PrhClient } from "../packages/client/src/prh.js";
import { createServer } from "../packages/mcp/src/index.js";
import { operations, prhCassette, toolCalls } from "../tests/prh-recordings.js";

/** Record the PRH cassettes. Prints outcomes, never bodies. */
const pause = () => Bun.sleep(800);
const client = new PrhClient({ retryLimit: 0 });

for (const [name, run] of Object.entries(operations)) {
  const outcome = await prhCassette(
    name,
    () =>
      run(client).then(
        (value) => {
          const page = value as { rows?: unknown[]; total_results?: number };
          return page.rows
            ? `${page.rows.length}/${page.total_results}`
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
  const server = createServer({ clients: { prh: client } });
  const mcp = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await prhCassette(
      `mcp-${name}`,
      () => mcp.callTool<{ items: unknown[] }>(tool, args),
      true,
    );
    console.log(
      `mcp-${name}`,
      result.structuredContent?.items?.length ?? "artifact",
    );
  } finally {
    await mcp.close();
    await server.close();
  }
  await pause();
}
