import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { KiprisClient } from "../packages/client/src/index.js";

export const kiprisCassette = resolve(
  import.meta.dir,
  "cassettes",
  "kipris.yaml",
);
/** The cassette stores this in place of the ServiceKey; replay sends it too. */
export const KIPRIS_REPLAY_KEY = "REDACTED";

/**
 * Replay (default) or record one KIPRIS Plus session: a search and a
 * bibliography lookup per service. Recording needs KIPO_KIPRIS_API_KEY;
 * the cassette filter replaces ServiceKey before anything is written.
 */
export async function kiprisRecording(record = false) {
  if (!record && !existsSync(kiprisCassette))
    throw new Error("Missing KIPRIS cassette.");
  let result: Awaited<ReturnType<typeof session>> | undefined;
  await useCassette(
    kiprisCassette,
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
      filterQueryParameters: ["ServiceKey", "serviceKey"],
      replacement: KIPRIS_REPLAY_KEY,
    },
    async () => {
      result = await session(
        new KiprisClient({
          ...(record ? {} : { serviceKey: KIPRIS_REPLAY_KEY }),
          retryLimit: 0,
        }),
      );
    },
  );
  return result as Awaited<ReturnType<typeof session>>;
}

async function session(client: KiprisClient) {
  const patents = await client.searchPatentsWord("센서", { numOfRows: 2 });
  const number = patents.items[0]?.applicationNumber;
  if (!number) throw new Error("The patent search returned no rows.");
  const patentAdvanced = await client.searchPatentsAdvanced({
    inventionTitle: "센서",
    numOfRows: 2,
  });
  const patent = await client.getPatent(number);
  const patentBibliography = await client.getPatentBibliography(number);
  const trademarks = await client.searchTrademarksWord("롯데", {
    numOfRows: 2,
  });
  const trademarkAdvanced = await client.searchTrademarksAdvanced({
    title: "롯데",
    numOfRows: 2,
  });
  const markNumber = trademarks.items[0]?.applicationNumber;
  const trademarkBibliography = markNumber
    ? await client.getTrademarkBibliography(markNumber)
    : null;
  const designs = await client.searchDesignsWord("한국", { numOfRows: 2 });
  const designAdvanced = await client.searchDesignsAdvanced({
    articleName: "직물지",
    numOfRows: 2,
  });
  const designNumber = designs.items[0]?.applicationNumber;
  const designBibliography = designNumber
    ? await client.getDesignBibliography(designNumber)
    : null;
  return {
    patents,
    patentAdvanced,
    patent,
    patentBibliography,
    trademarks,
    trademarkAdvanced,
    trademarkBibliography,
    designs,
    designAdvanced,
    designBibliography,
  };
}
