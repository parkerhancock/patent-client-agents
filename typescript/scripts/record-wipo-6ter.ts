// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { Wipo6terClient } from "../packages/client/src/wipo-6ter.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  operations,
  sixterCassette,
  toolCalls,
} from "../tests/wipo-6ter-recordings.js";

/** Record the WIPO 6ter cassettes. Prints outcomes, never bodies. */
const pause = () => Bun.sleep(800);
const client = new Wipo6terClient({ retryLimit: 0 });

for (const [name, run] of Object.entries(operations)) {
  const outcome = await sixterCassette(
    name,
    () =>
      run(client).then(
        (value) => {
          const page = value as { signs?: unknown[]; count?: number };
          return page?.signs ? `${page.signs.length}/${page.count}` : "ok";
        },
        (error: Error) => `${error.name}: ${error.message.slice(0, 80)}`,
      ),
    true,
  );
  console.log(name, outcome);
  await pause();
}
for (const [name, [tool, args]] of Object.entries(toolCalls)) {
  const server = createServer({ clients: { wipo6ter: client } });
  const mcp = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await sixterCassette(
      `mcp-${name}`,
      () => mcp.callTool<{ summary: string }>(tool, args),
      true,
    );
    console.log(`mcp-${name}`, result.structuredContent?.summary);
  } finally {
    await mcp.close();
    await server.close();
  }
  await pause();
}
