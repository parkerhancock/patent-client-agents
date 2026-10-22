import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  CopyrightClient,
  type CopyrightSearchResult,
} from "../packages/client/src/index.js";

export const copyrightCassette = resolve(
  import.meta.dir,
  "cassettes",
  "copyright.yaml",
);
type Lookup = Awaited<ReturnType<CopyrightClient["getRecord"]>>;
export interface CopyrightRecording {
  /** Keyword "Mickey Mouse": pre-1978 card-catalog registrations. */
  keyword: CopyrightSearchResult;
  /** Title "Steamboat Willie": Voyager and Siebel registrations plus recordations. */
  title: CopyrightSearchResult;
  /** Name "Walt Disney": recordations, with hit_count at the 50,000 cap. */
  name: CopyrightSearchResult;
  /** getRecord for a Voyager registration, a card-catalog card and a missing id. */
  voyager: Lookup;
  card: Lookup;
  missing: Lookup;
}

export const RECORDED_IDS = {
  voyager: "voyager_37022961",
  card: "card_catalog_CC19381945B_390000-391999.1449",
  missing: "voyager_99999999999",
} as const;

/** Replay (default) or record one session against the public records API. */
export async function copyrightRecording(
  record = false,
): Promise<CopyrightRecording> {
  if (!record && !existsSync(copyrightCassette))
    throw new Error("Missing Copyright Office cassette.");
  let result: CopyrightRecording | undefined;
  await useCassette(
    copyrightCassette,
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri", "body"],
    },
    async () => {
      const client = new CopyrightClient({ retryLimit: 0 });
      const keyword = await client.search({ query: "Mickey Mouse" });
      const title = await client.search({
        query: "Steamboat Willie",
        field: "title",
        pageSize: 20,
      });
      const name = await client.search({
        query: "Walt Disney",
        field: "name",
        pageSize: 2,
      });
      const voyager = await client.getRecord(RECORDED_IDS.voyager);
      const card = await client.getRecord(RECORDED_IDS.card);
      const missing = await client.getRecord(RECORDED_IDS.missing);
      result = { keyword, title, name, voyager, card, missing };
    },
  );
  return result as CopyrightRecording;
}
