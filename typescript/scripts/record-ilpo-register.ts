// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { IlpoRegisterClient } from "../packages/client/src/ilpo-register.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  ilpoCassette,
  operations,
  toolCalls,
} from "../tests/ilpo-register-recordings.js";

/** Record the ILPO register cassettes. Prints outcomes, never bodies. */
const pause = () => Bun.sleep(800);
const client = new IlpoRegisterClient({ retryLimit: 0 });

for (const [name, run] of Object.entries(operations)) {
  const outcome = await ilpoCassette(
    name,
    () =>
      run(client).then(
        (value) => {
          const page = value as { rows?: unknown[]; total?: number };
          return Array.isArray(value)
            ? `${value.length} rows`
            : `${page.rows?.length}/${page.total}`;
        },
        (error: Error) => `${error.name}: ${error.message.slice(0, 80)}`,
      ),
    true,
  );
  console.log(name, outcome);
  await pause();
}
for (const [name, [tool, args]] of Object.entries(toolCalls)) {
  const server = createServer({ clients: { ilpoRegister: client } });
  const mcp = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await ilpoCassette(
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
