import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  CafcClient,
  type CafcSearchResult,
} from "../packages/client/src/index.js";

export const cafcCassette = resolve(import.meta.dir, "cassettes", "cafc.yaml");
export interface CafcRecording {
  /** PTO/DCT/ITC/CFC opinions released June-September 2026; 150 rows over two pages. */
  patentOpinions: CafcSearchResult;
  /** Free-text search for "valtrus". */
  query: CafcSearchResult;
  /** findAppeal with a four-digit-year appeal number. */
  appeal: CafcSearchResult;
  pdf: Awaited<ReturnType<CafcClient["downloadPdf"]>>;
}

/**
 * Replay (default) or record one session against the public CAFC site. The
 * session shares one client, so the opinions page (and its nonce) is fetched
 * once and request bodies replay in order.
 */
export async function cafcRecording(record = false): Promise<CafcRecording> {
  if (!record && !existsSync(cafcCassette))
    throw new Error("Missing CAFC cassette.");
  let result: CafcRecording | undefined;
  await useCassette(
    cafcCassette,
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri", "body"],
    },
    async () => {
      const client = new CafcClient({ retryLimit: 0 });
      const patentOpinions = await client.searchPatentOpinions({
        dateFrom: "2026-06-01",
        dateTo: "2026-09-30",
        maxResults: 150,
      });
      const query = await client.search({ query: "valtrus", maxResults: 25 });
      const appeal = await client.findAppeal("2024-1945");
      const url = appeal.data[0]?.pdf_url;
      if (!url) throw new Error("Appeal 24-1945 has no PDF.");
      const pdf = await client.downloadPdf(url);
      result = { patentOpinions, query, appeal, pdf };
    },
  );
  return result as CafcRecording;
}
