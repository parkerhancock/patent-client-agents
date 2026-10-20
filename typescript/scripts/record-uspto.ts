import {
  BulkDataClient,
  OfficeActionsClient,
  PetitionsClient,
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
} from "@patent-client-agents/client";
import { recorded } from "../tests/cassettes.js";

const record = Bun.argv.includes("--record"),
  replay = Bun.argv.includes("--replay");
if (record === replay) throw new Error("Choose --record or --replay.");
if (record && !process.env.USPTO_ODP_API_KEY)
  throw new Error("Configure USPTO_ODP_API_KEY before recording.");
const mode = record ? "all" : "none";
const options = {
  apiKey: record
    ? (process.env.USPTO_ODP_API_KEY as string)
    : "replay-placeholder",
  retryLimit: 0,
  timeoutMs: 20000,
};
const trials = new PtabTrialsClient(options),
  appeals = new PtabAppealsClient(options),
  interferences = new PtabInterferencesClient(options),
  petitions = new PetitionsClient(options),
  bulk = new BulkDataClient(options),
  officeActions = new OfficeActionsClient(options);
const operations: [string, () => Promise<{ count?: number | undefined }>][] = [
  ["ptab-proceedings", () => trials.searchProceedings({ limit: 1 })],
  ["ptab-decisions", () => trials.searchDecisions({ limit: 1 })],
  ["ptab-documents", () => trials.searchDocuments({ limit: 1 })],
  ["ptab-appeals", () => appeals.search({ limit: 1 })],
  ["ptab-interferences", () => interferences.search({ limit: 1 })],
  ["petitions", () => petitions.search({ limit: 1 })],
  ["bulk-products", () => bulk.search({ limit: 1 })],
  ["office-actions", () => officeActions.search({ limit: 1 })],
];
let failed = false;
for (const [name, run] of operations) {
  try {
    const result = await recorded(name, run, mode);
    if (result.count === undefined || result.count < 1)
      throw new Error("Expected positive live coverage");
    console.log(JSON.stringify({ name, mode, count: result.count }));
  } catch (error) {
    failed = true;
    console.log(
      JSON.stringify({
        name,
        mode,
        status:
          typeof error === "object" && error && "status" in error
            ? error.status
            : undefined,
        code:
          typeof error === "object" && error && "code" in error
            ? error.code
            : "CONTRACT_ERROR",
      }),
    );
  }
}
if (failed) process.exitCode = 1;
