// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import {
  ckanCassette,
  omitHtmlBodies,
  operations,
  replayClients,
  toolCalls,
} from "../tests/ckan-recordings.js";

/** Record the ILPO and IP Australia catalog cassettes. Prints outcomes, never bodies. */
const pause = () => Bun.sleep(800);
const clients = replayClients();

for (const [name, run] of Object.entries(operations)) {
  const outcome = await ckanCassette(
    name,
    () =>
      run(clients).then(
        (value) => {
          const result = value as {
            data: { name: string; resources: unknown[] };
          };
          return `${result.data.name}: ${result.data.resources.length} resources`;
        },
        (error: Error) => `${error.name}: ${error.message.slice(0, 80)}`,
      ),
    true,
  );
  console.log(name, outcome);
  await omitHtmlBodies(name);
  await pause();
}
for (const [name, [tool, args]] of Object.entries(toolCalls)) {
  const server = createServer({
    clients: { ilpoTm: clients.ilpo, ipaBulk: clients.ipa },
  });
  const mcp = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await ckanCassette(
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
