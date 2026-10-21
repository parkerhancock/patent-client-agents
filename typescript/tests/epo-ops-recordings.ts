import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { EpoOpsClient } from "../packages/client/src/epo-ops.js";

/** Public OPS samples. EP1000000 is the long-standing OPS documentation example. */
export const samples = {
  query: "ta=CRISPR and pa=Broad Institute",
  emptyQuery: 'ta="zzqvxjk nonexistent phrase"',
  publication: "EP1000000A1",
  granted: "EP1000000B1",
  epNumber: "EP1000000",
  unitary: "EP4108782",
  usPgpub: "US20050262543A1",
  cpc: "H04L9/32",
  cpcQuery: "machine learning",
} as const;

type Run = (client: EpoOpsClient) => Promise<unknown>;
export const operations: Record<string, Run> = {
  search: (c) => c.search(samples.query, { rangeBegin: 1, rangeEnd: 5 }),
  "search-empty": (c) => c.search(samples.emptyQuery, { rangeEnd: 5 }),
  biblio: (c) => c.getBiblio(samples.publication),
  "biblio-us-pgpub": (c) => c.getBiblio(samples.usPgpub),
  citations: (c) => c.getCitations(samples.publication),
  equivalents: (c) => c.getEquivalents(samples.publication),
  claims: (c) => c.getFullText(samples.granted, "claims"),
  description: (c) => c.getFullText(samples.granted, "description"),
  family: (c) => c.getFamily(samples.publication),
  "legal-events": (c) => c.getLegalEvents(samples.publication),
  "register-biblio": (c) => c.getRegisterBiblio(samples.epNumber),
  "register-events": (c) => c.getRegisterEvents(samples.epNumber),
  "register-procedural-steps": (c) =>
    c.getRegisterProceduralSteps(samples.epNumber),
  "unitary-patent": (c) => c.getUnitaryPatentPackage(samples.unitary),
  "unitary-patent-none": (c) => c.getUnitaryPatentPackage(samples.epNumber),
  "number-conversion": (c) => c.convertNumber(samples.publication),
  "cpci-biblio": (c) => c.getCpciBiblio(samples.publication),
  "cpc-retrieve": (c) => c.retrieveCpc(samples.cpc, { depth: 1 }),
  "cpc-search": (c) => c.searchCpc(samples.cpcQuery, { rangeEnd: 5 }),
  "cpc-map": (c) => c.mapClassification("cpc", samples.cpc, "ipc"),
  "family-evidence": (c) => c.getFamilyEvidence(samples.publication),
  pdf: (c) => c.downloadPdf(samples.publication),
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `epo-ops-${name}.yaml`);

/**
 * Replay (default) or record one operation. Each cassette holds its own
 * token exchange; Cassetter's defaults drop the Authorization header and
 * the access_token body field before anything reaches disk.
 */
export async function epoRecording<T = unknown>(
  name: string,
  credentials?: { apiKey: string; apiSecret: string },
): Promise<T> {
  const run = operations[name];
  if (!run) throw new Error(`Unknown EPO OPS operation: ${name}`);
  const record = credentials !== undefined;
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing EPO OPS cassette: ${name}`);
  let result: unknown;
  await useCassette(
    cassettePath(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
      // OPS echoes the caller's IP address in these response headers.
      filterHeaders: [
        "authorization",
        "x-api-key",
        "x-epo-client-ip",
        "x-epo-forwarded",
      ],
      bodyScrubPatterns: ["access_token", "client_id", "api_product_list"],
    },
    async () => {
      result = await run(
        new EpoOpsClient({
          ...(credentials ?? {
            apiKey: "replay-placeholder",
            apiSecret: "replay-placeholder",
          }),
          retryLimit: 0,
        }),
      );
    },
  );
  return result as T;
}
