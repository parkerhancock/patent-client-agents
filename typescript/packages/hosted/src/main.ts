import { createHostedApp } from "./app.js";
import { loadConfig } from "./config.js";
import { prepareCorpora } from "./corpora.js";
import { logEvent } from "./usage.js";

/**
 * Container entrypoint: validate configuration, bootstrap corpora, then bind.
 * Any failure before binding exits non-zero so Cloud Run reports it instead
 * of serving a half-configured instance.
 */
async function main() {
  const config = loadConfig(process.env);
  // The client library reads this when each connector is constructed.
  process.env.PATENT_CLIENT_AGENTS_CACHE = config.httpCache;
  await prepareCorpora(config.corpora);
  const app = await createHostedApp(config);
  const listener = Bun.serve({
    hostname: config.host,
    port: config.port,
    // Tool calls such as file-history downloads can run for minutes; Bun's
    // default idle timeout is 10 s. Cloud Run applies its own request timeout.
    idleTimeout: 0,
    // MCP and OAuth requests are small; bound what one request can buffer.
    maxRequestBodySize: 8 * 1024 * 1024,
    fetch: (request) => app.fetch(request),
  });
  logEvent("startup", {
    url: `http://${listener.hostname}:${listener.port}`,
    public_url: config.publicUrl,
    auth: config.authBypass ? "bypass" : "google",
    state_backend: config.stateBackend,
    hidden_tools: config.hiddenTools,
    credentials: config.credentials,
    http_cache: config.httpCache,
  });
  let stopping = false;
  for (const signal of ["SIGINT", "SIGTERM"] as const)
    process.once(signal, () => {
      if (stopping) return;
      stopping = true;
      void (async () => {
        await listener.stop();
        await app.close();
      })().then(
        () => process.exit(0),
        () => process.exit(1),
      );
    });
}

main().catch((error: unknown) => {
  logEvent(
    "startup_failed",
    { error: error instanceof Error ? error.message : String(error) },
    undefined,
    "ERROR",
  );
  process.exit(1);
});
