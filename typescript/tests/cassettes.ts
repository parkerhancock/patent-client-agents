import { resolve } from "node:path";
import { ApplicationsClient } from "@patent-client-agents/client";
import { useCassette } from "cassetter";

export const applicationNumber = "14412875";
export const cassetteDirectory = resolve(import.meta.dir, "cassettes");
export const successfulCassettes = [
  "search",
  "application",
  "documents",
] as const;

export async function recorded<T>(
  name: string,
  run: () => Promise<T>,
  mode: "none" | "all" = "none",
): Promise<T> {
  let result: T | undefined;
  await useCassette(
    resolve(cassetteDirectory, `odp-${name}.yaml`),
    {
      recordMode: mode,
      intercept: ["fetch"],
      matchOn: ["method", "uri", "json_body"],
      filterHeaders: ["uspto-api-key", "x-ibm-client-id"],
      filterQueryParameters: ["apiKey", "tk"],
    },
    async () => {
      result = await run();
    },
  );
  return result as T;
}

export async function applicationRecordings(mode: "none" | "all") {
  // Replay needs a non-secret placeholder to satisfy client configuration.
  const api = new ApplicationsClient({
    ...(mode === "all" ? {} : { apiKey: "replay-placeholder" }),
    retryLimit: 0,
  });
  const search = await recorded(
    "search",
    () =>
      api.search({
        query: `applicationNumberText:${applicationNumber}`,
        limit: 1,
      }),
    mode,
  );
  const application = await recorded(
    "application",
    () => api.get(applicationNumber),
    mode,
  );
  const documents = await recorded(
    "documents",
    () => api.getDocuments(applicationNumber),
    mode,
  );
  return { search, application, documents };
}
