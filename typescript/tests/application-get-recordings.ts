import { ApplicationsClient } from "../packages/client/src/applications.js";
import { recorded } from "./cassettes.js";
export async function applicationPostDownloadRecording(mode: "all" | "none") {
  const client = new ApplicationsClient({
    ...(mode === "none" ? { apiKey: "replay-placeholder" } : {}),
    retryLimit: 0,
    timeoutMs: 20_000,
    maxResponseBytes: 4 * 1024 * 1024,
  });
  return recorded(
    "application-post-download",
    () =>
      client.downloadSearch({
        q: "applicationNumberText:14412875",
        fields: ["applicationNumberText"],
        format: "csv",
        pagination: { offset: 0, limit: 1 },
      }),
    mode,
  );
}
export async function applicationGetRecordings(mode: "all" | "none") {
  const client = new ApplicationsClient({
    ...(mode === "none" ? { apiKey: "replay-placeholder" } : {}),
    retryLimit: 0,
    timeoutMs: 20_000,
    maxResponseBytes: 4 * 1024 * 1024,
  });
  const search = await recorded(
    "application-get-search",
    () =>
      client.search({
        method: "GET",
        query: "applicationNumberText:14412875",
        fields: ["applicationNumberText"],
        limit: 1,
      }),
    mode,
  );
  if (mode === "all") await Bun.sleep(1000);
  const download = await recorded(
    "application-get-download",
    () =>
      client.downloadSearch(
        {
          q: "applicationNumberText:14412875",
          fields: ["applicationNumberText"],
          format: "csv",
          limit: 1,
        },
        { method: "GET" },
      ),
    mode,
  );
  if (mode === "all") await Bun.sleep(1000);
  const status = await recorded(
    "application-get-status-codes",
    () =>
      client.getStatusCodes(
        { q: "applicationStatusCode:150", limit: 1 },
        { method: "GET" },
      ),
    mode,
  );
  return { search, download, status };
}
