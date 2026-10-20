import { chmod, mkdtemp, rmdir, stat, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";
import { createFileWafSessionStore } from "../packages/waf-session/src/index.js";
import { refreshWafSession } from "../packages/waf-worker/src/index.js";

if (Bun.argv.slice(2).join(" ") !== "--live") {
  console.error(
    JSON.stringify({ verified: false, code: "EXPLICIT_LIVE_REQUIRED" }),
  );
  process.exit(1);
}
const directory = await mkdtemp(join(tmpdir(), "pca-waf-verification-"));
await chmod(directory, 0o700);
const filename = join(directory, "session.json");
let verified = false;
let stage = "acquisition";
let cleanedUp = true;
try {
  await refreshWafSession(createFileWafSessionStore(filename), {
    timeoutMs: 45000,
  });
  stage = "file";
  if (((await stat(filename)).mode & 0o777) !== 0o600) throw new Error();
  process.env.PCA_WAF_TOKEN_FILE = filename;
  delete process.env.PCA_WAF_SECRET_RESOURCE;
  // Prove that default MCP delivery takes precedence over a frozen snapshot.
  process.env.PCA_WAF_TOKEN_JSON = JSON.stringify({
    token: "synthetic-stale-snapshot",
    expires: Date.now() / 1000 + 86400,
  });
  stage = "mcp";
  const server = createServer();
  try {
    const client = await Client.connect(server, {
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const response = await client.callTool<{ items: unknown[] }>(
        "search_trademarks",
        {
          wordmark: "APPLE",
          limit: 1,
        },
      );
      if (response.isError || response.structuredContent?.items.length !== 1)
        throw new Error();
      verified = true;
    } finally {
      await client.close();
    }
  } finally {
    await server.close();
  }
} catch {
  // Never log a browser/request/provider error, response, or credential.
  process.exitCode = 1;
} finally {
  try {
    await unlink(filename).catch((error: NodeJS.ErrnoException) => {
      if (error.code !== "ENOENT") throw error;
    });
    await rmdir(directory);
  } catch {
    cleanedUp = false;
    process.exitCode = 1;
  }
}
console.log(
  JSON.stringify({ verified: verified && cleanedUp, stage, cleanedUp }),
);
