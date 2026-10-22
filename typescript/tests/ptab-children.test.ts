import { expect, test } from "bun:test";
import { PtabTrialsClient } from "../packages/client/src/index.js";

test("a trial with no decisions yet reads as an empty list, not an error", async () => {
  const requests: string[] = [];
  const trials = new PtabTrialsClient({
    apiKey: "synthetic",
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(new Request(input, init).url).pathname;
      requests.push(path);
      // Live ODP behavior observed October 21, 2026 for pending IPR2026-00505.
      return path.endsWith("/decisions")
        ? new Response(
            JSON.stringify({ code: 404, message: "No matching records found" }),
            { status: 404 },
          )
        : Response.json({
            count: 1,
            patentTrialDocumentDataBag: [{ documentIdentifier: "d1" }],
          });
    }) as unknown as typeof fetch,
  });
  const decisions = await trials.getDecisionsByTrial("IPR2026-00505");
  expect(decisions.count).toBe(0);
  expect(decisions.patentTrialDocumentDataBag).toEqual([]);
  expect((await trials.getDocumentsByTrial("IPR2026-00505")).count).toBe(1);
  expect(requests).toEqual([
    "/api/v1/patent/trials/IPR2026-00505/decisions",
    "/api/v1/patent/trials/IPR2026-00505/documents",
  ]);
});
