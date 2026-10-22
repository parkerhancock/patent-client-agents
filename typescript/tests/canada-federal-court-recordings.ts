import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  ApiError,
  CanadaFederalCourtClient,
  type FederalCourtCaseRecord,
  type FederalCourtCaseSearchResponse,
  type FederalCourtDocketResponse,
} from "../packages/client/src/index.js";
import {
  getCanadaFederalCourtCases,
  listCanadaFederalCourtDocketEntries,
  searchCanadaFederalCourtPatentCases,
} from "../packages/mcp/src/canada-federal-court.js";

export const canadaFederalCourtCassette = resolve(
  import.meta.dir,
  "cassettes",
  "canada-federal-court.yaml",
);
export interface CanadaFederalCourtRecording {
  /** "Taro Pharmaceuticals", patent-only (the default). */
  patent: FederalCourtCaseSearchResponse;
  /** The same party, every nature, up to 100. */
  all: FederalCourtCaseSearchResponse;
  /** "Pfizer" filed during 2024 (the dated endpoint). */
  dated: FederalCourtCaseSearchResponse;
  /** "Apotex Inc." sent as typed: only names stored with the period match. */
  dotted: FederalCourtCaseSearchResponse;
  /** T-2962-24 (lower-case input): metadata, parties, patents. */
  record: FederalCourtCaseRecord;
  /** T-649-23, filed at 23:41 Eastern on March 30, 2023. */
  evening: FederalCourtCaseRecord;
  docket: FederalCourtDocketResponse;
  /** Error raised for a file number the Registry does not know. */
  missing: unknown;
  /** MCP search over the same party with status fan-out, five results. */
  mcpSearch: Awaited<ReturnType<typeof searchCanadaFederalCourtPatentCases>>;
  /** MCP get over one known and one unknown file. */
  mcpGet: Awaited<ReturnType<typeof getCanadaFederalCourtCases>>;
  mcpDocket: Awaited<ReturnType<typeof listCanadaFederalCourtDocketEntries>>;
}

/** Replay (default) or record one session against the public Court Files endpoints. */
export async function canadaFederalCourtRecording(
  record = false,
): Promise<CanadaFederalCourtRecording> {
  if (!record && !existsSync(canadaFederalCourtCassette))
    throw new Error("Missing Canada Federal Court cassette.");
  let result: CanadaFederalCourtRecording | undefined;
  await useCassette(
    canadaFederalCourtCassette,
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
    },
    async () => {
      const client = new CanadaFederalCourtClient({ retryLimit: 0 });
      const patent = await client.searchPartyCases({
        partyName: "Taro Pharmaceuticals",
      });
      const all = await client.searchPartyCases({
        partyName: "Taro Pharmaceuticals",
        patentOnly: false,
        limit: 100,
      });
      const dated = await client.searchPartyCases({
        partyName: "Pfizer",
        filedFrom: "2024-01-01",
        filedTo: "2024-12-31",
      });
      const dotted = await client.searchPartyCases({
        partyName: "Apotex Inc.",
        patentOnly: false,
      });
      const recordT = await client.getCase("t-2962-24");
      const evening = await client.getCase("T-649-23");
      const docket = await client.listDocketEntries("T-2962-24");
      const missing = await client
        .getCase("T-99999-99")
        .then(() => undefined)
        .catch((error: unknown) => {
          if (!(error instanceof ApiError)) throw error;
          return error;
        });
      const mcpSearch = await searchCanadaFederalCourtPatentCases(client, {
        party_name: "Taro Pharmaceuticals",
        division: "t",
        limit: 5,
        patent_only: true,
        assess_status: true,
        full: false,
      });
      const mcpGet = await getCanadaFederalCourtCases(
        client,
        ["T-2962-24", "T-99999-99"],
        "t",
      );
      const mcpDocket = await listCanadaFederalCourtDocketEntries(client, {
        court_number: "T-2962-24",
        division: "t",
        limit: 5,
        full: false,
      });
      result = {
        patent,
        all,
        dated,
        dotted,
        record: recordT,
        evening,
        docket,
        missing,
        mcpSearch,
        mcpGet,
        mcpDocket,
      };
    },
  );
  return result as CanadaFederalCourtRecording;
}
