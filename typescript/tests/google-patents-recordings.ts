import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  GooglePatentsClient,
  GooglePatentsRateLimiter,
} from "../packages/client/src/index.js";

export const googleOperations = {
  search: (c: GooglePatentsClient) =>
    c.search({
      keywords: ["lithium battery thermal management"],
      countries: ["US"],
      before: "2020-01-01",
      pageSize: 10,
    }),
  "patent-us": (c: GooglePatentsClient) => c.getPatent("US7654321B2"),
  "patent-jp": (c: GooglePatentsClient) => c.getPatent("JP2019000001A"),
  /** Recorded while Google was throttling this machine: a real 503. */
  throttled: (c: GooglePatentsClient) =>
    c
      .search({
        keywords: ["lithium battery thermal management"],
        countries: ["US"],
        before: "2020-01-01",
        pageSize: 10,
      })
      .catch((error) => ({
        error: error.code,
        retryAfter: error.retryAfterSeconds,
      })),
  "not-found": (c: GooglePatentsClient) =>
    c.getPatent("US99999999999B9").catch((error) => ({ error: error.code })),
  pdf: (c: GooglePatentsClient) => c.downloadPdf("USD900000S1"),
} as const;
export type GoogleOperation = keyof typeof googleOperations;
export const googleCassette = (name: string) =>
  resolve(import.meta.dir, "cassettes", `google-patents-${name}.yaml`);

/** Replay (default) or record one operation; replay skips the throttle. */
export async function googleRecording<T = unknown>(
  name: GoogleOperation,
  record = false,
): Promise<T> {
  if (!record && !existsSync(googleCassette(name)))
    throw new Error(`Missing Google Patents cassette: ${name}`);
  let result: unknown;
  await useCassette(
    googleCassette(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
      filterHeaders: ["set-cookie", "cookie", "nel", "report-to"],
    },
    async () => {
      result = await googleOperations[name](
        new GooglePatentsClient({
          rateLimiter: new GooglePatentsRateLimiter(record ? 6_000 : 0, 90_000),
        }),
      );
    },
  );
  // Google pages embed the public browser key of its feedback widget; keep
  // it out of the repository so secret scanners stay quiet.
  if (record && existsSync(googleCassette(name)))
    writeFileSync(
      googleCassette(name),
      readFileSync(googleCassette(name), "utf8").replace(
        /AIza[0-9A-Za-z_-]{35}/g,
        "AIzaREDACTED",
      ),
    );
  return result as T;
}
