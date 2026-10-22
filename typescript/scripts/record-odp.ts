// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import {
  applicationNumber,
  applicationRecordings,
  recorded,
} from "../tests/cassettes.js";

const record = Bun.argv.includes("--record");
const replay = Bun.argv.includes("--replay");
if (record === replay)
  throw new Error("Choose exactly one of --record or --replay.");
const mode = record ? "all" : "none";

if (Bun.argv.includes("--anonymous")) {
  const status = await recorded(
    "unauthenticated",
    async () => {
      const response = await fetch(
        `https://api.uspto.gov/api/v1/patent/applications/${applicationNumber}`,
        {
          headers: { Accept: "application/json" },
          signal: AbortSignal.timeout(15_000),
          redirect: "error",
        },
      );
      await response.text();
      if (response.status !== 401 && response.status !== 403) {
        throw new Error(
          `Expected an unauthenticated error, received HTTP ${response.status}.`,
        );
      }
      return response.status;
    },
    mode,
  );
  console.log(
    `${record ? "Recorded" : "Replayed"} anonymous ODP HTTP ${status}; this does not verify successful API access.`,
  );
} else {
  if (record && !process.env.USPTO_ODP_API_KEY) {
    throw new Error(
      "Configure USPTO_ODP_API_KEY in the environment before recording. No requests made.",
    );
  }
  const results = await applicationRecordings(mode);
  console.log(
    JSON.stringify({
      mode,
      applicationNumber,
      searchCount: results.search.count,
      applicationCount: results.application.count,
      documents: results.documents.documents.length,
    }),
  );
}
