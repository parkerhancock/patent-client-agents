import {
  createFileWafSessionStore,
  createGoogleWafSessionStore,
  type WafSessionStore,
} from "@patent-client-agents/waf-session";
import {
  assertSafeWorkerEnvironment,
  refreshWafSession,
  WafWorkerError,
} from "./index.js";

export function configuredStore(
  args: string[],
  environment: Record<string, string | undefined>,
): WafSessionStore {
  let file = environment.PCA_WAF_TOKEN_FILE?.trim();
  let resource = environment.PCA_WAF_SECRET_RESOURCE?.trim();
  const seen = new Set<string>();
  for (let index = 0; index < args.length; index++) {
    const argument = args[index];
    if (
      (argument !== "--output-file" && argument !== "--secret-resource") ||
      seen.has(argument)
    )
      throw new WafWorkerError("INVALID_CONFIGURATION");
    seen.add(argument);
    const value = args[++index]?.trim();
    if (!value || value.startsWith("--"))
      throw new WafWorkerError("INVALID_CONFIGURATION");
    if (argument === "--output-file") file = value;
    else resource = value;
  }
  if (
    (file !== undefined && !file) ||
    (resource !== undefined && !resource) ||
    Boolean(file) === Boolean(resource)
  )
    throw new WafWorkerError("INVALID_CONFIGURATION");
  if (file) return createFileWafSessionStore(file);
  if (resource) return createGoogleWafSessionStore(resource);
  throw new WafWorkerError("INVALID_CONFIGURATION");
}

if (import.meta.main) {
  try {
    assertSafeWorkerEnvironment();
    const store = configuredStore(Bun.argv.slice(2), process.env);
    const result = await refreshWafSession(store);
    console.log(JSON.stringify(result));
  } catch (error) {
    console.error(
      JSON.stringify({
        refreshed: false,
        code: error instanceof WafWorkerError ? error.code : "WORKER_FAILURE",
      }),
    );
    process.exitCode = 1;
  }
}
