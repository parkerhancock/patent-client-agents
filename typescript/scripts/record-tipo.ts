// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { TipoClient } from "../packages/client/src/tipo.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  operations,
  tipoCassette,
  toolCalls,
} from "../tests/tipo-recordings.js";

/**
 * Record the TIPO cassettes. Needs TIPO_API_KEY (the data.gov.tw demo tk
 * works); the token is filtered from every recorded URI. Prints counts,
 * never bodies.
 */
const tk = process.env.TIPO_API_KEY?.trim();
if (!tk) throw new Error("Set TIPO_API_KEY to record TIPO cassettes.");
const pause = () => Bun.sleep(800);
const client = new TipoClient({ tk, retryLimit: 0 });

for (const [name, run] of Object.entries(operations)) {
  const outcome = await tipoCassette(
    name,
    () =>
      run(client).then(
        (page) => `${page.rows.length}/${page.total_count}`,
        (error: Error) => `${error.name}: ${error.message.slice(0, 80)}`,
      ),
    true,
  );
  console.log(name, outcome);
  await pause();
}
// A token TIPO does not know: it answers with sample data, status "sample".
await tipoCassette(
  "sample-token",
  () =>
    new TipoClient({
      tk: "00000000-0000-0000-0000-000000000000",
      retryLimit: 0,
    })
      .query("PatentAppl", { top: 1 })
      .catch((error: Error) => error.message),
  true,
);
for (const [name, [tool, args]] of Object.entries(toolCalls)) {
  const server = createServer({ clients: { tipo: client } });
  const mcp = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await tipoCassette(
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
