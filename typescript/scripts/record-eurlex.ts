// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { EurlexClient } from "../packages/client/src/eurlex.js";
import { createServer } from "../packages/mcp/src/index.js";
import {
  eurlexCassette,
  operations,
  toolCalls,
} from "../tests/eurlex-recordings.js";

/** Record the EUR-Lex cassettes. Prints outcomes, never bodies. */
const pause = () => Bun.sleep(800);
const client = new EurlexClient({ retryLimit: 0 });
/** Cassette names to record, e.g. `bun run record:eurlex missing`; all when none. */
const only = process.argv.slice(2);
const wanted = (name: string) => !only.length || only.includes(name);

for (const [name, run] of Object.entries(operations)) {
  if (!wanted(name)) continue;
  const outcome = await eurlexCassette(
    name,
    () =>
      run(client).then(
        (value) => {
          const page = value as {
            cases?: unknown[];
            total?: number;
            acts?: unknown[];
            data?: { text?: string };
          };
          if (page.cases) return `${page.cases.length}/${page.total}`;
          if (page.acts) return `${page.acts.length} acts`;
          return `text ${page.data?.text?.length ?? 0} chars`;
        },
        (error: Error) => `${error.name}: ${error.message.slice(0, 80)}`,
      ),
    true,
  );
  console.log(name, outcome);
  await pause();
}
for (const [name, [tool, args]] of Object.entries(toolCalls)) {
  if (!wanted(`mcp-${name}`)) continue;
  const server = createServer({ clients: { eurlex: client } });
  const mcp = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    const result = await eurlexCassette(
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
