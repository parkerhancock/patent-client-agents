import { chmod, mkdtemp, rmdir, stat, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { TrademarkSearchClient } from "../packages/client/src/index.js";
import {
  createFileWafSessionStore,
  createWafSessionProvider,
} from "../packages/waf-session/src/index.js";
import { refreshWafSession } from "../packages/waf-worker/src/index.js";

// Run inside the worker image; never print exceptions or session contents.
if (Bun.argv.slice(2).join(" ") !== "--live") {
  console.error(
    JSON.stringify({ verified: false, code: "EXPLICIT_LIVE_REQUIRED" }),
  );
  process.exit(1);
}
let directory: string | undefined;
let filename: string | undefined;
let stage = "runtime";
let verified = false;
let cleanedUp = true;
try {
  if (process.platform !== "linux" || process.getuid?.() === 0)
    throw new Error();
  directory = await mkdtemp(join(tmpdir(), "pca-waf-container-"));
  await chmod(directory, 0o700);
  filename = join(directory, "session.json");
  const store = createFileWafSessionStore(filename);
  stage = "acquisition";
  await refreshWafSession(store, { timeoutMs: 45000 });
  stage = "delivery";
  if (((await stat(filename)).mode & 0o777) !== 0o600) throw new Error();
  const client = new TrademarkSearchClient({
    sessionProvider: createWafSessionProvider(store),
  });
  stage = "search";
  const result = await client.search({ wordmark: "APPLE", size: 1 });
  if (result.results.length !== 1) throw new Error();
  verified = true;
} catch {
  process.exitCode = 1;
} finally {
  try {
    if (filename)
      await unlink(filename).catch((error: NodeJS.ErrnoException) => {
        if (error.code !== "ENOENT") throw error;
      });
    if (directory) await rmdir(directory);
  } catch {
    cleanedUp = false;
    process.exitCode = 1;
  }
}
console.log(
  JSON.stringify({ verified: verified && cleanedUp, stage, cleanedUp }),
);
